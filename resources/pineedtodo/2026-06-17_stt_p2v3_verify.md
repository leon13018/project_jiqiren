# Pi 端待辦 — STT Phase 2 v3 實測（重點：無自我回授仍成立 + 播完跟手度改善）

- **建立日期**：2026-06-17
- **對應提交**：`ea0bd57`（暖機期送靜音、arecord 提前 prewarm）
- **簡介**：v2 把 arecord 留在 `arm()`（提示音播完）才起 → 仍有 subprocess spawn 啟動延遲（你回報「播完不能馬上講、卡頓」）。v3 把 arecord **提前到 `prewarm`** 暖好、暖機期 sender 讀真實聲但送**等長靜音**（機器人聲讀進但永不送進 Deepgram、靜音同時維持連線取代 KeepAlive），`arm` 只翻旗號解 mute 改送真實 → arm 後零啟動延遲。**這次實測兩件事：(1) v2 的無自我回授有沒有被破壞；(2) 播完到能講有沒有變跟手。** 無新 pip/apt 依賴。

## Step 1 — 環境（與 v2 相同：6ch + ch0）
```bash
echo $STT_ARECORD_DEVICE    # 應為 hw:CARD=ArrayUAC10（原生 6ch；取 ch0）
echo $DEEPGRAM_API_KEY      # 應非空
```
若 `STT_ARECORD_DEVICE` 不是 `hw:CARD=ArrayUAC10`，改回：
```bash
sed -i 's#plughw:CARD=ArrayUAC10#hw:CARD=ArrayUAC10#' ~/.bashrc && source ~/.bashrc
```
**喇叭插樹莓派板載 3.5mm**（TTS 走 ALSA 預設 card 1）。

## Step 2 — 同步 + 跑
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull && python3.11 -m myProgram
```
（`git clean tts_cache` 防 untracked 快取擋 pull / 擋 Stop hook 自動 sync。）

## 驗證段（重點）
按 `1` 進叫賣 → `c` 進顧客層 → 講「我要紅茶兩杯」等 5–10 句：
- **✅ 核心驗收 1：無自我回授仍成立** —— 機器人講完話後**不會**冒出 `[語音辨識] <機器人自己剛說的話>`、**不會**自我對話無限迴圈。只有你講話時才出現 `[語音辨識] <你的話>`。（v3 mute 在來源端送靜音，機器人聲一樣永不進 Deepgram，理論上回授仍被根治。）
- **✅ 核心驗收 2：播完跟手度改善** —— 提示音/機器人語音播完後，**幾乎可立刻開口**就被收音辨識，不像 v2 有「播完到能講」的明顯空檔卡頓。（arecord 已在播放期間暖好。）
- 辨識 ≥8/10、繁體；純鍵盤 / 缺 key graceful 不變。

**故障排除**：
| 症狀 | 排查 |
|---|---|
| 又出現自我回授（機器人辨識到自己） | 立即回報——理論不該發生（來源端送靜音）；附終端輸出 |
| 播完仍明顯卡頓、要等一下才收音 | 回報——可能 ALSA drain 尾音（~0.3s 機器人尾音，本就不在 v3 範圍）vs arecord 未暖好，需區分 |
| `arecord` channels 錯 / 無音訊 | `STT_ARECORD_DEVICE` 沒指 `hw:` 6ch（需 -c 6） |
| 印「未設定 DEEPGRAM_API_KEY」 | key 沒在跑程式的同一 shell |

**回報**：(1) **有無自我回授**（最重要）；(2) **播完跟手度有無改善**（vs v2）；(3) 10 句辨識結果。
