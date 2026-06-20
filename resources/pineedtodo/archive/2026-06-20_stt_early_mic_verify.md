# Pi 驗收（by-ear）— STT 早麥 `STT_EARLY_MIC`（2026-06-20）

> 對應 spec `resources/specs/stt_early_mic_2026-06-20_spec.md` + plan、commits `7def4cd`/`eaca0e4`/`46cffa8`。
> **核心**：`STT_EARLY_MIC=1` → 提示音**播放期間**就開 arecord 把**真實環境音**串進 Deepgram 暖機（`_capturing=False` 不注入、提示音不進訂單），提示音播完才 `arm()` 翻注入閘 → 顧客馬上講的首字落在「已暖 + 麥已開」串流。
> 使用者裁決：走人體聽感、直接開早麥（warm-arecord 重訪，**無 discard-mode 舊坑**，改用 `_capturing` 閘只擋注入）。

## 步驟
`git pull` 後 A/B（都加 `STT_TTS_TIMING=1`），兩輪都**語音播完馬上講**（不要刻意等）`冰紅茶三瓶刮刮樂五張`，各 ≥4 輪：

```
# A（對照，重現問題）：不設
STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram

# B（早麥）
STT_EARLY_MIC=1 STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram
```

## by-ear 驗收項（依優先序聽）
- [ ] **① 收得到音（最優先 = 舊坑檢查）**：B 講話**有反應**、不是「我說話根本沒反應 / 收不到音」（上次 warm-arecord 掛的就是這個）。**完全沒反應 = 踩舊坑 → 回報、收手**。
- [ ] **② 提示音沒被打進訂單（回授閘）**：機器人的提示音**沒**變成你的訂單字（`_capturing` 閘該擋掉播放期間的辨識）。若提示音的字冒進訂單 = 閘沒擋乾淨 → 回報。
- [ ] **③ 首字不再被吞（目標）**：B 馬上講，開頭「冰/紅」穩定收到（對照 A 馬上講會間歇漏「冰」）。
- [ ] **④ 不卡頓 / 不增延遲**：一問一答節奏正常、不掛死。

## ⚠️ 假設成立 / 否證
- **①✓ ②✓ ③✓** → **早麥成立、真因坐實**。回報後另案把 `STT_EARLY_MIC` 釘成預設。
- **① 收不到音** → 踩舊 warm-arecord 坑（即使無 discard 仍收不到）→ 回報，`STT_EARLY_MIC=0` 即關（預設本就關、不需 revert），早麥這條收手。
- **② 有回授**（提示音進訂單） → 注入閘需收緊（另案：`_capturing` False→True 翻轉瞬間擋掉 trailing 的提示音 speech_final）。先回報嚴重程度。

## 備註
- 旗標純 env、預設關 = 現況不變；可與 `STT_MIC_OPEN_DELAY_MS` / `STT_PREROLL_MS` 疊加測。
- 已知 minor risk（reviewer 標、accepted）：早麥開了 arecord 後若連線**中途死掉**、第二次 `arm()` 重連換新 `_ws`，舊 sender 仍對舊 ws 送（被 `_send_loop` broad except 吞）→ 該輪可能沒音。單輪連線 ~12s 內罕見、不 block 實驗；若 Pi 實測偶發「某輪突然全沒音」再回報。
