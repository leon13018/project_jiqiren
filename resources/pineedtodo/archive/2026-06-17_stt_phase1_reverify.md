# Pi 端待辦 — STT 退回 Phase 1 後重測（確認辨識恢復正常）

- **建立日期**：2026-06-17
- **對應提交**：`6b20e7f`（revert(stt): 退回 Phase 1 — 移除 ch0 + prewarm）
- **簡介**：v2/v3 改讀 ReSpeaker ch0（處理後聲道）+ prewarm，Pi 實測辨識變不准（有講沒錄進 / 錄進但轉換錯誤）、prewarm 也無感。已 revert 回 Phase 1（`-c 1` mono 降混、播完才開麥），這版你先前實測辨識正常。**本輪確認辨識恢復正常。** 無新 pip/apt 依賴。

## ⚠️ Step 1 — 改回降混裝置（關鍵！否則 arecord 會失敗）
Phase 1 用 `arecord -c 1`（單聲道降混）。v2/v3 期間你把 `STT_ARECORD_DEVICE` 設成 `hw:CARD=ArrayUAC10`（原生固定 6ch）——**`hw:` 配 `-c 1` 會衝突 / 失敗**。改回可降混的 `plughw:`：
```bash
echo $STT_ARECORD_DEVICE     # 現在大概是 hw:CARD=ArrayUAC10
sed -i 's#hw:CARD=ArrayUAC10#plughw:CARD=ArrayUAC10#' ~/.bashrc && source ~/.bashrc
echo $STT_ARECORD_DEVICE     # 應變成 plughw:CARD=ArrayUAC10
```
（若 `~/.bashrc` 裡本來就是 `plughw:...` 就不用改；確認是 `plughw:` 開頭即可。`plughw` 會自動把 6ch 降混成 `-c 1` 要的單聲道。）
**喇叭插樹莓派板載 3.5mm**（TTS 走 ALSA 預設 card 1）。

## Step 2 — 同步 + 跑
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull && python3.11 -m myProgram
```

## 驗證段（重點）
按 `1` 進叫賣 → `c` 進顧客層 → 講「我要紅茶兩杯」等 5–10 句：
- **✅ 核心驗收：辨識恢復正常** —— 你講的話有被錄進、轉錄內容正確（≥8/10、繁體），不再像 v3 那樣「沒錄進 / 轉換錯誤」。
- 純鍵盤 / 缺 key graceful 不變。
- （延遲：播完到能講仍有 Deepgram endpointing ~0.3s + 轉錄的固有延遲，這是結構性的、Phase 1 本來就有，非本輪要解。）

**故障排除**：
| 症狀 | 排查 |
|---|---|
| 完全錄不到 / arecord 報錯 | `STT_ARECORD_DEVICE` 還是 `hw:`（要改 `plughw:`，見 Step 1） |
| 辨識仍不准 | 回報——可能不是 ch0 而是其他（麥克風增益 / 喇叭位置 / 環境噪音）；附終端輸出 |
| 印「未設定 DEEPGRAM_API_KEY」 | key 沒在跑程式的同一 shell |

**回報**：(1) **辨識有無恢復正常**（最重要，vs v3）；(2) 10 句辨識結果。
