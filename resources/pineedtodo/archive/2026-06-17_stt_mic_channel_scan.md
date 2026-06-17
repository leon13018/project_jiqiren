# Pi 端待辦 — STT 掃描 raw 麥克風聲道（找「刮刮樂」最清楚的軌）

- **建立日期**：2026-06-17
- **對應提交**：`f7b16ab`（feat(stt): 改抽單一 raw 麥克風聲道（-c 6 + STT_MIC_CHANNEL））
- **簡介**：`-c 1` 降混音質糊,Deepgram 把「刮刮樂五張」聽成「25/八二五張」。改成抓原生 6 軌、抽**單一 raw 麥克風軌**餵 Deepgram。但 4 支生麥(ch1-4)哪支最清楚要實測。本輪:掃 ch1→4,找「刮刮樂」最不會被聽錯的那軌,回報後我寫死成預設。無新依賴。

## ⚠️ Step 1 — 裝置改回 hw（關鍵!`-c 6` 要原生 6ch）
之前 Phase 1 用 `-c 1` 把裝置設成 `plughw:`。現在改 `-c 6` 抓原生 6 軌,**裝置要改回 `hw:`**:
```bash
export STT_ARECORD_DEVICE=hw:CARD=ArrayUAC10
echo $STT_ARECORD_DEVICE     # 應為 hw:CARD=ArrayUAC10（不是 plughw:）
```
若沒改回 hw:,`-c 6` 在 plughw 上可能也行(passthrough),但 hw: 才是原生乾淨來源、建議用。
**喇叭插樹莓派板載 3.5mm。**

## Step 2 — 逐軌掃描（重點）
**每次設一個聲道、重跑、講同一句「刮刮樂五張」幾次**,記哪軌辨識最準:
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull   # 先同步一次

# ── 測 ch1 ──
export STT_MIC_CHANNEL=1
python3.11 -m myProgram          # 進顧客層講「刮刮樂五張」3-5 次,看 [語音辨識] 對不對 → 記下 → q 退出

# ── 測 ch2 ──（不用再 git pull）
export STT_MIC_CHANNEL=2
python3.11 -m myProgram

# ── 測 ch3 ──
export STT_MIC_CHANNEL=3
python3.11 -m myProgram

# ── 測 ch4 ──
export STT_MIC_CHANNEL=4
python3.11 -m myProgram
```
（`STT_MIC_CHANNEL` 範圍 0-5;ch0=處理後軌已知爛、ch5=播放參考,**這兩個別用**,只掃 1-4。設非法值會自動 fallback ch1。）

## 驗證段（重點）
每軌講「刮刮樂五張」「冰紅茶兩瓶」各幾次:
- **✅ 看哪軌的 `[語音辨識]` 最常正確抓到「刮刮樂」**(不被聽成 25/八二五之類數字)、「冰紅茶」也穩。
- 記每軌的命中率印象(例:ch1 爛、ch2 好、ch3 普通、ch4 好)。

**故障排除**:
| 症狀 | 排查 |
|---|---|
| `arecord: Channels count non available` | 裝置還是限制聲道——確認 `STT_ARECORD_DEVICE=hw:CARD=ArrayUAC10`（Step 1）|
| 某軌完全沒聲/全錯 | 那支麥可能離你遠/壞,跳過,測其他軌 |
| 全部軌都把刮刮樂聽錯 | 回報——代表不是聲道問題,要改方向(keyterm/Deepgram 參數,另案)|

**回報**:**哪個 `STT_MIC_CHANNEL`（1/2/3/4）辨識「刮刮樂」最準**（最好附各軌印象）→ 我把它寫死成 `_DEFAULT_MIC_CHANNEL`,以後不用再設 env。
