"""S4 非阻塞 TTS 模組 — daemon worker thread + FIFO queue + shutdown cleanup。

S4 範圍（incremental-rebuild 第 4 步）：
    - 對外 API 不變：`speak(text)` 仍是 module-level 函式，signature 相容 S2
    - 新增 `shutdown()`：程式退出時 terminate 當前播放中的 mpg123 + 清空 queue
    - 改造重點：caller thread 立即返回（不阻塞），實際 synth + 播放在背景 daemon
      thread 內 FIFO 順序消費

S4 動機（S2 同步阻塞實機踩到的問題）：
    1. L1 hawk speak 期間商家按 q 想退出 → 主線程被 mpg123.wait() 卡死、input()
       沒在跑、q 只能存 stdin buffer 等 speak 播完才響應（3-5s 延遲）
    2. 主線程被阻塞時 opencv 也無法 poll（為 S6 真 opencv 偵測鋪路）
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
"""

import asyncio
import queue
import subprocess
import threading
import time

import edge_tts  # fail-fast：缺套件直接 ImportError；S2+ demo 環境是 Pi，必須有

VOICE = "zh-TW-HsiaoChenNeural"  # 台灣女聲
TMP_MP3 = "/tmp/last_tts.mp3"  # Linux 絕對路徑（path-conventions 規範）

# mpg123 退出時 ALSA buffer 仍可能有未播完的尾巴音訊（~200-400ms）。下一個 speak
# 立刻啟動新 mpg123 開 ALSA device 會把舊 buffer 沖掉,造成上一句末尾被截斷。
# 故在 Popen.wait() 成功 return 後加此 drain 等待。0.3s 是 Pi 上經驗值,
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


async def _synthesize(text: str, out_path: str) -> None:
    """edge_tts async 合成至 out_path（覆寫）；rate 依字數三段式（見 _pick_rate）。"""
    await edge_tts.Communicate(text=text, voice=VOICE, rate=_pick_rate(text)).save(out_path)


