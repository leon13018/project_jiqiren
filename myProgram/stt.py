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

# 去頭尾用標點集（中英常見 + 空白）；句中標點保留——只防 strict-short 比對
# （「好。」≠「好」）與字首雜訊，語意內容不動。
_PUNCT = "。，、！？；：．,!?;: \t\r\n"


def _normalize_transcript(text: str) -> str:
    """去頭尾標點與空白（句中不動）；全標點輸入歸空字串（caller 不注入）。"""
    return text.strip(_PUNCT)


# Deepgram 串流端點（統領設計 §2.5 既定參數；Pi 首測若 handshake 400 → 改試
# language=zh-Hant 並回寫 spec §2.3）
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-3&language=zh-TW&encoding=linear16&sample_rate=16000"
    "&channels=1&interim_results=true&endpointing=300&smart_format=false"
)
CHUNK_BYTES = 3200  # 100ms @ 16kHz 16-bit mono——粒度夠細不增 ws 訊息開銷


class SttWorker:
    """Deepgram 串流 worker：arm 起 session（sender+receiver threads）、disarm 終止。

    Thread model：主線程呼叫 arm()/disarm()/shutdown()（_lock 保護 session 狀態）；
    session 內 SttSender（audio.read→ws.send）與 SttReceiver（ws.recv→sink）皆
    daemon=True。無常駐 thread——未 arm 時本 worker 零活動。

    注入 seams（Windows pytest 全 fake）：
        sink：speech_final 文字輸出口（production = input_reader.inject）
        audio_factory：回傳具 read(n)->bytes / close() 的音源（production = arecord）
        ws_factory：接 api_key 回傳具 send/recv/close 的連線（production = websockets）
    """

    def __init__(self, sink, api_key=None, audio_factory=None, ws_factory=None):
        self._sink = sink
        self._api_key = api_key
        self._audio_factory = audio_factory or _default_audio_factory
        self._ws_factory = ws_factory or _default_ws_factory
        self._lock = threading.Lock()
        self._session = None      # (stop_event, audio, ws, receiver, sender)
        self._disabled = False    # 缺 key / 401 → 本次執行停用（鍵盤照常）

    def is_armed(self) -> bool:
        with self._lock:
            return self._session is not None

    def arm(self) -> None:
        """冪等開麥：已 armed / 已停用 no-op；缺 key 印一次警告後停用。"""
        with self._lock:
            if self._disabled or self._session is not None:
                return
            if not self._api_key:
                print("[語音辨識] ⚠️ 未設定 DEEPGRAM_API_KEY，STT 停用（鍵盤輸入照常）")
                self._disabled = True
                return
            ws = self._connect_with_retry()
            if ws is None:
                return  # 本輪放棄（已印原因）；下次 arm 再試或已永久停用
            audio = self._audio_factory()
            stop = threading.Event()
            receiver = threading.Thread(
                target=self._receive_loop, args=(ws, stop),
                name="SttReceiver", daemon=True)
            sender = threading.Thread(
                target=self._send_loop, args=(ws, audio, stop),
                name="SttSender", daemon=True)
            self._session = (stop, audio, ws, receiver, sender)
            receiver.start()
            sender.start()

    def _connect_with_retry(self):
        """建線；非 401 失敗重試 1 次；401 → 永久停用（本次執行）。Task 6 補測。"""
        for attempt in (1, 2):
            try:
                return self._ws_factory(self._api_key)
            except Exception as e:
                if _is_auth_error(e):
                    print(f"[語音辨識] ⚠️ API key 無效（HTTP 401），本次執行停用 STT")
                    self._disabled = True
                    return None
                if attempt == 1:
                    continue
                print(f"[語音辨識] ⚠️ 連線失敗（{type(e).__name__}: {e!r}），本輪改用鍵盤")
                return None

    def _send_loop(self, ws, audio, stop) -> None:
        """audio.read → ws.send；EOF（disarm terminate / 裝置故障）或 stop 即止。"""
        try:
            while not stop.is_set():
                chunk = audio.read(CHUNK_BYTES)
                if not chunk:
                    break
                ws.send(chunk)
        except Exception:
            pass  # ws 已關（disarm / 斷線）→ 靜默結束；對外回報由 receiver 負責

    def _receive_loop(self, ws, stop) -> None:
        """ws.recv → JSON → speech_final 的 transcript 正規化後注入 sink。"""
        try:
            while not stop.is_set():
                msg = ws.recv()
                if isinstance(msg, bytes):
                    continue  # Deepgram Results 皆為 text frame；防禦略過
                data = json.loads(msg)
                if data.get("type") != "Results" or not data.get("speech_final"):
                    continue
                alts = data.get("channel", {}).get("alternatives", [])
                text = _normalize_transcript(alts[0].get("transcript", "")) if alts else ""
                if text:
                    print(f"[語音辨識] {text}")
                    self._sink(text)
        except Exception as e:
            if not stop.is_set():
                # 非 disarm 觸發的中斷（伺服器斷線等）——印警示；不自動重連，
                # 下次 arm 重建 session。timeout 既有 reprompt 流程兜底。
                print(f"[語音辨識] ⚠️ 串流中斷（{type(e).__name__}），本輪改用鍵盤")

    def disarm(self) -> None:
        """冪等收麥：stop → 殺音源（sender 讀到 EOF 止）→ 關 ws（解 receiver 阻塞）。

        join(timeout=1) 讓 session 結束具確定性（測試 / re-arm 安全）；threads 為
        daemon，極端卡住也不擋程式退出（對齊 S6 教訓：不嘗試強解 blocking IO）。
        """
        with self._lock:
            if self._session is None:
                return
            stop, audio, ws, receiver, sender = self._session
            self._session = None
            stop.set()
            audio.close()
            try:
                ws.close()
            except Exception:
                pass  # 已斷線的 ws close 可能 raise——cleanup 路徑安全吞掉
        for th in (receiver, sender):
            th.join(timeout=1.0)

    def shutdown(self) -> None:
        self.disarm()


def _is_auth_error(e: Exception) -> bool:
    """websockets InvalidStatus 的 401 偵測——duck-typing 避免頂層 import websockets。"""
    return getattr(getattr(e, "response", None), "status_code", None) == 401


def _default_audio_factory():
    raise NotImplementedError  # Task 7 實作（Pi-only：arecord subprocess）


def _default_ws_factory(api_key: str):
    raise NotImplementedError  # Task 7 實作（Pi-only：lazy import websockets）
