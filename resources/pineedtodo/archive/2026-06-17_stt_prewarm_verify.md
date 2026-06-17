# Pi 端待辦 — STT prewarm（不加 ch0）實測（重點：跟手度有無變快 + 辨識不退步）

- **建立日期**：2026-06-17
- **對應提交**：`44ad113`（feat(stt): v2 式 prewarm 預熱連線（保留 -c 1 mono、不加 ch0））
- **簡介**：在你剛確認辨識正常的 Phase 1（`-c 1` mono）上,加回 v2 式 prewarm——prompt 播放期背景先連好 Deepgram ws + 送 KeepAlive 維持(**不開麥不送音訊**),播完 `arm` 才開麥。目的:把 ws 握手(~0.2–0.5s)藏進播放期 → 播完到能講少等一點。**這次比的是「跟手度」,辨識準確度應跟 Phase 1 一樣(沒加 ch0)。** 無新依賴。

## Step 1 — 裝置(跟 Phase 1 一樣,通常不用改)
```bash
echo $STT_ARECORD_DEVICE     # 應為 plughw:CARD=ArrayUAC10（你上次已設好）
```
若不是 `plughw:` 開頭 → `sed -i 's#=hw:CARD=ArrayUAC10#=plughw:CARD=ArrayUAC10#' ~/.bashrc && source ~/.bashrc`。
**喇叭插樹莓派板載 3.5mm。**

## Step 2 — 同步 + 跑
```bash
cd /home/pi/Desktop/project_jiqiren && git clean -f myProgram/tts_cache/ ; git pull && python3.11 -m myProgram
```

## 驗證段（重點）
進顧客層講 5–10 句:
- **✅ 核心驗收 1:辨識仍正常** —— 跟剛剛 Phase 1 一樣準(≥8/10、繁體),**沒有**因 prewarm 退步。(prewarm 期不送音訊,理論上不影響辨識。)
- **✅ 核心驗收 2:播完到能講有無變跟手** —— 對比你印象中剛剛的 Phase 1,提示音/語音播完後開口被收音「少等一點」(省掉 ws 握手)。**老實回報「有感 / 沒感 / 差不多」即可**——這就是這次要測的唯一問題。
- 無自我回授(機器人不會辨識到自己);純鍵盤 / 缺 key graceful 不變。

> **預期管理**:prewarm 只省 ws 握手那 0.2–0.5s;endpointing(~0.3s)+轉錄的固有延遲還在、prewarm 動不到。若你覺得「差不多沒感」,代表瓶頸在 Deepgram 那段,那我們就知道下一步該調 endpointing(另一題)、而非 prewarm。**沒感也是有效結果,照實說。**

**故障排除**:
| 症狀 | 排查 |
|---|---|
| 辨識變差(vs 剛剛 Phase 1) | 不該發生——回報,附終端輸出 |
| 錄不到 / arecord 報 `Channels count non available` | `STT_ARECORD_DEVICE` 又變 `hw:`(要 `plughw:`,見 Step 1) |
| 出現自我回授 | 不該發生(prewarm 期不送音訊)——回報 |

**回報**:(1) **辨識準確度** vs Phase 1(一樣 / 變差);(2) **跟手度**(有感變快 / 沒感 / 差不多)。
