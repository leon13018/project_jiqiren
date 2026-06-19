# STT 開麥延遲旋鈕 `STT_MIC_OPEN_DELAY_MS` — Mini SDD spec（2026-06-20）

> 實驗：驗證「開麥延後到喇叭 ALSA 尾音排空 → 顧客軟起音首字不被吞」假設。
> Pi 量測背景見 `changelogs/changelog_2026-06-19_stt_realtime.md`。

## 1. 背景與動機（Pi log 鐵證）

2026-06-20 Pi 實測（`STT_TTS_TIMING=1`）**否證**了「開麥晚 0.5~1s」假設：
- `開麥連線 511~679ms` **每輪都印在提示音播放中**（在各句 `play=Xms` 完成 log 之前）→ prearm 完全藏住握手，`arm()` 不卡。
- `開麥→第一個音框 0.14s` 每輪一致（= 100ms chunk + ~40ms arecord 冷啟動），不是 0.5s。
- `timeout=12`（開始聽）在 mpg123 一結束就觸發，比顧客耳朵「聽到靜音」早 ~0.3s（ALSA 尾巴仍在響）。

**真症狀**：軟起音首字（冰 bīng / 紅 hóng）**間歇**被吞 —— Pi log turn 2 第一個 interim 是 `'冰'`（收到），turn 3/4 開頭直接 `'紅茶三'`、`'紅茶商品'`（冰沒了）。

**機制嫌疑**：最後一句提示音 `drain=off`（為省 turn boundary 0.3s 跳過 ALSA 排空）→ `arm()` 在喇叭尾音（~300ms）還在響時就開 arecord → 收進機器人自己的尾音 → 顧客緊接的軟起音黏在尾音後，被 Deepgram 串流起音偵測一起吞。

## 2. 假設與實驗

把開麥稍微**延後**到尾音排空，arecord 收到乾淨「靜音 → 顧客首字」→ 起音不被吞。以 env 旋鈕量化延遲、**預設 0（不改行為）**，Pi 端 A/B（0 vs 300）驗證。延後的 ~0.3s 由顧客「聽到靜音 → 反應開口」的反應時間吸收，不實際變慢。

## 3. 改檔範圍

### `myProgram/main.py`
- **加 import**：頂層 `import os`（現只 import `math`/`sys`/`time`）。
- **加模組常數**（imports 後、`class _S1State` 前）：
  ```python
  # 開麥延遲（env 旋鈕）：wait_idle 後、arm 前等這麼久讓喇叭 ALSA 尾音排空，
  # 避免 arecord 把機器人尾音收進去、黏吞顧客軟起音首字。預設 0 = 不改行為。
  _MIC_OPEN_DELAY_SEC = int(os.environ.get("STT_MIC_OPEN_DELAY_MS", "0")) / 1000.0
  ```
- **`read_customer_input`**：在 `tts.wait_idle()` 之後、`stt.arm()` 之前（`stt.arm()` 那行正上方、`try` 區塊外）插入：
  ```python
  if _MIC_OPEN_DELAY_SEC > 0:
      time.sleep(_MIC_OPEN_DELAY_SEC)
  ```
  （`time` 已 import。）

### `tests/sales/test_main_read_callbacks.py`（既有 read_customer_input／prearm 佈線測試所在；實際檔名以 repo 為準，由 sales-coder 置於對應檔）
- **測試 A（旋鈕生效 + 序列）**：patch 模組常數 `main._MIC_OPEN_DELAY_SEC = 0.3` + patch `main.time.sleep` → 呼叫 `read_customer_input` → 斷言 `time.sleep` 以 `0.3` 被呼叫，且整體呼叫序為 `tts.wait_idle → time.sleep → stt.arm`（用 mock 的 call order／`mock_calls` 驗，確認延遲落在「等播完」與「開麥」之間）。
- **測試 B（預設不改行為）**：`main._MIC_OPEN_DELAY_SEC = 0.0`（預設）→ 斷言開麥前**未**插入 `time.sleep` 延遲（序列中 `wait_idle` 後直接 `arm`，無 sleep）。

> 測試 mock 注入點、既有 fixture reuse 由 sales-coder 依 TDD 決定；以上為行為規約。注意 `read_customer_input` 走 `_tick_countdown` + fake `input_reader.read`，斷言要針對「開麥延遲那次 sleep」、別與倒數邏輯混淆。

## 4. Out of scope
- 不動 `stt.py` / `tts.py`（prearm / arm / disarm / 條件式 drain 邏輯全不變）。
- 不調 endpointing / `CHUNK_BYTES`（另案）。
- 不碰 warm-arecord（已 revert，且方向相反）。

## 5. 驗證
- **本機**：`python -m pytest tests/sales/` 全綠，數量 = 現有 + 2 新增。
- **Pi A/B**：
  ```
  STT_MIC_OPEN_DELAY_MS=300 STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram
  ```
  跑多輪、講「冰紅茶三瓶刮刮樂五張」，對照預設（不設＝0）→ 看「冰/紅」首字是否不再間歇被吞。

## 6. Commit
- 單一 commit（TDD：test 先紅 → 最小 prod 綠）。
- `git add myProgram/main.py tests/sales/test_main_read_callbacks.py`
- message：`feat(stt): add STT_MIC_OPEN_DELAY_MS to delay mic-open past speaker ALSA tail`
