# Pi 驗收 — STT Deepgram 串流暖機 `STT_PREROLL_MS`（2026-06-20）

> 對應 spec `resources/specs/stt_preroll_warmup_2026-06-20_spec.md` + plan、commit `9df6712`。
> **核心假設**：每輪開麥先 burst 送 ~1s 靜音暖 Deepgram 串流 → 顧客**馬上講**時串流已暖、首字（冰/紅）不落在暖機窗被吞（= 自動化你「等 1s 再講」的發現，但你不用等）。

## 步驟
`git pull` 後 A/B（都加 `STT_TTS_TIMING=1`），兩輪都**語音播完馬上講**（不要刻意等）`冰紅茶三瓶刮刮樂五張`，各 ≥4 輪：

```
# A（對照，重現問題）：不設 STT_PREROLL_MS
STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram

# B（暖機 1s）
STT_PREROLL_MS=1000 STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram
```

## 驗收項
- [ ] **B 馬上講不再吞首字**：開頭 interim 穩定帶「冰」/「紅」（對照 A 組馬上講會間歇 `紅茶三`、漏「冰」）。
- [ ] **不增延遲體感**：暖機是 burst 送零、非真實等待 → 一問一答節奏跟 A 一樣快、辨識結果不變慢。
- [ ] **預設（不設＝0）行為不變**：回歸確認。
- [ ]（選）往**下**掃 `STT_PREROLL_MS=500` / `=1500` 找「剛好夠暖」的最小值。

## ⚠️ 假設成立 / 否證
- **B 馬上講不再掉首字** → **假設成立、真因確認 = Deepgram 串流暖機**。回報後另案把預設從 0 釘成有效值（降到剛好夠的值即可）。
- **B 還是掉** → 數位靜音暖不夠（Deepgram 可能需真實底噪/AGC 校正，非單純樣本數）→ 備案：real-ambient 暖機（開早麥收真實環境音，warm-arecord 那條較冒險的路），或接受固有 + 自然頓半拍 / 鍵盤·觸控備援撐 demo。

## 備註
- 旋鈕純 env、預設 0 不改行為；不動 arm/disarm/prearm/連線/endpointing。
- 與 `STT_MIC_OPEN_DELAY_MS`（前案 `fc9faa7`）**獨立**，可疊加測（如 `STT_MIC_OPEN_DELAY_MS=200 STT_PREROLL_MS=1000`）。
