"""S2 同步 TTS 模組 — edge_tts 合成 + mpg123 阻塞播放。

S2 範圍（incremental-rebuild 第 2 步）：
    - 純單線程同步：speak() 阻塞至播完才 return
    - 無 worker thread / queue / 中斷邏輯（那些是 S4+ 才加）
    - Voice：zh-TW-HsiaoChenNeural（台灣女聲）
    - 合成走 edge_tts.Communicate().save()；播放走 subprocess.run mpg123 -q

設計準則（vs 舊版 legacy_threading_v1/tts.py）：
    - import edge_tts 失敗 → 直接 ImportError（fail-fast，不 silent fallback）
    - runtime 失敗（合成 / 播放炸）→ noisy print 詳細訊息 + return，不 raise（caller dialog 繼續）
    - 嚴禁 silent except / 籠統印一行 e 就 continue

caller（main.py 的 speak callback）使用方式：
    >>> from myProgram import tts
    >>> tts.speak("歡迎光臨")  # 阻塞，等到播放完成才 return
"""

import asyncio
import subprocess
import time

import edge_tts  # fail-fast：缺套件直接 ImportError；S2 demo 環境是 Pi，必須有

VOICE = "zh-TW-HsiaoChenNeural"  # 台灣女聲
TMP_MP3 = "/tmp/last_tts.mp3"  # Linux 絕對路徑（path-conventions 規範）

# mpg123 退出時 ALSA buffer 仍可能有未播完的尾巴音訊（~200-400ms）。下一個 speak
# 立刻啟動新 mpg123 開 ALSA device 會把舊 buffer 沖掉，造成上一句末尾被截斷。
# 故在 subprocess.run 成功 return 後加此 drain 等待。0.3s 是 Pi 上經驗值，
# 短句子尾巴 (~200ms) + 安全餘裕 (~100ms)。
ALSA_DRAIN_SEC: float = 0.3


async def _synthesize(text: str, out_path: str) -> None:
    """edge_tts async 合成至 out_path（覆寫）。"""
    await edge_tts.Communicate(text=text, voice=VOICE).save(out_path)


def speak(text: str) -> None:
    """同步 TTS：合成 + 播放，阻塞至播完才 return。

    失敗策略：noisy print 詳細訊息 + return（不 raise，caller dialog 繼續）。
    分階段（synth / play）try/except 讓使用者知道哪個階段炸的。
    """
    # 跟 S1 一致：speak 開頭印一行，方便 SSH log 觀察說了什麼
    print(f"[語音] {text}")

    # 階段 1：合成 mp3
    try:
        asyncio.run(_synthesize(text, TMP_MP3))
    except Exception as e:
        # edge_tts 可能 raise NoAudioReceived / WebSocketException / asyncio 相關錯
        # 不確定具體類型 → 統一 catch Exception，但訊息要詳細
        print(f"[語音] ⚠️ TTS 失敗（階段=synth）")
        print(f"[語音]   exception = {type(e).__name__}: {e!r}")
        print(f"[語音]   text      = {text!r}")
        print(f"[語音] 此字略過，繼續下一字")
        return

    # 階段 2：播放 mp3（subprocess.run = 同步阻塞 + check=True 非 0 退出碼 raise）
    try:
        subprocess.run(["mpg123", "-q", TMP_MP3], check=True)
    except FileNotFoundError as e:
        # mpg123 binary 不存在（Pi 未 apt install mpg123）
        print(f"[語音] ⚠️ TTS 失敗（階段=play）")
        print(f"[語音]   exception = FileNotFoundError: {e!r}")
        print(f"[語音]   text      = {text!r}")
        print(f"[語音]   hint      = 請在 Pi 上執行 `sudo apt install mpg123`")
        print(f"[語音] 此字略過,繼續下一字")
        return
    except subprocess.CalledProcessError as e:
        # mpg123 退出碼非 0（檔案損毀 / 音訊裝置忙 等）
        print(f"[語音] ⚠️ TTS 失敗（階段=play）")
        print(f"[語音]   exception = subprocess.CalledProcessError: returncode={e.returncode}")
        print(f"[語音]   cmd       = {e.cmd}")
        print(f"[語音]   text      = {text!r}")
        print(f"[語音] 此字略過,繼續下一字")
        return
    except Exception as e:
        # 兜底 — 不明錯誤也要詳細印
        print(f"[語音] ⚠️ TTS 失敗（階段=play）")
        print(f"[語音]   exception = {type(e).__name__}: {e!r}")
        print(f"[語音]   text      = {text!r}")
        print(f"[語音] 此字略過,繼續下一字")
        return

    # 播放成功才 drain：給 ALSA buffer 完成尾巴音訊播放的時間，避免下一個 speak()
    # 立刻啟動新 mpg123 沖掉舊 buffer（症狀：「付款成功」尾巴被截）。失敗 return
    # path 不到這裡因 mpg123 沒真播 = 無 buffer 殘留 = 不需 drain。
    time.sleep(ALSA_DRAIN_SEC)
