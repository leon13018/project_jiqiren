#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""edge-tts 包裝：合成 zh-TW-HsiaoChenNeural 台灣女聲，中斷式播放。

設計：TtsWorker 為 singleton，內部一條 daemon thread 從 queue 取文字依序播放。
say() 為非阻塞 producer：終止當前播放 + 清空 queue + 入新任務。
"""

import asyncio
import queue
import subprocess
import threading

try:
    import edge_tts
    _ENABLED = True
except ImportError:
    _ENABLED = False

VOICE   = "zh-TW-HsiaoChenNeural"
TMP_MP3 = "/tmp/last_tts.mp3"


async def _synthesize(text: str, out_path: str) -> None:
    await edge_tts.Communicate(text=text, voice=VOICE).save(out_path)


class TtsWorker:
    def __init__(self):
        self._q = queue.Queue()
        self._proc = None            # 當前 mpg123 Popen handle
        self._lock = threading.Lock()
        threading.Thread(target=self._loop, daemon=True).start()

    def say(self, text: str) -> None:
        """非阻塞：終止當前 + 清空 queue + 入新任務。"""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
            while not self._q.empty():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break
            self._q.put(text)

    def _loop(self):
        while True:
            text = self._q.get()
            print(f"[語音] {text}")
            if not _ENABLED:
                continue
            try:
                asyncio.run(_synthesize(text, TMP_MP3))
                # 合成期間若又被搶 → 跳過此次播放
                if not self._q.empty():
                    continue
                with self._lock:
                    self._proc = subprocess.Popen(["mpg123", "-q", TMP_MP3])
                self._proc.wait()
                with self._lock:
                    self._proc = None
            except Exception as e:
                print(f"[語音] TTS 失敗：{e}")

    def shutdown(self) -> None:
        """主程式退出時呼叫：終止當前播放 + 清空 queue（mpg123 孤兒不會自動退）。"""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()
            while not self._q.empty():
                try:
                    self._q.get_nowait()
                except queue.Empty:
                    break


tts_worker = TtsWorker()


def say(text: str) -> None:
    """對外 API：非阻塞語音播放。"""
    tts_worker.say(text)


def shutdown() -> None:
    """對外 API：終止當前播放與佇列。"""
    tts_worker.shutdown()


# 保留舊名稱以相容（若有其他 import）
speak = say
