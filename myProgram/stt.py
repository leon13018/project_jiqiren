"""STT worker — Deepgram Nova-3 串流語音辨識（Phase 1：播完才聽）。

對應 spec：resources/specs/stt_p1_2026-06-12_spec.md
（統領設計 resources/specs/stt_bargein_2026-06-12_design.md）。

架構（第四個 worker；producer 形狀，與 input_reader 同類）：
    - 無常駐 thread：arm() 起 session（sender + receiver 兩條 daemon thread），
      disarm() 終止。與 tts.py 常駐 asyncio loop 不同——Deepgram 用 websockets
      同步 client（v12+），全程無 asyncio（asyncio-in-thread 地雷區整個避開）。
    - 音源：arecord subprocess（ReSpeaker 為標準 USB 音訊裝置；與 mpg123 播放
      subprocess 同 idiom，零編譯依賴）。
    - 輸出：speech_final 的 transcript 去頭尾標點 → sink（input_reader.inject）
      → 與鍵盤共用單一 input queue（producer 端零分流；read_customer_input 內
      既有 normalize_input 統一做全形數字等正規化，本模組不重複）。

Windows 紅線：頂層**禁止** import websockets（本機不裝依賴）；該 import 收在
_default_ws_factory 內 lazy 執行（Pi-only 路徑），測試一律注入 fake factory。
"""

import json
import os
import subprocess
import threading
import time
from urllib.parse import quote

# 去頭尾用標點集（中英常見 + 空白）；句中標點保留——只防 strict-short 比對
# （「好。」≠「好」）與字首雜訊，語意內容不動。
_PUNCT = "。，、！？；：．,!?;: \t\r\n"


def _normalize_transcript(text: str) -> str:
    """去頭尾標點與空白（句中不動）；全標點輸入歸空字串（caller 不注入）。"""
    return text.strip(_PUNCT)


def _timing(msg: str) -> None:
    """STT_TTS_TIMING 設了才印計時行（量測用，預設靜默；可隨時移除）。"""
    if os.environ.get("STT_TTS_TIMING"):
        print(f"[計時] {msg}")


# Keyterm prompting 詞表（Nova-3 contextual biasing）——點餐場景高頻詞，引導模型
# 在近音模糊時偏向「清單內」的詞。解「三瓶」誤辨識為「商品」：sān-píng / shāng-pǐn
# 平翹舌＋前後鼻音雙重混淆，而「商品」不在清單、「三瓶」在 → 模型偏向正確輸出。
# 純連線參數、inference 內偏置，零額外延遲（非事後糾錯階段）。約 29 詞，遠低於
# Deepgram 500 token 上限。數量用中文數字（顧客口語＋既有 NLU 吃中文數字）。
KEYTERMS = [
    "一瓶", "兩瓶", "三瓶", "四瓶", "五瓶", "六瓶", "七瓶", "八瓶", "九瓶", "十瓶",
    "一張", "兩張", "三張", "四張", "五張", "六張", "七張", "八張", "九張", "十張",
    "冰紅茶", "紅茶", "刮刮樂",
    "結帳", "取消", "繼續", "繼續選購", "幾瓶", "幾張",
]

# endpointing 毫秒：env 旋鈕（未設 = 300，與原硬編逐字元相同）。Pi 設
# STT_ENDPOINTING_MS=200 可 A/B「顧客講完 → speech_final」速度，不動碼。
_ENDPOINTING_MS = int(os.environ.get("STT_ENDPOINTING_MS", "300"))


def _build_deepgram_url(endpointing_ms: int) -> str:
    """組 Deepgram 串流 URL；endpointing 由參數帶入，其餘參數固定。keyterm 在固定
    參數後 append（percent-encoded）。統領設計 §2.5 既定參數；Pi 首測若 handshake
    400 → 改試 language=zh-Hant 並回寫 spec §2.3。"""
    return (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-3&language=zh-TW&encoding=linear16&sample_rate=16000"
        f"&channels=1&interim_results=true&endpointing={endpointing_ms}&smart_format=false"
        + "".join(f"&keyterm={quote(_kt)}" for _kt in KEYTERMS)
    )


DEEPGRAM_URL = _build_deepgram_url(_ENDPOINTING_MS)
CHUNK_BYTES = 3200  # 100ms @ 16kHz 16-bit mono——粒度夠細不增 ws 訊息開銷

