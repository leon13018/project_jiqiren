"""S4 非阻塞 TTS 模組 — daemon worker thread + FIFO queue + shutdown cleanup。

S4 範圍（incremental-rebuild 第 4 步）：
    - 對外 API 不變：`speak(text)` 仍是 module-level 函式，signature 相容 S2
    - 新增 `shutdown()`：程式退出時 terminate 當前播放中的 mpg123 + 清空 queue
    - 改造重點：caller thread 立即返回（不阻塞），實際 synth + 播放在背景 daemon
      thread 內 FIFO 順序消費

S4 動機（S2 同步阻塞實機踩到的問題）：
    1. L1 hawk speak 期間商家按 q 想退出 → 主線程被 mpg123.wait() 卡死、input()
       沒在跑、q 只能存 stdin buffer 等 speak 播完才響應（3-5s 延遲）
    2. 主線程被阻塞時無法及時響應其他輪詢（如 hawk 叫賣輪播 / 讀鍵）
    3. 程式結束時最後一段 mpg123 仍在播完才停（沒 cleanup）

設計準則（依 `.claude/rules/incremental-rebuild.md` S4 段）：
    - **預設 FIFO 不中斷**：say(text) 只 put 進 queue，不終止當前任務、不清 queue
      （中斷邏輯是 S7 的選擇性升級，不是 S4 預設）
    - **單 queue 單消費者**：避免旗號分流 race
    - **`_proc` lock 保護**：worker thread 設值 vs main thread shutdown 讀/terminate
      之間 race（thread-safe pattern，依 [[threading-conventions]] 推薦）
    - **失敗策略保留 S2 noisy**：synth / play 失敗 noisy print + continue 下一輪；
      shutdown 觸發的 SIGTERM 也走 CalledProcessError path（returncode 負值），
      仍印訊息但屬 expected exit
    - **print 在 caller thread**：`speak()` 內立即印 `[語音] xxx`，**不**放到
      `_loop()` 內 — 保持 SSH log 時序跟 dialog flow 一致（user 看到「[語音]
      xxx」緊接著「[商家] >」prompt，不會因 worker 延遲導致 log 亂序）

caller（main.py 的 speak callback / main 函式）使用方式：
    >>> from myProgram import tts
    >>> tts.speak("歡迎光臨")  # 立即返回（入 queue，不阻塞）
    >>> # ... 主線程做別的事 ...
    >>> tts.shutdown()          # 程式退出前 cleanup（terminate + drain queue）

speak_and_wait（2026-05-30 v2 加 — wall-clock budget pattern）：
    >>> tts.speak_and_wait("您好，請選擇")  # say + wait_idle 連續 call，阻塞至播完
    >>> deadline = time.monotonic() + 6.0  # 從這裡開始計 6s budget — TTS 已播完

設計動機：先 speak 再立刻算 deadline = monotonic + 6 → 6s 預算被 TTS 播放時間
（典型 2-4s）吃掉，顧客實際只剩 2-4s 回應。speak_and_wait 阻塞至播完，
deadline 從 TTS 結束起算 → 顧客拿到完整 6s budget。
"""

import asyncio
import hashlib
import os
import subprocess
import threading
import time

import edge_tts  # fail-fast：缺套件直接 ImportError；S2+ demo 環境是 Pi，必須有

from myProgram.queue_worker import QueueWorker

# 語音 echo 模式（env 旗標）：SALES_VOICE=1 顯示終端機器人 echo（demo 預設隱藏 —
# 跟 web 鏡像 + 實體機器人重複是雜訊；偶爾 debug 才開），預設 0 = 隱藏。錯誤 ⚠️ 與
# 導航不受此旗標影響恆顯示。各模組各自讀（沿用 STT_TTS_TIMING precedent，不新增跨
# 模組 import）；只 gate echo print。
_VOICE = bool(int(os.environ.get("SALES_VOICE", "0")))