class TtsWorker:
    """同步 TTS daemon worker：FIFO queue + lock-protected current Popen。

    主線程 say(text) 立即返回；worker 從 queue 依序取 text → synth → play。
    程式退出時 shutdown() terminate 當前 mpg123 + 清空 queue。

    Thread model（依 [[threading-conventions]] 推薦：blocking 任務全推背景）：
        - 主線程：呼叫 say(text)（非阻塞 put queue）+ shutdown()（cleanup）
        - 背景 daemon thread：跑 _loop() 依序消費 queue（同步 synth + play）

    Lock 保護範圍：`self._proc`（worker 寫、main read+terminate 之間 race window）。
    Lock **不**包 `_proc.wait()` — wait 會 block 2-5s,期間 shutdown 拿不到 lock
    就 defeat 了 shutdown 的目的。改在 spawn / 清 None 兩個短瞬間獨立加 lock。
    """

    def __init__(self) -> None:
        # type hint 用 queue.Queue[str]：Python 3.9+ 支援 generic alias（Pi 是 3.7
        # 但 string annotation 不會 runtime evaluate，OK）
        self._q: "queue.Queue[str]" = queue.Queue()
        self._proc: "subprocess.Popen | None" = None
        # _active：True 表示 worker 正在處理一個 text（synth/play/drain 全週期內）。
        # 2026-05-30 加 — 跟 _proc 區別：_proc 只 cover play 階段，_active 涵蓋整輪
        # 處理（含 synth 網路 call + drain sleep）。給 wait_idle() 用，讓 caller 真正
        # 等到「TTS 完全空閒」才開始倒數 timeout（避免顧客還在聽 prompt 就被扣秒）。
        self._active = False
        self._lock = threading.Lock()
        # daemon=True：主程式退出時這個 thread 自動 die（不會卡住整個程序退出）
        # 但 daemon die 不會自動 terminate 當前 mpg123 子程序 → 仍需顯式 shutdown()
        threading.Thread(target=self._loop, name="TtsWorker", daemon=True).start()

    def say(self, text: str) -> None:
        """非阻塞 producer：text 入 queue 立即 return。FIFO 順序消費（不中斷）。

        預設不中斷：text 入 queue 排隊;當前播放完才播下一段。中斷邏輯
        （新任務覆蓋舊）是 S7 的選擇性升級,S4 不做。
        """
        self._q.put(text)

    def _loop(self) -> None:
        """Daemon worker：get text → synth → play → drain → 下一輪（無限迴圈）。

        queue 空就 block 在 self._q.get() 等待新任務。daemon=True 主程式退出時
        自動死亡（即使 thread 卡在 get() 也會被 Python runtime 清掉）。
        """
        while True:
            # blocking get：queue 空就等到有任務（無 timeout，等到天荒地老）
            text = self._q.get()
            # 標記 active — try/finally 確保 synth / play / drain / 任何 exception
            # 路徑後都會 reset 為 False（給 wait_idle 用）。
            with self._lock:
                self._active = True
            try:
                self._process_text(text)
            finally:
                with self._lock:
                    self._active = False

    def _process_text(self, text: str) -> None:
        """處理單一 text：synth → play → drain（封裝以便 _loop 用 try/finally 包 _active）。

        Note: 早 return 取代既有 `continue`（單一 text 的失敗 path）— 由 `_loop`
        的 while-true + try/finally 負責進下一輪 + reset _active。
        """
        # 階段 1：合成 mp3
        try:
            asyncio.run(_synthesize(text, TMP_MP3))
        except Exception as e:
            # edge_tts 可能 raise NoAudioReceived / WebSocketException / asyncio 相關錯
            # 不確定具體類型 → 統一 catch Exception，但訊息要詳細
            print(f"[語音] ⚠️ TTS 失敗（階段=synth）")
            print(f"[語音]   exception = {type(e).__name__}: {e!r}")
            print(f"[語音]   text      = {text!r}")
            print(f"[語音] 此字略過,繼續下一字")
            return  # 早 return 取代既有 continue

        # 階段 2：播放 mp3（subprocess.Popen → 保留 reference 給 shutdown 用）
        # 對比 S2 同步版用 subprocess.run：S4 改 Popen + wait 兩段是為了讓
        # shutdown() 可在播放期間呼叫 _proc.terminate()。
        #
        # stdin=DEVNULL（commit f7dab09 加,S2 Pi 實機踩坑）：mpg123 預設讀父
        # 程序 stdin 接收 control characters（q/s/p/+/- 等）。不設 DEVNULL 時：
        #   1. 播放期間 user 在 dialog 打的字會被 mpg123 偷走 → 無法進
        #      Python input() → 顧客以為打了字結果機器人沒反應
        #   2. user 不小心打到 'q' / 's' → mpg123「Stopped.」+ quit 退出碼非 0
        #      → CalledProcessError → 整段 dialog flow 中斷
        # mpg123 從 mp3 路徑參數讀資料、不從 stdin 讀資料 → DEVNULL 不影響播放。
        try:
            with self._lock:
                # 短臨界區：spawn + 存 ref，不包 wait（避免 shutdown 拿不到 lock）
                self._proc = subprocess.Popen(
                    ["mpg123", "-q", TMP_MP3],
                    stdin=subprocess.DEVNULL,
                )
            # 等播完（不持 lock — shutdown 可在此期間 terminate）。terminate
            # 觸發時 wait 返回非 0 returncode（Linux 上 SIGTERM 是 -15）。
            returncode = self._proc.wait()
            if returncode != 0:
                # check=True 等效手寫：模擬 subprocess.CalledProcessError 行為。
                # 走 except 分支印 noisy 訊息（shutdown 觸發的 SIGTERM 也會走這
                # path，returncode 負值代表被 signal 中斷 — 是 expected exit
                # 但仍印訊息，方便 SSH log 看到「程式退出時殺掉了播放中的 X」）。
                raise subprocess.CalledProcessError(
                    returncode=returncode,
                    cmd=["mpg123", "-q", TMP_MP3],
                )
        except FileNotFoundError as e:
            # mpg123 binary 不存在（Pi 未 apt install mpg123）
            print(f"[語音] ⚠️ TTS 失敗（階段=play）")
            print(f"[語音]   exception = FileNotFoundError: {e!r}")
            print(f"[語音]   text      = {text!r}")
            print(f"[語音]   hint      = 請在 Pi 上執行 `sudo apt install mpg123`")
            print(f"[語音] 此字略過,繼續下一字")
            with self._lock:
                self._proc = None
            return
        except subprocess.CalledProcessError as e:
            # mpg123 退出碼非 0（檔案損毀 / 音訊裝置忙 / shutdown SIGTERM 等）
            print(f"[語音] ⚠️ TTS 失敗（階段=play）")
            print(f"[語音]   exception = subprocess.CalledProcessError: returncode={e.returncode}")
            print(f"[語音]   cmd       = {e.cmd}")
            print(f"[語音]   text      = {text!r}")
            print(f"[語音] 此字略過,繼續下一字")
            with self._lock:
                self._proc = None
            return
        except Exception as e:
            # 兜底 — 不明錯誤也要詳細印
            print(f"[語音] ⚠️ TTS 失敗（階段=play）")
            print(f"[語音]   exception = {type(e).__name__}: {e!r}")
            print(f"[語音]   text      = {text!r}")
            print(f"[語音] 此字略過,繼續下一字")
            with self._lock:
                self._proc = None
            return

        # 播放成功（returncode==0）：清 _proc + drain ALSA
        with self._lock:
            self._proc = None
        # 給 ALSA buffer 完成尾巴音訊播放的時間,避免下一個 speak() 立刻啟動
        # 新 mpg123 沖掉舊 buffer（症狀：「付款成功」尾巴被截）。失敗 path
        # 不到這裡因 mpg123 沒真播完 = 無 buffer 殘留 = 不需 drain。
        time.sleep(ALSA_DRAIN_SEC)

    def wait_idle(self, poll_interval: float = 0.05) -> None:
        """阻塞至 worker 完全閒置（queue 空 + 無正在處理的 text）。

        2026-05-30 加 — 解 user Pi demo UX bug：原本 `read_customer_input(timeout=N)`
        在 `speak(text)` 入 queue 後立即倒數，timeout 會「吃掉」顧客還在聽 prompt
        的時間。caller 改先呼叫此函式，等到 TTS 真正播完才開始倒數。

        判斷條件：`self._q.empty()` AND NOT `self._active`。
            - `_active` 涵蓋整個處理週期（synth/play/drain），由 `_loop` 的
              try/finally 嚴格守護，避免 synth 階段 `_proc` 還沒設值時 wait_idle
              誤判 idle 的 race window。
            - `_q.empty()` 補抓「下一個任務已入 queue 但 worker 還沒 get」短瞬間。

        Polling 50ms（poll_interval）—  Pi 上人類聽覺對 50ms 不敏感（一般延遲門檻
        ~200ms），不影響 UX。比 threading.Event 簡單，避免 set/clear race。

        Args:
            poll_interval: polling 間隔（秒），預設 0.05。
        """
        while True:
            with self._lock:
                still_active = self._active
            if self._q.empty() and not still_active:
                return
            time.sleep(poll_interval)

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
            # 清 queue：把剩餘任務全丟掉
            while not self._q.empty():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break


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
    print(f"[語音] {text}")
    _worker.say(text)


def wait_idle() -> None:
    """對外 API：阻塞至 TTS 完全閒置（queue 空 + 無播放中的 text）。

    使用情境：caller 在 `read_customer_input(timeout=N)` 前呼叫，確保 timeout
    從 TTS 播完瞬間開始倒數，而非從 speak() 入 queue 瞬間（避免顧客還在聽
    prompt 就被扣秒）。詳見 TtsWorker.wait_idle docstring。
    """
    _worker.wait_idle()


def shutdown() -> None:
    """對外 API：terminate 當前播放 + 清空 queue（main.py exit 時呼叫）。

    使用情境：main() 的 finally block 內呼叫，確保程式退出時最後一段
    mpg123 不會繼續播完才停（S4 解 user 訴求 #3）。
    """
    _worker.shutdown()
