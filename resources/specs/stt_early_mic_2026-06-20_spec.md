# STT 早麥 `STT_EARLY_MIC` — SDD spec（2026-06-20）

> 對應 plan `resources/plans/stt_early_mic_2026-06-20_plan.md`。
> 使用者裁決：走人體聽感、直接開早麥（warm-arecord 重訪，但無 discard-mode 舊坑）。

## 1. 背景與動機

`STT_MIC_OPEN_DELAY_MS`（延後開麥）與 `STT_PREROLL_MS`（數位靜音暖機）兩案 Pi 實測仍未解「顧客馬上講、首字被吞」。使用者實測「**等 1s 再講不掉字**」確立暖機需求，並裁決：**開早麥** —— 提示音還在播時就開 arecord、把**真實環境音**串進 Deepgram 暖機（比數位靜音更真），保證「麥來不及」根本不發生。走人體聽感調整，接受回授風險。

**舊坑提醒**：上次 warm-arecord 掛在「收不到音」（discard-mode sender 把真語音丟掉）。本案**不做 discard**：收音層照常串流，改用既有 `_capturing` 閘**只擋注入**（提示音不被打進訂單），結構更簡單、避開舊坑。

## 2. 設計核心 + 行為規約

**早麥兩段式開麥（`STT_EARLY_MIC=1` 才啟用，預設關 = 現況不變）**：
1. `read_customer_input` 開場（`wait_idle()` 前）呼叫 `stt.arm(capture=False)` → 開連線 + arecord + sender（音流進 Deepgram 暖機），但 `_capturing=False` → 注入閘關（提示音的辨識**不**注入訂單）。
2. `wait_idle()`（提示音播完）後呼叫 `stt.arm()`（`capture=True`）→ 翻 `_capturing=True` 開始注入，**不重開 arecord**（復用早麥已開的收音層）。
3. 顧客語音落在「已暖、麥已開」的串流 → 首字不被吞。

**`arm(capture: bool = True)` 行為規約**：
- `capture=True`（既有預設）：開收音層（若未開）+ `_capturing=True`。**既有單呼叫行為完全不變**（向後相容）。
- `capture=False`：開收音層（若未開）+ **不**設 `_capturing`。
- 收音層「若未開才開」：`self._audio is None` 才 `_audio_factory()` + 起 sender；早麥已開則第二次 `arm()` 只翻 `_capturing`、不重開 arecord。
- 既有冪等防禦（`if self._capturing: return`）保留。

**`disarm()` 修正（早麥必需）**：收音層清理閘從 `if capturing` 改為 `if self._audio is not None` —— 早麥開了 arecord 卻因 q/例外未進注入窗（`_capturing` 從未 True）時，舊 `if capturing` 會**漏收 arecord + sender**（洩漏）。改判 `_audio` 是否開著。對既有路徑等價（capturing 為 True 時 `_audio` 必非 None）。

**注入閘（既有，不改）**：`_receive_loop` 在 `not self._capturing` 時 `_last_nonempty=""; continue`（不注入）。早麥窗（`_capturing=False`）的提示音 Results 自然被擋；翻 True 後顧客語音才注入。提示音 / 顧客語音之間 Deepgram 靠 endpointing 自然斷句，各成獨立 utterance。

## 3. 改檔範圍

- **`myProgram/stt.py`**：
  - `arm` 加 `capture: bool = True` 參數 + 「收音層若未開才開」邏輯（plan 給完整碼）。
  - `disarm` 清理閘 `if capturing` → `if self._audio is not None`（plan 給完整碼）。
- **`myProgram/main.py`**：
  - 模組常數 `_EARLY_MIC = bool(int(os.environ.get("STT_EARLY_MIC", "0")))`（`os` 已 import）。
  - `read_customer_input` 重排：`prearm` → `try{`（早麥則 `arm(capture=False)`）→ `wait_idle` → mic-delay → `arm()` → 倒數讀 `}finally{ disarm }`（plan 給完整碼；非早麥路徑呼叫序與行為不變）。
- **`tests/stt/test_worker.py`**：加 2 測試（capture=False 串流不注入 / capture=True 後不重開 arecord）。
- **`tests/sales/test_main_read_callbacks.py`**：更新 `_make_fake_stt_module`（arm 接 `capture` kwarg，True→"arm" / False→"arm_early"，向後相容）+ 加 2 測試（早麥序列 / 預設無早麥）。

## 4. Out of scope
- 不動 prearm / `_ensure_connected` / `_receive_loop` / `_send_loop` / 連線生命週期。
- 不動 endpointing / `CHUNK_BYTES` / `STT_MIC_OPEN_DELAY_MS` / `STT_PREROLL_MS`（皆獨立並存）。
- 不做 discard-mode（舊 warm-arecord 坑）；回授（提示音尾巴翻閘瞬間漏入）若 Pi 實測明顯，另案收緊閘。

## 5. 規範與參考
- 派 sales-coder（worker 級 stt.py 生命週期 + main.py wire-up + 兩處 tests）；karpathy + TDD frontmatter 預載。
- **生命週期 / race 改動 → 走完整三段 review**（spec-reviewer + code-quality-reviewer）。
- reuse：`_audio_factory` / `_send_lock` / `_ensure_connected` / `_capturing` 閘 / `FakeWs` / `FakeAudioSource` / `_make_worker` / `wait_until` / 既有 `_install_fake_*`。
- sales-coder 須確認 `is_armed()`（回 `_capturing`）的呼叫端容忍「收音層開著但未 capture」語意（早麥窗 `is_armed()` 回 False）。

## 6. 測試指令 + 預期
- 本機：`py -m pytest tests/stt/ tests/sales/ -q` 全綠 + 4 新增；**既有 arm/disarm 冪等、prearm 佈線測試不得回歸**（capture=True 預設＝舊行為）。
- Pi（by-ear）：`STT_EARLY_MIC=1 STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram`，**馬上講** → 聽 (a) 有無收到音（收不到＝舊坑、回報）(b) 提示音有無被打進訂單（回授）(c) 首字有無不再被吞。對照不設（＝0）。

## 7. Commit
- 單一 commit（TDD：先紅）。
- `git add myProgram/stt.py myProgram/main.py tests/stt/test_worker.py tests/sales/test_main_read_callbacks.py`
- message：`feat(stt): add STT_EARLY_MIC to open mic during prompt (gated injection)`

## 8. 流程鳥瞰
```
read_customer_input（STT_EARLY_MIC=1）：
  prearm（連線）
  try:
    arm(capture=False) ── 開場開 arecord+sender，音流→Deepgram 暖機，_capturing=False（不注入）
    wait_idle()        ── 提示音播放期間麥已暖；提示音 Results 被閘擋（不進訂單）
    [mic-open delay]
    arm()              ── capture=True：翻 _capturing，復用已開 arecord（不重開）
    倒數讀入            ── 顧客語音落在「已暖+已開」串流，首字不被吞
  finally:
    disarm()           ── _audio 開著就收（涵蓋早麥開了卻沒 capture 的 q/例外路徑）
```