VOICE = "zh-TW-HsiaoChenNeural"  # 台灣女聲
# perf_w5：內容定址快取目錄——package-anchored（非 cwd 依賴），Pi 上隨 git pull 取得
# 預熱資產；執行期合成的動態句也存入此處自我增長（重啟後仍有效，SD 卡非 tmpfs）。
# 模組變數＝測試 seam（monkeypatch 指到 tmp_path）。
_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_cache")

# mpg123 退出時 ALSA buffer 仍可能有未播完的尾巴音訊（~200-400ms）。下一個 speak
# 立刻啟動新 mpg123 開 ALSA device 會把舊 buffer 沖掉，造成上一句末尾被截斷。
# 故在 Popen.wait() 成功 return 後加此 drain 等待。0.3s 是 Pi 上經驗值，
# 短句子尾巴 (~200ms) + 安全餘裕 (~100ms)。
ALSA_DRAIN_SEC: float = 0.3

# 語速分段（2026-05-28 加）— 依 voice constants 字數分佈三段式：
#   短句 (≤ 13 字)  → +3%   例：「付款成功」「謝謝光臨，歡迎再來」
#   中句 (14-22 字) → +6%   例：「您好，請問需要購買什麼東西嗎？」「好的，已加入購物車，請問還有額外需要購買的嗎？」
#   長句 (≥ 23 字)  → +12%  例：「不好意思我聽不太懂，請問要買什麼呢？或者您想聯繫客服？」
# edge-tts rate 格式：`[+-]\d+%` 必帶正負號 + 只能整數（client regex 強制）。Azure
# 服務端有效範圍 -50% ~ +100%（0.5x ~ 2x）。
# 字數用 `len(text)` 算，中文每字 1 code point；含標點（標點 ≈ 短停頓 token）。
# Template 字串如 L4_ENTRY_PROMPT_TEMPLATE 在 caller 已 format 過才進來，len() 算實際 spoken length。
RATE_SHORT: str = "+3%"
RATE_MEDIUM: str = "+6%"
RATE_LONG: str = "+12%"
MEDIUM_THRESHOLD: int = 14  # 字數 >= 此值視為中句
LONG_THRESHOLD: int = 23    # 字數 >= 此值視為長句


def _pick_rate(text: str) -> str:
    """依字數選 rate：< 14 短 / 14-22 中 / >= 23 長。"""
    if len(text) >= LONG_THRESHOLD:
        return RATE_LONG
    if len(text) >= MEDIUM_THRESHOLD:
        return RATE_MEDIUM
    return RATE_SHORT


def _cache_path_for(text: str) -> str:
    """內容定址：同文字（同 VOICE＋rate）永遠同檔名。任一合成參數改變 → key 變 → 自然失效。"""
    key = f"{VOICE}|{_pick_rate(text)}|{text}".encode("utf-8")
    return os.path.join(_CACHE_DIR, hashlib.sha1(key).hexdigest() + ".mp3")


def _store_into_cache(tmp_path: str, cache_path: str) -> None:
    """tmp → cache 原子搬移（防中斷殘留半寫檔進快取）。tmp 缺失時 no-op——
    測試以不寫檔的 fake _synthesize 注入，此 seam 讓既有 fake 全數免改。"""
    if os.path.exists(tmp_path):
        os.replace(tmp_path, cache_path)


async def _synthesize(text: str, out_path: str) -> None:
    """edge_tts async 合成至 out_path（覆寫）；rate 依字數三段式（見 _pick_rate）。"""
    await edge_tts.Communicate(text=text, voice=VOICE, rate=_pick_rate(text)).save(out_path)


def _print_failure(stage: str, detail_lines: list) -> None:
    """TTS 失敗訊息統一印製（synth / play 兩階段共用；字面與舊版逐行一致）。

    detail_lines 每行自帶「key = value」格式，由 caller 依舊版順序排列
    （play FileNotFoundError 的 text 在 hint 前；CalledProcessError 的 cmd 在 text 前）。
    """
    print(f"[語音] ⚠️ TTS 失敗（階段={stage}）")
    for line in detail_lines:
        print(f"[語音]   {line}")
    print(f"[語音] 此字略過，繼續下一字")


