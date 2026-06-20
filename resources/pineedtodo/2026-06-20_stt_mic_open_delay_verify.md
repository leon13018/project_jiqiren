# Pi 驗收 — STT 開麥延遲 `STT_MIC_OPEN_DELAY_MS`（2026-06-20）

> 對應 spec `resources/specs/stt_mic_open_delay_2026-06-20_spec.md`、commit `fc9faa7`。
> **核心假設**：開麥延後到喇叭 ALSA 尾音排空 → arecord 收到乾淨「靜音→顧客首字」→ 軟起音首字（冰 bīng／紅 hóng）不再被機器人尾音黏吞。
> **前因**：2026-06-20 Pi log 已**否證**「開麥晚 0.5~1s」（`開麥連線` 每輪印在播放中＝prearm 藏住握手、`arm()` 不卡、`開麥→第一個音框 0.14s`）。真症狀＝軟起音首字間歇被吞。

## 步驟
`git pull` 後分兩輪 A/B（都加 `STT_TTS_TIMING=1` 看計時）：

```
# A（預設，對照組）：不設 STT_MIC_OPEN_DELAY_MS
STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram

# B（實驗組）：開麥延後 300ms
STT_MIC_OPEN_DELAY_MS=300 STT_TTS_TIMING=1 STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 python3.11 -m myProgram
```
兩輪都「語音播完馬上講」`冰紅茶三瓶刮刮樂五張`，各跑 ≥4 輪。

## 驗收項
- [ ] **A（預設）行為不變**：開麥即時、辨識照舊（迴歸確認預設 0 = 無影響）。
- [ ] **B：「冰/紅」首字不再間歇被吞**：對照 A，看開頭 interim 是否穩定帶「冰」/「紅」（A 組曾 turn 3/4 開頭直接 `紅茶三`、漏「冰」）。
- [ ] **B 體感不變慢**：延後的 0.3s 被「聽到靜音→反應開口」反應時間吸收，不覺得卡。
- [ ]（選）試 `STT_MIC_OPEN_DELAY_MS=200` / `=400` 找甜蜜點。

## ⚠️ 假設成立 / 否證
- **B 首字吞顯著改善** → 假設成立。回報後另案把預設值從 0 釘成有效值（再走一次 SDD 改預設）。
- **B 沒差 / 反而更糟（延後反而裁掉搶快的首字）** → 假設否證：首字吞是純 Deepgram 串流固有 + Pi 聲學，**收手接受**（自然停半拍 / 鍵盤備援撐 demo）。旋鈕留著預設 0、不啟用即可，無需 revert。

## 備註
- 旋鈕純 env、預設 0 不改行為；不動 prearm / arm / disarm / 條件式 drain。
- 與 warm-arecord（已 revert）方向相反：warm 是「更早開麥（進播放段）」失敗；本案是「更晚開麥（過尾音）」。
