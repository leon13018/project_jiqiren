# Pi 端待辦 — STT 暖機 arecord 實測（驗：開頭不再被裁、刮刮樂辨識正確）

- **建立日期**：2026-06-17
- **對應提交**：`cf284c3`（feat(stt): 暖機 arecord 送靜音、arm 即切真實）
- **簡介**：找到真因——舊版 arecord 在語音播完才開,USB 冷啟 ~200–400ms,你一播完馬上開口時「刮刮樂」的「刮」被裁掉 → 聽成數字。現在 arecord 在播放期就**暖機錄音**、送靜音(機器人聲不送),語音一播完 arm 翻旗號即收真實 → **開麥零裁切**。音源仍 `-c 1` 降混。無新依賴、**裝置不用改**（維持 plughw）。

## Step 1 — 裝置（維持上輪 plughw，不用改）
```bash
echo $STT_ARECORD_DEVICE     # 應為 plughw:CARD=ArrayUAC10（上輪已設,不用動）
```
若不是 plughw 開頭 → `export STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10`。
**喇叭插樹莓派板載 3.5mm。**

## Step 2 — 同步 + 跑
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull && python3.11 -m myProgram
```

## 驗證段（重點：故意「搶快」測裁切）
進顧客層,**故意在語音一播完就「馬上、毫不遲疑」開口**講「刮刮樂五張」「冰紅茶兩瓶」各幾次:
- **✅ 核心驗收 1：開頭不再被裁** —— 即使你播完瞬間就開口,「刮刮樂」整個被收到、辨識正確,不再變成「25/八二五張」這種掉頭的結果。
- **✅ 核心驗收 2：無自我回授** —— 機器人講話時不會辨識到自己（靜音期不送機器人聲）。
- **✅ 跟手** —— 播完即可講、不用刻意等。
- 純鍵盤 / 缺 key graceful 不變。

**故障排除**：
| 症狀 | 排查 |
|---|---|
| 還是掉頭/聽成數字 | 回報——若已暖機仍掉頭,代表不是裁切、是 Deepgram+降混難詞上限 → 開下一案攻 keyterm/參數 |
| 出現自我回授 | 不該發生(靜音期不送真實聲)——回報附終端輸出 |
| `Channels count non available` | 裝置變 hw 了——改回 plughw（Step 1）|

**回報**：(1) **「刮刮樂」搶快講還會不會掉頭/聽錯**（最重要）；(2) 整體跟手 + 無回授是否 OK。