def _timing(msg: str) -> None:
    """STT_TTS_TIMING 設了才印計時行（量測用，預設靜默；可隨時移除）。
    與 stt.py 同名 helper 各自內聯——兩模組無共享依賴，2 行不抽 util（YAGNI）。"""
    if os.environ.get("STT_TTS_TIMING"):
        print(f"[語音][計時] {msg}")


class TtsWorker(QueueWorker):
    """同步 TTS daemon worker：FIFO queue + lock-protected current Popen。

    主線程 say(text) 立即返回；worker 從 queue 依序取 text → synth → play。
    程式退出時 shutdown() terminate 當前 mpg123 + 清空 queue。

    Thread model（依 [[threading-conventions]] 推薦：blocking 任務全推背景）：
        - 主線程：呼叫 say(text)（非阻塞 put queue）+ shutdown()（cleanup）
        - 背景 daemon thread：依序消費 queue（同步 synth + play）

    骨架（FIFO queue + daemon thread + get→_process→on_done 迴圈）在 QueueWorker
    基底；本子類別覆寫 _process（synth+play）+ on_done（dec _pending + notify），
    並另持 _pending/_cv 計數（wait_idle 用）與 _proc/_lock（subprocess 中斷用）。

    Lock 保護範圍：`self._proc`（worker 寫、main read+terminate 之間 race window）。
    Lock **不**包 `_proc.wait()` — wait 會 block 2-5s,期間 shutdown 拿不到 lock
    就 defeat 了 shutdown 的目的。改在 spawn / 清 None 兩個短瞬間獨立加 lock。
    """

    thread_name = "TtsWorker"

    def __init__(self) -> None:
        # ⚠️ 欄位先設、super().__init__() 後呼叫：基底 __init__ 立即啟動 daemon
        # thread，thread 第一時間（on_done）即可能觸碰 _cv / _pending。
        self._proc: "subprocess.Popen | None" = None
        self._lock = threading.Lock()  # 既有 _proc 保護 — 不動
        # Condition + _pending counter 同步 say + worker on_done + wait_idle。
        # _active bool 設計曾有 R1 race window：
        #   worker:  text = q.get()      # 此瞬間 q.empty()=True 但 _active 仍 False
        #   main:    wait_idle()          # q.empty() && !_active → 誤判 idle 立即返回
        #   worker:  _active = True       # 太晚
        # fix：say() 原子 inc _pending + put queue，worker on_done dec _pending。
        # q.get() 後 _pending 仍 > 0，wait_idle 阻塞至 worker 真完成才返回。
        self._cv = threading.Condition()
        self._pending = 0  # queued + processing 的 text 數量（say inc / worker on_done dec）
        # perf_w2 F-4／w5：1-deep prefetch 標記（僅 worker thread 觸碰，不需鎖）
        self._prefetched: "tuple[str, str] | None" = None      # (text, cache_path)
        # 基底建 _q + 啟動 daemon thread（daemon=True：主程式退出時自動 die，不會
        # 卡住整個程序退出；但 daemon die 不會自動 terminate 當前 mpg123 子程序 →
        # 仍需顯式 shutdown()）。
        super().__init__()

    def on_thread_start(self) -> None:
        # perf_w2 F-5：worker thread 常駐 event loop（取代每句 asyncio.run 建拆）。
        # 顯式 new_event_loop（worker thread 無預設 loop，get_event_loop 會炸——
        # threading reference Part A 地雷區）；set_event_loop 讓 edge-tts 內部
        # get_event_loop 類呼叫也拿到同一顆。
        # 不在 shutdown close：daemon thread 與 loop 同壽命，main.py 以 os._exit(0)
        # 強退（S6 教訓 3/4），跨 thread close 反引入 race。
        self._loop_obj = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop_obj)
        # perf_w5：快取目錄就緒（冪等；Pi 上通常已隨 git pull 存在）
        os.makedirs(_CACHE_DIR, exist_ok=True)

    def _peek_next(self) -> "str | None":
        """偷看 queue 下一筆（不取出）。安全性：本 thread 是唯一消費者（唯一會移除
        元素的人），producer 並發 put 只 append 尾端 → mutex 下讀 queue[0] 穩定。"""
        with self._q.mutex:
            return self._q.queue[0] if self._q.queue else None

    def say(self, text: str) -> None:
        """非阻塞 producer：原子 inc _pending + put queue。FIFO 順序消費（不中斷）。

        2026-05-30 v2：inc _pending 必須跟 put 同臨界區（持 _cv），避免 R1 race —
        若先 put 後 inc，worker 可能在中間 get text 並開始處理，_pending 看似為 0
        被 wait_idle 誤判 idle。先 inc 再 put 保證 _pending 永遠 >= queue 內未消費數。

        預設不中斷：text 入 queue 排隊；當前播放完才播下一段。中斷邏輯
        （新任務覆蓋舊）是 S7 的選擇性升級，S4 不做。
        """
        with self._cv:
            self._pending += 1
            self._q.put(text)

    def on_done(self, text: str) -> None:
        """基底 _loop finally 回調：dec _pending + 歸 0 時 notify_all（無論成功 / 失敗）。

        基底 _loop 以 try/finally 包 _process，無論成功 / 失敗 path 都呼叫 on_done →
        dec _pending + notify_all，防止 wait_idle 永久阻塞。
        """
        with self._cv:
            self._pending -= 1
            if self._pending == 0:
                self._cv.notify_all()

    def _process(self, text: str) -> None:
        """處理單一 text：synth（或 prefetch 命中）→ play＋預取下一句 → drain。

        本函式是 single-iteration body（基底 _loop 每輪 get 一筆即呼叫一次），失敗
        分支用 return 結束 — 基底 _loop 的 try/finally 才負責 on_done（_pending
        dec + notify_all）+ 下一輪 get。

        perf_w2 F-4／w5：播放等待期間（Popen 後、wait() 前）確保 queue 下一句已在
        內容定址快取——句間靜默從一次 synth round-trip 降到接近 0。單 thread 內重疊，
        零新鎖、零新 race 面（_prefetched 只被本 thread 觸碰；各句快取檔名互異）。
        """
        # 階段 1：取得 mp3——prefetch 標記 → 內容定址快取 → 現場合成（三層 fallback）
        cache_path = _cache_path_for(text)
        _synth_ms = 0.0  # 計時 log 用；僅現場合成分支量測（prefetch / cache 命中為 0）
        if self._prefetched is not None and self._prefetched[0] == text:
            source = "prefetch"
            mp3_path = self._prefetched[1]
            self._prefetched = None
        elif os.path.exists(cache_path):
            # perf_w5：快取命中——零合成零網路（固定文案預熱後 demo 斷網也能播）
            source = "cache"
            self._prefetched = None
            mp3_path = cache_path
        else:
            source = "synth"
            # 防禦：FIFO 單消費者下 prefetch 內容必等於下一句，mismatch 理論不可達；
            # 若出現（未來改動引入）丟棄重合成即可，行為仍正確
            self._prefetched = None
            tmp_path = cache_path + ".tmp"
            try:
                _synth_t0 = time.monotonic()
                self._loop_obj.run_until_complete(_synthesize(text, tmp_path))
                _synth_ms = (time.monotonic() - _synth_t0) * 1000
            except Exception as e:
                # edge_tts 可能 raise NoAudioReceived / WebSocketException / asyncio 相關錯
                # 不確定具體類型 → 統一 catch Exception，但訊息要詳細
                _print_failure("synth", [
                    f"exception = {type(e).__name__}: {e!r}",
                    f"text      = {text!r}",
                ])
                return
            # 原子入快取（執行期自我增長：動態句首播後永久免合成）
            _store_into_cache(tmp_path, cache_path)
            mp3_path = cache_path

        # 階段 2：播放 mp3（subprocess.Popen → 保留 reference 給 shutdown 用）
        # 對比 S2 同步版用 subprocess.run：S4 改 Popen + wait 兩段是為了讓
        # shutdown() 可在播放期間呼叫 _proc.terminate()。
        #
        # stdin=DEVNULL（commit f7dab09 加，S2 Pi 實機踩坑）：mpg123 預設讀父
        # 程序 stdin 接收 control characters（q/s/p/+/- 等）。不設 DEVNULL 時：
        #   1. 播放期間 user 在 dialog 打的字會被 mpg123 偷走 → 無法進
        #      Python input() → 顧客以為打了字結果機器人沒反應
        #   2. user 不小心打到 'q' / 's' → mpg123「Stopped.」+ quit 退出碼非 0
        #      → CalledProcessError → 整段 dialog flow 中斷
        # mpg123 從 mp3 路徑參數讀資料、不從 stdin 讀資料 → DEVNULL 不影響播放。
        #
        # finally 統一清 _proc（取代原 3 except + 成功路徑共 4 處重複）：
        # 成功 = try 正常結束 → finally 清 → drain；失敗 = except 印完 → finally 清
        # → return 生效 — 兩種時序皆與舊版「印完才清 / 清完才 drain」一致。
        try:
            with self._lock:
                # 短臨界區：spawn + 存 ref，不包 wait（避免 shutdown 拿不到 lock）
                self._proc = subprocess.Popen(
                    ["mpg123", "-q", mp3_path],
                    stdin=subprocess.DEVNULL,
                )
            # 階段 2.5（perf_w2 F-4／perf_w5 快取版）：播放等待前確保下一句已在快取
            # ——本 thread 反正要阻塞等播放，把閒置時間拿來 synth；內容定址檔名
            # 各句互異，不存在互踩。
            nxt = self._peek_next()
            if nxt is not None:
                nxt_cache = _cache_path_for(nxt)
                if os.path.exists(nxt_cache):
                    self._prefetched = (nxt, nxt_cache)   # 已在快取＝瞬時預取
                else:
                    nxt_tmp = nxt_cache + ".tmp"
                    try:
                        self._loop_obj.run_until_complete(_synthesize(nxt, nxt_tmp))
                        _store_into_cache(nxt_tmp, nxt_cache)
                        self._prefetched = (nxt, nxt_cache)
                    except Exception:
                        self._prefetched = None
                        # 預取失敗刻意靜默：該句輪到自己的 _process 會重試 synth，
                        # 屆時才走既有 noisy 失敗 path——避免同一句印兩次失敗訊息
            # 等播完（不持 lock — shutdown 可在此期間 terminate）。terminate
            # 觸發時 wait 返回非 0 returncode（Linux 上 SIGTERM 是 -15）。
            _play_t0 = time.monotonic()
            returncode = self._proc.wait()
            _play_ms = (time.monotonic() - _play_t0) * 1000
            if returncode != 0:
                # check=True 等效手寫：模擬 subprocess.CalledProcessError 行為。
                # 走 except 分支印 noisy 訊息（shutdown 觸發的 SIGTERM 也會走這
                # path，returncode 負值代表被 signal 中斷 — 是 expected exit
                # 但仍印訊息，方便 SSH log 看到「程式退出時殺掉了播放中的 X」）。
                raise subprocess.CalledProcessError(
                    returncode=returncode,
                    cmd=["mpg123", "-q", mp3_path],
                )
        except FileNotFoundError as e:
            # mpg123 binary 不存在（Pi 未 apt install mpg123）
            _print_failure("play", [
                f"exception = FileNotFoundError: {e!r}",
                f"text      = {text!r}",
                f"hint      = 請在 Pi 上執行 `sudo apt install mpg123`",
            ])
            return
        except subprocess.CalledProcessError as e:
            # mpg123 退出碼非 0（檔案損毀 / 音訊裝置忙 / shutdown SIGTERM 等）
            _print_failure("play", [
                f"exception = subprocess.CalledProcessError: returncode={e.returncode}",
                f"cmd       = {e.cmd}",
                f"text      = {text!r}",
            ])
            return
        except Exception as e:
            # 兜底 — 不明錯誤也要詳細印
            _print_failure("play", [
                f"exception = {type(e).__name__}: {e!r}",
                f"text      = {text!r}",
            ])
            return
        finally:
            with self._lock:
                self._proc = None

        # 播放成功（returncode==0）：僅在 queue 還有下一句要播時 drain ALSA。
        # drain 防的是「下一個 mpg123 開同一播放裝置沖掉舊 buffer 截尾」；worker 即將
        # idle（_peek_next 為 None）→ 無下一個 mpg123 → 跳過 drain，省 turn boundary
        # ~0.3s（playback→listen 轉場；喇叭=板載、麥=USB 不同裝置，arecord 開 capture
        # 不會沖播放 buffer，尾巴自然播完）。連發句之間照舊 drain（防截尾，行為不變）。
        # 失敗 path 不到這裡因 mpg123 沒真播完 = 無 buffer 殘留 = 不需 drain。
        drained = self._peek_next() is not None
        if drained:
            time.sleep(ALSA_DRAIN_SEC)
        _timing(f"{text!r} 來源={source} play={_play_ms:.0f}ms"
                + (f" synth={_synth_ms:.0f}ms" if source == "synth" else "")
                + f" drain={'on' if drained else 'off'}")

    def wait_idle(self, max_wait: float = 30.0) -> bool:
        """阻塞至 _pending=0（worker FIFO 全跑完）或 max_wait 超時。

        2026-05-30 v2 加 — 給 wall-clock budget pattern caller 用：
            speak_and_wait(prompt)  # say + wait_idle 連續
            deadline = monotonic + 6  # 從 TTS 播完起算，不被 synth/play 時間吃掉

        Args:
            max_wait: 上限秒數（預設 30s — 2026-05-30 從 10s bump，Pi 實測 hawk
                slogan + L2 entry back-to-back 兩條合計 ~12-15s 超過 10s。30s 容忍
                正常 back-to-back queue 兩條 + synth round-trip，仍是異常偵測防線）
                v1 reverted 設計用無 timeout `cv.wait()` 永久阻塞，當 edge_tts
                synth 卡網路 / mpg123 hang 時整個 dialogue flow 卡死 — 毀 L4
                wall-clock budget 訴求（P0 bug）。max_wait fallback 強制 return False
                讓 caller 仍能 continue（雖然 TTS 沒播完，但 dialog 不卡）。

        Returns:
            True  — _pending 真的歸 0（TTS 已全部播完）
            False — max_wait timeout（synth / play 異常未播完，極異常但不卡死 caller）
        """
        with self._cv:
            deadline = time.monotonic() + max_wait
            while self._pending > 0:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    # 警示：極異常 fallback，正常 TTS 不應到這裡
                    print(f"[語音] ⚠️ wait_idle 超過 max_wait={max_wait}s，TTS 異常未播完，繼續流程")
                    return False
                self._cv.wait(timeout=remaining)
            return True

    def is_idle(self) -> bool:
        """非阻塞查詢 worker 是否閒置（_pending == 0），立即返回不等待。

        給 L1 hawk polling loop 用：hawk 不可呼叫阻塞的 wait_idle（max_wait=30s 與
        0.1s polling cadence 衝突會卡死 hawk loop（輪播停、't' 收不到）），但叫賣輪播需「上一句
        播完才起算間距」→ 用本方法非阻塞瞬讀。只在 _cv mutex 下讀一個 int，
        不 wait、立即返回。_pending==0 ⟺ 當前所有句 synth+play+drain 全完成。
        """
        with self._cv:
            return self._pending == 0

    def shutdown(self) -> None:
        """程式退出 cleanup：terminate 當前 mpg123 + 清空 queue。

        Thread-safe：用 self._lock 保護 _proc 讀取 + terminate 呼叫，避免跟
        worker thread 設 _proc 之間 race。

        Terminate 後 worker 的 _proc.wait() 會返回非 0 returncode → 走
        CalledProcessError 分支 noisy print continue。daemon thread 隨主程式
        退出自動 die，不需 join。

        清空 queue：避免 daemon die 前還消費剩餘任務（雖然 daemon 主退出時
        會被 runtime 清掉，但 drain 一下更乾淨）。
        """
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                # poll() is None = 還在跑（未退出）；用 terminate 發 SIGTERM
                try:
                    self._proc.terminate()
                except OSError:
                    # 子程序剛好同時自然結束 → terminate 對已退出 proc 在某些
                    # 平台 raise OSError（Linux 通常 silent）。安全 swallow。
                    pass
            # 清 queue：把剩餘任務全丟掉（共用 drain_queue helper，原手寫迴圈收基底）
            self.drain()


