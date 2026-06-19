# STT 移除 disarm Finalize（修空白 speech_final 殭屍 bug）— Mini SDD spec

**日期：** 2026-06-19
**類型：** bug 修復（`myProgram/stt.py` disarm）

## 診斷（Pi 2026-06-19 `STT_TTS_TIMING` log 確認）
殭屍輪：Deepgram interim **正常帶文字**（`final=False ... '紅茶三瓶刮刮樂五張'`），但每個 `speech_final=True` 都是**空字串** → 我們只在 speech_final 帶文字才注入 → 全空 → timeout 自動結帳。

**時序鐵證**：第一輪（**送 Finalize 前**）`speech_final` 帶完整文字、正常；第二輪起（**每次 disarm 送 Finalize 後**）`speech_final` 開始空、越來越糟。→ **元凶 = `disarm` 每輪送 `{"type":"Finalize"}`**：Deepgram Finalize 是設計給串流結束 flush，逐輪 mid-stream 送會破壞後續 utterance 的 finalization。

## 修法：移除 disarm 的 Finalize

`disarm()`（現 ~284-294）改前：
```python
        send_stop.set()
        audio.close()
        sender.join(timeout=1.0)
        # 僅 sender 已收（未卡在 ws.send 持 _send_lock）才送 Finalize；join 逾時仍 alive
        # → 跳過，避免搶 _send_lock 掛死 disarm（連線此時多半已異常，送不送意義不大）。
        if ws is not None and not sender.is_alive():
            try:
                with self._send_lock:
                    ws.send(_FINALIZE_MSG)  # 沖 pending 音訊，乾淨收尾
            except Exception:
                pass
```
改後：
```python
        send_stop.set()
        audio.close()
        sender.join(timeout=1.0)
        # 不送 Finalize：逐輪 mid-stream Finalize 會破壞 Deepgram 對後續 utterance 的
        # finalization（症狀：speech_final 空白、辨識整輪漏掉；Pi 2026-06-19 診斷鐵證）。
        # 改靠 endpointing 自然 finalize（像首輪那樣 final 帶文字）+ _capturing 閘門擋跨輪殘響。
```
同時 `disarm` 內 `with self._lock:` 區塊裡的 `ws = self._ws`（現 ~280）與其賦值移除（不再用到 ws）；模組頂 `_FINALIZE_MSG` 常數移除（不再被引用）。

## 連帶影響
- **A3 反思（disarm-finalize-blocked）的 is_alive 守衛隨 Finalize 一併移除** → 該防護「Finalize 搶 _send_lock 掛死」的情境不復存在（無 Finalize 可掛）；proposals.md 該條 append 一行說明被本 fix 取代（仍 adopted，落實升級為「移除 Finalize 根除」）。
- 跨輪殘響：仍由 `_capturing` 閘門擋（disarm 後 capturing=False，Deepgram 對前一 utterance 尾巴的 endpointing speech_final 到達時被丟棄）。

## 測試
- `tests/stt/test_worker.py`：
  - `test_finalize_sent_on_disarm` → **反轉**為 `test_finalize_not_sent_on_disarm`（disarm 後 `_control_sent(ws, "Finalize")` 為 **False**）。
  - `test_disarm_skips_finalize_when_sender_stuck` → 保留但語意更新：sender 卡死時 disarm 仍 ~1s 內返回不掛死、且（必然）不送 Finalize。斷言 `elapsed < 2.0` + `not _control_sent(ws,"Finalize")` 皆續成立。
  - 其餘（keepalive/closestream/復用/重連/閘門/計時）續綠。
- `py -3.14 -m pytest tests/ -q`（baseline 674）。
- Pi：`STT_TTS_TIMING=1` 跑多輪 → 確認**每輪 `speech_final=True` 都帶文字**（不再空白）、辨識不再整輪漏掉。

## Out of scope
- 開頭裁切（warm-arecord）、持久連線是否改每輪新連線（若移除 Finalize 後仍偶發空 final 才考慮）、endpointing/drain/對話文案：不動。

## Commit
- 明列 `myProgram/stt.py tests/stt/test_worker.py`；末尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
