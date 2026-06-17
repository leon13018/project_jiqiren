# Pi 端待辦 — STT Phase 2 v2 實測（重點：驗無自我回授）

- **建立日期**：2026-06-16
- **對應提交**：`cc61647`（讀 ch0）+ `d8c8d77`（來源端閘 prewarm）
- **簡介**：v2 把 prewarm 的閘從「結果端」移到「來源端」——播放期間**完全不送音訊**進 Deepgram，TTS 播完才送顧客音訊。理論上根治 v1 的 STT↔TTS 自我回授（機器人辨識到自己的 TTS → 無限迴圈）。**這次實測的核心就是確認回授沒了。** 無新 pip/apt 依賴。

## Step 1 — 環境（v2 要 6ch + ch0）
```bash
echo $STT_ARECORD_DEVICE    # 應為 hw:CARD=ArrayUAC10（原生 6ch；v2 用 -c 6 取 ch0）
echo $DEEPGRAM_API_KEY      # 應非空
```
若 `STT_ARECORD_DEVICE` 不是 `hw:CARD=ArrayUAC10`（例如之前 revert 時改成 plughw），改回：
```bash
sed -i 's#plughw:CARD=ArrayUAC10#hw:CARD=ArrayUAC10#' ~/.bashrc && source ~/.bashrc
```
**喇叭插樹莓派板載 3.5mm**（TTS 走 ALSA 預設 card 1）。

## Step 2 — 同步 + 跑
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull && python3.11 -m myProgram
```
（`git clean tts_cache` 防 untracked 快取擋 pull。）

## 驗證段（重點）
按 `1` 進叫賣 → `c` 進顧客層 → 講「我要紅茶兩杯」等 5–10 句：
- **✅ 核心驗收：無自我回授** —— 機器人講完話後**不會**再冒出 `[語音辨識] <機器人自己剛說的話>`、**不會**自我對話無限迴圈。只有你講話時才出現 `[語音辨識] <你的話>`。
- 辨識 ≥8/10、繁體；prewarm 後播完可立刻講（連線已熱）。
- 純鍵盤 / 缺 key graceful 不變。

**故障排除**：
| 症狀 | 排查 |
|---|---|
| 又出現自我回授（機器人辨識到自己） | 立即回報——理論不該發生（來源端閘）；附終端輸出 |
| `arecord` channels 錯 / 無音訊 | `STT_ARECORD_DEVICE` 沒指 `hw:` 6ch（v2 需 -c 6） |
| 印「未設定 DEEPGRAM_API_KEY」 | key 沒在跑程式的同一 shell |

**回報**：(1) **有無自我回授**（最重要）；(2) 10 句辨識結果；(3) 體感是否更跟手。