# Module-level singleton：import 時自動啟動 daemon thread。
# 使用者多次 `from myProgram import tts` 不會重複建（Python module cache）。
_worker = TtsWorker()


def speak(text: str) -> None:
    """對外 API：非阻塞 TTS（入 queue 立即返回）。

    `print(f"[語音] {text}")` 在 **caller thread** 立即印 — 不放到 worker
    內 — 是為了保持 SSH log 時序跟 dialog flow 一致（user 看到「[語音] xxx」
    緊接著「[商家] >」prompt，不會因 worker 延遲導致 log 亂序）。

    對比 S2 同步版：對外 signature 完全相容（接 text、回 None），但行為從
    「阻塞至播完」改為「立即返回（背景排隊播）」。
    """
    if _VOICE:
        print(f"[語音] {text}")
    _worker.say(text)


def speak_and_wait(text: str, max_wait: float = 30.0) -> bool:
    """同步阻塞 speak — say + wait_idle 連續 call。2026-05-30 v2 加。

    給 wall-clock budget pattern caller 用（_cancel_confirm / DialogSession.c2_second_stage()
    / l4 entry）：先讓 TTS 完整播完，再算 deadline = monotonic + N → 顧客拿到
    完整 N 秒 budget，而非「N 秒減 TTS 播放時間」。

    Args:
        text: 要 speak 的文字
        max_wait: wait_idle 上限秒數（預設 30s — 見 TtsWorker.wait_idle docstring）

    Returns:
        True if TTS 完整播完；False if max_wait timeout（caller 仍 continue 不卡）
    """
    speak(text)
    return _worker.wait_idle(max_wait=max_wait)


def wait_idle(max_wait: float = 30.0) -> bool:
    """對外 API：阻塞至 TtsWorker 完全閒置（_pending=0）或 max_wait 超時。

    使用情境：caller 需要「上一段 speak 已播完」的保證 — e.g. 計算 wall-clock
    deadline 前確保 TTS 不還在隊列裡。
    """
    return _worker.wait_idle(max_wait=max_wait)


def is_idle() -> bool:
    """對外 API：非阻塞查詢 TTS 是否已播完當前所有句（_pending==0）。

    使用情境：L1 hawk polling loop「上一句播完才起算 HAWK_INTERVAL 間距」用。
    非阻塞瞬讀，不像 wait_idle 會阻塞等播完。
    """
    return _worker.is_idle()


def shutdown() -> None:
    """對外 API：terminate 當前播放 + 清空 queue（main.py exit 時呼叫）。

    使用情境：main() 的 finally block 內呼叫，確保程式退出時最後一段
    mpg123 不會繼續播完才停（S4 解 user 訴求 #3）。
    """
    _worker.shutdown()
