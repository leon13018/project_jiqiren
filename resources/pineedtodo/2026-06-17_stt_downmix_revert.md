# Pi 端待辦 — STT 退回 plughw -c 1 降混（裝置改回 plughw）

- **建立日期**：2026-06-17
- **對應提交**：`4301a55`（revert(stt): 退回 -c 1 plughw 降混）
- **簡介**：單一 raw 麥克風軌(ch1-4)實測「很難分辨」、訊號比多麥降混弱 → 退回 `plughw -c 1` 全麥降混(你記得辨識較好的 Phase 1 音源)。本輪 Pi 端**只需把裝置從 hw 改回 plughw**。無新依賴。

## ⚠️ Step 1 — 裝置改回 plughw（關鍵!`-c 1` 需降混）
掃軌時你把裝置設成 `hw:`(原生 6ch)。現在退回 `-c 1` 降混,**要改回 `plughw:`**:
```bash
export STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10
echo $STT_ARECORD_DEVICE     # 應為 plughw:CARD=ArrayUAC10（不是 hw:）
```
（`-c 1` 配 `hw:` 會報 `Channels count non available`;`plughw` 才會把 6ch 降混成 1ch。`STT_MIC_CHANNEL` 已無作用,設不設都行。）
**喇叭插樹莓派板載 3.5mm。**

## Step 2 — 同步 + 跑
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull && python3.11 -m myProgram
```

## 驗證段
進顧客層講幾句:
- **✅ 辨識恢復到你記得「比較好」的程度**(全麥降混)。
- 若「刮刮樂」這類難詞仍偶爾被聽錯——這是 Deepgram + 降混的固有上限,**下一步要攻 keyterm / Deepgram 參數**(另案),不是聲道問題了。

**故障排除**:
| 症狀 | 排查 |
|---|---|
| `arecord: Channels count non available` | 裝置還是 `hw:`——改回 `plughw:`（Step 1）|
| 辨識比掃軌時還差 | 不該發生(降混訊號較強);回報附終端輸出 |

**回報**:(1) 辨識是否恢復到可用程度;(2) 「刮刮樂」這類難詞還會不會偶爾錯(決定要不要開下一案攻 Deepgram 參數)。
