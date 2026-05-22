#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""edge-tts 包裝：合成 zh-TW-HsiaoChenNeural 台灣女聲並阻塞播放。"""

import asyncio
import subprocess
import threading

try:
    import edge_tts
    _ENABLED = True
except ImportError:
    _ENABLED = False

VOICE   = "zh-TW-HsiaoChenNeural"
TMP_MP3 = "/tmp/last_tts.mp3"
_lock   = threading.Lock()


async def _synthesize(text: str, out_path: str) -> None:
    await edge_tts.Communicate(text=text, voice=VOICE).save(out_path)


def speak(text: str) -> None:
    """同步播放台灣國語語音；失敗時 fallback 為文字輸出，不讓 demo 中斷。"""
    print(f"[語音] {text}")
    if not _ENABLED:
        return
    with _lock:
        try:
            asyncio.run(_synthesize(text, TMP_MP3))
            subprocess.run(["mpg123", "-q", TMP_MP3], check=True)
        except Exception as e:
            print(f"[語音] TTS 失敗：{e}")