_KEEPALIVE_INTERVAL: float = 5.0  # 秒；< Deepgram 10s idle timeout（NET-0001）。測試可 monkeypatch 縮短
_KEEPALIVE_MSG = json.dumps({"type": "KeepAlive"})
_FINALIZE_MSG = json.dumps({"type": "Finalize"})
_CLOSE_MSG = json.dumps({"type": "CloseStream"})


class SttWorker:
    """Deepgram 串流 worker：整場共用一條持久連線（連線層常駐），每輪只開關 arecord（收音層）。

    Thread model：
        - 連線層（整場常駐）：_ws（持久連線）+ SttReceiver（ws.recv→閘門→sink）
          + SttKeepAlive（idle 時送 KeepAlive 撐住）。lazy 於首次 arm 建線，死則下次
          arm 重連，shutdown 收掉。
        - 收音層（每輪 arm/disarm）：arecord（_audio）+ SttSender（audio.read→ws.send）。
        - _capturing 閘門：receiver 只在收音窗注入，擋上一輪殘響 / Finalize 回覆漏入下一輪。
        - _send_lock 序列化所有 ws.send（音框 / keepalive / finalize / close）——websockets
          sync client 並發 send 非 thread-safe。

    注入 seams（Windows pytest 全 fake）：sink / audio_factory / ws_factory（同前）。
    """

    def __init__(self, sink, api_key=None, audio_factory=None, ws_factory=None):
        self._sink = sink
        self._api_key = api_key
        self._audio_factory = audio_factory or _default_audio_factory
        self._ws_factory = ws_factory or _default_ws_factory
        self._lock = threading.Lock()        # 保護連線層狀態 + capturing 切換
        self._send_lock = threading.Lock()   # 序列化所有 ws.send
        self._connect_lock = threading.Lock()  # 序列化建線（prearm 背景 vs arm 主線程），不與 _lock 同時持有
        # 連線層（整場常駐）
        self._ws = None                      # 持久連線，或 None（未連 / 已死）
        self._conn_stop = None               # Event：停 receiver + keepalive（shutdown）
        self._receiver = None
        self._keepalive = None
        # 收音層（每輪）
        self._audio = None
        self._sender = None
        self._send_stop = None
        # 其他
        self._capturing = False
        self._armed_at = 0.0                 # arm 時記 monotonic（計時 log 用）
        self._disabled = False               # 缺 key / 401 → 本次執行停用（鍵盤照常）

    def is_armed(self) -> bool:
        with self._lock:
            return self._capturing

    def _ensure_connected(self) -> bool:
        """確保持久連線存在：已連則復用（True）。未連則**鎖外**建線（阻塞網路 IO 不持
        _lock，避免凍結 disarm/shutdown）+ 鎖內寫狀態 + 起常駐 receiver/keepalive（含
        「開麥連線」計時）。連線失敗回 False。_connect_lock 序列化 prearm/arm 並發建線。"""
        with self._lock:
            if self._ws is not None:
                return True
        with self._connect_lock:
            with self._lock:
                if self._ws is not None:
                    return True  # 等鎖期間 prearm/另一 arm 已建好 → 復用
            # 鎖外建線（_lock 已釋放）——阻塞 IO 不凍結 disarm/shutdown
            _connect_t0 = time.monotonic()
            ws = self._connect_with_retry()
            if ws is None:
                return False
            _timing(f"開麥連線 {(time.monotonic() - _connect_t0) * 1000:.0f}ms")
            conn_stop = threading.Event()
            receiver = threading.Thread(
                target=self._receive_loop, args=(ws, conn_stop),
                name="SttReceiver", daemon=True)
            keepalive = threading.Thread(
                target=self._keepalive_loop, args=(ws, conn_stop),
                name="SttKeepAlive", daemon=True)
            with self._lock:
                self._ws = ws
                self._conn_stop = conn_stop
                self._receiver = receiver
                self._keepalive = keepalive
            receiver.start()
            keepalive.start()
            return True

    def arm(self) -> None:
        """冪等開麥：已 capturing / 已停用 no-op；缺 key 印一次警告後停用。
        建線在鎖外（不持 _lock，避免凍結 disarm/shutdown）；首輪建線、之後只 spawn
        arecord + sender（若 prearm 已建線則直接復用）。"""
        with self._lock:
            if self._disabled or self._capturing:
                return
            if not self._api_key:
                print("[語音辨識] ⚠️ 未設定 DEEPGRAM_API_KEY，STT 停用（鍵盤輸入照常）")
                self._disabled = True
                return
        # 連線在鎖外（_ensure_connected 內自持 _connect_lock；失敗已印原因）
        if not self._ensure_connected():
            return  # 本輪走鍵盤
        with self._lock:
            if self._capturing:
                return  # 防禦：理論上單 caller 不發生
            audio = self._audio_factory()
            send_stop = threading.Event()
            sender = threading.Thread(
                target=self._send_loop, args=(self._ws, audio, send_stop),
                name="SttSender", daemon=True)
            self._audio = audio
            self._send_stop = send_stop
            self._sender = sender
            self._armed_at = time.monotonic()
            self._capturing = True
            sender.start()

    def _connect_with_retry(self):
        """建線；非 401 失敗重試 1 次；401 → 永久停用（本次執行）。"""
        for attempt in (1, 2):
            try:
                return self._ws_factory(self._api_key)
            except Exception as e:
                if _is_auth_error(e):
                    print("[語音辨識] ⚠️ API key 無效（HTTP 401），本次執行停用 STT")
                    self._disabled = True
                    return None
                if attempt == 1:
                    continue
                print(f"[語音辨識] ⚠️ 連線失敗（{type(e).__name__}: {e!r}），本輪改用鍵盤")
                return None

    def _send_loop(self, ws, audio, send_stop) -> None:
        """audio.read → ws.send（經 _send_lock）；EOF（disarm terminate / 裝置故障）或
        send_stop 即止。首框到達印「開麥→第一個音框」計時。"""
        first = True
        try:
            while not send_stop.is_set():
                chunk = audio.read(CHUNK_BYTES)
                if not chunk:
                    break
                if first:
                    # arm 記的 _armed_at 到第一個音框 ≈ arecord 冷啟動 + 首框填充
                    _timing(f"開麥→第一個音框 {time.monotonic() - self._armed_at:.2f}s（arecord 冷啟動＋首框填充）")
                    first = False
                with self._send_lock:
                    ws.send(chunk)
        except Exception:
            pass  # ws 已關 / 死 → 靜默結束；receiver 負責標記死亡

    def _receive_loop(self, ws, conn_stop) -> None:
        """常駐：ws.recv → JSON → speech_final（**僅 _capturing 才注入**）。
        雙層 try：外層只包 ws.recv（連線層——recv 失敗=連線死→退出重連）；內層包單訊息
        處理（json/格式異常→印警示後 continue，**持久連線存活**）。退出時若非 shutdown
        觸發 → 印警示並標記 _ws 死亡（下次 arm 重連）。"""
        try:
            while not conn_stop.is_set():
                msg = ws.recv()
                try:
                    if isinstance(msg, bytes):
                        continue  # Deepgram Results 皆 text frame；防禦略過
                    data = json.loads(msg)
                    if data.get("type") != "Results" or not data.get("speech_final"):
                        continue
                    if not self._capturing:
                        continue  # 閘門：收音窗外（上一輪殘響 / Finalize 回覆）丟棄
                    alts = data.get("channel", {}).get("alternatives", [])
                    text = _normalize_transcript(alts[0].get("transcript", "")) if alts else ""
                    if text:
                        print(f"[語音辨識] {text}")
                        _timing(f"開麥後 {time.monotonic() - self._armed_at:.2f}s 出辨識結果")
                        self._sink(text)
                except Exception as e:
                    # 單訊息處理失敗（格式不合 / json 壞）→ 略過該則，持久連線存活
                    print(f"[語音辨識] ⚠️ 跳過異常訊息（{type(e).__name__}）")
        except Exception as e:
            if not conn_stop.is_set():
                print(f"[語音辨識] ⚠️ 串流中斷（{type(e).__name__}），下次開麥重連")
        finally:
            with self._lock:
                if self._ws is ws:
                    self._ws = None  # 標記死亡 → 下次 arm 重連

    def _keepalive_loop(self, ws, conn_stop) -> None:
        """常駐：idle（_capturing=False）時每 _KEEPALIVE_INTERVAL 秒送 KeepAlive 撐住
        連線（Deepgram 10s 無音訊/keepalive 即關 NET-0001）。conn_stop 設或 send 失敗即止。"""
        while not conn_stop.wait(_KEEPALIVE_INTERVAL):
            if self._capturing:
                continue  # 收音中音訊自然撐住，不送
            try:
                with self._send_lock:
                    ws.send(_KEEPALIVE_MSG)
            except Exception:
                break  # ws 死 → 退出；receiver 標記 _ws=None

    def disarm(self) -> None:
        """冪等收麥：停收音層（sender + arecord）+ 送 Finalize 沖尾巴；**連線不關**
        （keepalive 撐住，下輪直接開麥）。"""
        with self._lock:
            if not self._capturing:
                return
            self._capturing = False
            audio = self._audio
            send_stop = self._send_stop
            sender = self._sender
            ws = self._ws
            self._audio = None
            self._send_stop = None
            self._sender = None
        send_stop.set()
        audio.close()
        sender.join(timeout=1.0)
        if ws is not None:
            try:
                with self._send_lock:
                    ws.send(_FINALIZE_MSG)  # 沖 pending 音訊，乾淨收尾
            except Exception:
                pass

    def shutdown(self) -> None:
        """程式退出：收收音層 + 送 CloseStream + 關連線 + 收常駐 thread。"""
        self.disarm()
        with self._lock:
            ws = self._ws
            conn_stop = self._conn_stop
            receiver = self._receiver
            keepalive = self._keepalive
            self._ws = None
            self._conn_stop = None
            self._receiver = None
            self._keepalive = None
        if conn_stop is not None:
            conn_stop.set()
        if ws is not None:
            try:
                with self._send_lock:
                    ws.send(_CLOSE_MSG)
            except Exception:
                pass
            try:
                ws.close()
            except Exception:
                pass
        for th in (receiver, keepalive):
            if th is not None:
                th.join(timeout=1.0)


