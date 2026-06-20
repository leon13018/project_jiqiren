# STT 收音改取 ReSpeaker 第0條處理聲道 — SDD spec

**日期：** 2026-06-20
**類型：** 辨識準確度（`myProgram/stt.py` 收音層）
**裁定：** 使用者 2026-06-20 報「STT 極度不準（整句/數量/品名/意圖全失準）」→ 主 agent SSH 同源 A/B 實證根因 = 收音聲道錯 → 使用者選「改程式走 SDD」。

## 1. 背景與動機（含實證）

Pi 實測 STT 整體辨識極差。SSH 同源 A/B（使用者錄一句 6 聲道 `我要三瓶冰紅茶和五張刮刮樂，然後結賬`，主 agent 拆聲道後各跑 Deepgram nova-3）鐵證：

| 聲道處理 | RMS | Deepgram（zh-TW＋keyterm） |
|---|---|---|
| **第0條（XVF-3000 處理過）** | **1542** | 我要三瓶冰紅茶和五張刮刮樂然後結帳 ✅ 近完美 |
| **6聲道混音（現行 `-c 1` plughw 降混）** | 324 | 我**撈**三瓶冰紅茶（缺「和」）… ❌；配 `zh` 更出「五幺三品冰红茶五脏瓜瓜」亂碼 |
| 4麥混音（ch1-4） | 294 | 近完美（佐證：問題在「把處理聲道與生麥/回授攪在一起」）|

**根因**：ReSpeaker Mic Array v2.0（XVF-3000）原生**只出 6 聲道**（`hw:` 拒 `-c 1`）：**ch0 = 晶片處理過的 ASR 專用聲道**（beamform＋AEC＋除噪＋AGC）、ch1-4 = 生麥、ch5 = 喇叭回授。現行 `arecord -c 1`（plughw）把 6 條**全部降混成單聲道** → 乾淨響亮的 ch0（RMS 1542）被生麥與回授稀釋（RMS 掉到 324）＋處理聲道與生麥有演算法延遲差 → 相位互抵糊掉 → 整句辨識崩潰。

**修法**：收 6 聲道、**只抽 ch0** 送 Deepgram。ch0 額外好處：含 AEC，真機 TTS 播放時能消機器人自己的回音（生麥無此能力）。

> 推翻舊結論：memory `respeaker_mic_array_v2` 記「ch0/單軌不如全麥降混」——本次同源公平 A/B 否證之（舊測法疑似抽錯聲道 / 量錯指標）。收尾修 memory。語言（zh-TW 出繁體；`zh` 出簡體不可用）、keyterm（修「和/喝」、確認對中文有效）、endpointing(300) **皆已正確、不動**。

## 2. 設計核心與行為規約

### 2.1 改動本質
`myProgram/stt.py` **收音層**：`arecord` 改 `-c <STT_CAPTURE_CHANNELS>`（預設 6）；`_ArecordSource.read()` 反交錯抽出 `STT_ASR_CHANNEL`（預設 0）那條 → 仍回單聲道 bytes 給既有 `_send_loop`（Deepgram URL `channels=1` 不變）。**不動** `SttWorker`/arm/disarm/連線層/receiver/keyterm/endpointing/URL。

### 2.2 env 旋鈕（模組常數，沿用 `_ENDPOINTING_MS`/`_PREROLL_MS` 風格；import 時讀一次）
```python
_CAPTURE_CHANNELS = int(os.environ.get("STT_CAPTURE_CHANNELS", "6"))  # XVF-3000 原生 6 聲道
_ASR_CHANNEL = int(os.environ.get("STT_ASR_CHANNEL", "0"))            # ch0 = 處理過 ASR 聲道
```

### 2.3 反交錯（`_ArecordSource`）
- `__init__(proc, channels=1, ch_index=0)` 存 channels / ch_index / `_frame_bytes = channels*2`。
- `read(n)`：`channels==1` → 直通（`stdout.read(n)`，零開銷、向後相容）。否則讀滿 `(n//2)*frame_bytes` bytes（frame 對齊）→ `array('h')` 切片 `samples[ch_index::channels]` 抽該條 → 回 bytes。
- `_readexact(want)`：迴圈讀滿 want（pipe 可能短讀）；EOF 提早回（呼叫端視為結束）。
- 行為不變式：回傳「想要的單聲道 bytes 量」（≤n）；EOF 回 `b""`；`close()` 不變。

### 2.4 工廠
`_default_audio_factory` 的 `-c` 由 `"1"` 改 `str(_CAPTURE_CHANNELS)`；回 `_ArecordSource(proc, channels=_CAPTURE_CHANNELS, ch_index=_ASR_CHANNEL)`。`STT_ARECORD_DEVICE` 注入不變（Pi 現有 `plughw:CARD=ArrayUAC10` 配 `-c 6` 直通 6 聲道，**Pi 端零設定變更**）。

## 3. 改檔範圍（高層）

| 檔 | 類型 | 估行數 |
|---|---|---|
| `myProgram/stt.py` | 修改：+`import array`、+2 env 常數、`_ArecordSource` 反交錯、工廠 `-c`/回傳 | +~25 |
| `tests/stt/test_worker.py` | 改：`test_default_audio_factory_command` 斷言 `-c 6`；新增反交錯抽 ch0 / 直通 / EOF 測試 | +~35 |

## 4. Out of scope（明示不動）

語言碼（zh-TW 已對）｜keyterm 詞表（已有效）｜endpointing(300)｜連線生命週期 / receiver / arm-disarm / prearm / pre-roll｜sales/NLU｜Deepgram URL 其餘參數｜4麥混音方案（ch0 已最佳，且唯一含 AEC）｜Pi `.bashrc` 重複 `export STT_ARECORD_DEVICE` 清理（屬 Pi housekeeping，口頭提醒，非本 spec code）。

## 5. 規範與參考

- 改 worker 檔 `stt.py` → 派 **sales-coder**（karpathy 預載）。
- 對齊既有：env 常數風格（`_ENDPOINTING_MS`）、`_ArecordSource` 註解密度、`FakeAudioSource`/`FakeProc` 測試 fake。
- 紅線：`array` 頂層 import OK（stdlib）；**仍禁** websockets 頂層 import。

## 6. 測試指令與預期

- `py -3.14 -m pytest tests/stt/ -v --tb=short`（本機 `python` 無 pytest，用 py -3.14；見既有 STT spec 紀錄）→ 全綠，含新反交錯測試。
- `py -3.14 -m pytest tests/ -q` → 既有全量 + 新增全綠、0 failed。
- 覆蓋：6 聲道交錯 → `read` 抽出 ch0 序列正確｜`channels=1` 直通｜EOF/短讀回 `b""`/不足｜工廠 cmd 含 `-c 6`｜`STT_ARECORD_DEVICE` 注入不變。
- **Pi by-ear 驗收**（merge 後）：重講「我要三瓶冰紅茶和五張刮刮樂，然後結賬」等 → 辨識應從「糊成一團」變「近完美」。

## 7. Commit 規範

worktree `worktree-stt-ch0`（首 commit = 本 spec + plan）。英文標題（`fix(stt): ...` / `test(stt): ...`）+ 繁中 body + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；`git add` 明列檔名。

## 8. 流程鳥瞰

```
spec+plan commit → sales-coder（TDD）→ Iron Law（pytest 全量 + branch verify）
→ spec-reviewer → code-quality-reviewer → ff-merge → push（hook sync Pi）
→ 使用者 Pi by-ear 重測辨識率 → 修正 respeaker memory 錯誤結論
```
