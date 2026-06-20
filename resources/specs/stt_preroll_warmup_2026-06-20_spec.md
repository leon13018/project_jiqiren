# STT Deepgram 串流暖機 pre-roll `STT_PREROLL_MS` — SDD spec（2026-06-20）

> 對應 plan `resources/plans/stt_preroll_warmup_2026-06-20_plan.md`。
> 背景延續 `changelogs/changelog_2026-06-19_stt_realtime.md` + spec `stt_mic_open_delay_2026-06-20`。

## 1. 背景與動機（Pi 實證）

2026-06-20 Pi A/B（mic-open delay）+ 使用者關鍵實驗確立真因：
- **mic-open delay A/B**：B（開麥延後 300ms、乾淨無尾音）比 A（開麥早、收進機器人尾音）少掉首字，但**仍掉**。
- **使用者決定性實驗**：語音播完「**等 1 秒再講**」→ 首字完全不掉；「**馬上講**」→ 首字（冰/紅）間歇被吞。

→ 真因 = **Deepgram 每輪串流前 ~1s「暖機」期辨識不穩**。顧客首字若落在暖機窗 → 被吞。三情境一致解釋：

| 情境 | 暖機 | 乾淨 | 結果 |
|---|---|---|---|
| A（開麥早）| ~300ms | ❌ 機器人尾音 | 掉 |
| B（開麥晚）| ~0ms（一開口就是串流起點）| ✅ | 掉 |
| 等 1s | ~1s | ✅ | **不掉** |

贏的組合＝**乾淨 + 滿暖機**。A 有暖機但髒、B 乾淨但沒暖機。

## 2. 設計核心 + 行為規約

**每輪開麥時，先送 `STT_PREROLL_MS` 毫秒的靜音 PCM 給 Deepgram，再串真實 arecord 音訊** → 顧客開口時串流已暖、首字落在暖區被收到。

- 暖機是 **burst 送零位元組**（非真實等待）→ 不增 turn 空檔、不增辨識結果延遲（Deepgram 以樣本數而非 wall-clock 暖機）。
- 純送數位零 → **不開早麥、不收機器人音、不碰 AEC**。
- **預設 `0` = 不送 = 完全不改行為**；與既有 `STT_MIC_OPEN_DELAY_MS`（前案）獨立並存。

**靜音量**：arecord 為 16kHz × 2 byte（S16_LE）× mono → `total = int(16000 * 2 * _PREROLL_MS / 1000)` bytes，以 `CHUNK_BYTES`(3200 = 100ms) 切片送，最後一片取 `min(CHUNK_BYTES, 剩餘)`。

**送出時機**：`_send_loop` 進 while 收音迴圈**之前**送（既有 `try` 內、`first=True` 之後）：
- `first`（「開麥→第一個音框」計時）仍量第一個**真實 arecord** 框，pre-roll 不影響。
- pre-roll 迴圈內檢查 `send_stop`（disarm 期間可中止）；每片 `ws.send` 走 `_send_lock`（序列化）。
- pre-roll 例外由既有 `except Exception: pass` 接（連線死則靜默結束，receiver 負責標記）。

## 3. 改檔範圍

- **`myProgram/stt.py`**：
  - 模組常數 `_PREROLL_MS`（置 `_ENDPOINTING_MS` 附近，§2 字面）。
  - `_send_loop`：while 迴圈前加 pre-roll 送靜音段（plan 給完整碼）。
- **`tests/stt/test_worker.py`**：加 2 測試（pre-roll 設值 → 靜音框前綴 + 預設 0 → 無前綴）。

## 4. Out of scope
- 不動 arm / disarm / prearm / 連線生命週期；不動 endpointing / `CHUNK_BYTES`。
- 不碰 warm-arecord（real-ambient 暖機是備案；本案先試**數位靜音**，便宜零風險）。
- `STT_MIC_OPEN_DELAY_MS`（前案 commit `fc9faa7`）不動、與本案獨立並存。

## 5. 規範與參考
- 派 sales-coder（worker 級 `stt.py` + `tests/stt/`）；karpathy + TDD frontmatter 預載。
- reuse：`CHUNK_BYTES` / `_send_lock` / `FakeWs.sent` / `_make_worker` / `wait_until`（皆既有）。

## 6. 測試指令 + 預期
- 本機：`py -m pytest tests/stt/ -v` 全綠 + 2 新增（`python -m pytest` 若無 pytest 改 `py -m pytest`）。
- Pi：`STT_PREROLL_MS=1000 STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram`，**馬上講**「冰紅茶三瓶刮刮樂五張」多輪 → 首字是否不再被吞（對照不設＝0）。

## 7. Commit
- 單一 commit（TDD：先紅 → 最小綠）。
- `git add myProgram/stt.py tests/stt/test_worker.py`
- message：`feat(stt): add STT_PREROLL_MS to warm Deepgram stream before customer speech`

## 8. 流程鳥瞰
```
arm → _send_loop 起跑
  ├ pre-roll（_PREROLL_MS>0）：送 N ms 靜音 burst → Deepgram 暖機（_send_lock，gate send_stop）
  └ while：arecord.read → ws.send（顧客語音落在「已暖」串流，首字不被吞）
```