def _is_auth_error(e: Exception) -> bool:
    """websockets InvalidStatus 的 401 偵測——duck-typing 避免頂層 import websockets。"""
    return getattr(getattr(e, "response", None), "status_code", None) == 401


class _ArecordSource:
    """arecord subprocess 包裝：read 走 stdout pipe，close 走 terminate。

    stdin=DEVNULL 對齊 tts.py mpg123 守則（不偷主程式 stdin）；terminate 容錯
    OSError（子程序剛好自然結束——對齊 tts.shutdown 同情境處理）。
    """

    def __init__(self, proc: "subprocess.Popen") -> None:
        self._proc = proc

    def read(self, n: int) -> bytes:
        return self._proc.stdout.read(n)

    def close(self) -> None:
        if self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass


def _default_audio_factory():
    """production 音源：arecord 16kHz/S16_LE/mono raw → stdout pipe。

    裝置選擇：環境變數 STT_ARECORD_DEVICE（如 "plughw:1,0"）；未設用 ALSA 預設
    （Pi 端把 ReSpeaker 設為預設 capture 或設此變數——pineedtodo 會列）。
    """
    cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"]
    device = os.environ.get("STT_ARECORD_DEVICE")
    if device:
        cmd[1:1] = ["-D", device]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)   # arecord 被 terminate 的 EINTR 臨終雜訊不上終端
    return _ArecordSource(proc)


def _default_ws_factory(api_key: str):
    """production 連線：websockets 同步 client（lazy import——Windows 紅線）。"""
    from websockets.sync.client import connect
    return connect(DEEPGRAM_URL,
                   additional_headers={"Authorization": f"Token {api_key}"})


# Lazy singleton（與 input_reader eager singleton 不同的刻意選擇）：import 時
# 不起 thread、不讀 env——Windows pytest import 零副作用；首次 arm 才建。
_worker: "SttWorker | None" = None


def _get_worker() -> SttWorker:
    global _worker
    if _worker is None:
        from myProgram import input_reader
        _worker = SttWorker(sink=input_reader.inject,
                            api_key=os.environ.get("DEEPGRAM_API_KEY"))
    return _worker


def arm() -> None:
    """對外 API：開麥（read_customer_input 於 TTS 播完後呼叫）。"""
    _get_worker().arm()


def disarm() -> None:
    """對外 API：收麥（read_customer_input finally 呼叫）。"""
    _get_worker().disarm()


def shutdown() -> None:
    """對外 API：main() finally 鏈呼叫；singleton 未建過則 no-op。"""
    if _worker is not None:
        _worker.shutdown()
