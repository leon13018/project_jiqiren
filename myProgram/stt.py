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

    def disarm(self) -> None:
        pass  # Task 5 實作

    def shutdown(self) -> None:
        self.disarm()


def _default_audio_factory():
    raise NotImplementedError  # Task 7 實作（Pi-only：arecord subprocess）


def _default_ws_factory(api_key: str):
    raise NotImplementedError  # Task 7 實作（Pi-only：lazy import websockets）
