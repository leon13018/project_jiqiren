# Pi 驗收 — STT/TTS turn-boundary 即時化（2026-06-19）

> 對應：spec `resources/specs/stt_tts_turn_latency_2026-06-19_spec.md`、plan `resources/plans/stt_tts_turn_latency_2026-06-19_plan.md`；commits `52e10eb`→`5c66d8e`（4 個）。
> **零新依賴**。預設行為不變（兩 env 未設 = 與現狀逐位元相同）。

## 兩個新 env 旋鈕（都選用，平時不必設）

| 變數 | 作用 | 何時設 |
|---|---|---|
| `STT_TTS_TIMING` | 設任意值 → 終端多印 `[計時]` 行（TTS 來源/play/synth/drain、STT 開麥→辨識 delta） | **量測時臨時設**，平時不設（避免 log 噪音） |
| `STT_ENDPOINTING_MS` | Deepgram endpointing 毫秒（顧客講完→判定結束的靜默門檻） | **A/B 試 200**；未設 = 300（同現狀） |

單行帶 env 跑法（Pi SSH，避免多行縮排坑）：
`STT_TTS_TIMING=1 STT_ENDPOINTING_MS=200 python3.11 -m myProgram`
（只量測不改 endpointing → 只留 `STT_TTS_TIMING=1`；只 A/B → 只留 `STT_ENDPOINTING_MS=200`。）

## 步驟
1. Pi：`git pull`（拉 4 個 commit）。
2. 先跑**一輪正常語音點餐**（不帶任何新 env）→ 確認**行為與之前完全一樣**（文案/狀態/倒數/辨識都不變）。

## 驗收項

### A. 條件式 drain 自我回授（最關鍵，drain commit `4810f89` 的風險點）
跳過 idle 前的 0.3s drain 後，機器人最後一句的**尾音是否被麥克風收進去、誤辨識成顧客輸入**？理論上 arecord 冷啟動(~300–500ms) ≥ 尾音(~200–400ms) 會吸收，但要 Pi 實測確認。
- [ ] 機器人問句播完 → **不要馬上講話**，靜待它開麥 → 觀察終端有沒有冒出「機器人剛說的話」被當成 `[語音辨識] ...` 顧客輸入。
- [ ] 重複幾輪不同長短的問句（短句尾音風險較高）。
- **若出現自我辨識** → 回報，我單獨 revert `4810f89`（原子，其餘三項不受影響）。

### B. 量測 turn 預算（`STT_TTS_TIMING=1` 跑一輪）
- [ ] `STT_TTS_TIMING=1 python3.11 -m myProgram` 跑一輪完整點餐 → 把終端 `[計時]` 行整段**貼回來**。
  - 看 `[語音][計時] ... play=Xms ... drain=on/off`：drain 在「機器人最後一句、接著要聽顧客」那拍應顯示 **drain=off**（省下 0.3s）；連發句之間應 **drain=on**。
  - 看 `[計時] 開麥後 Z.Zs 出辨識結果`：反映冷啟動 + 顧客講話 + endpointing 總時長。
  - 看 `來源=synth` 的句子 `synth=Xms`：未快取動態句的合成 round-trip 成本（決定要不要走下一步 prewarm 擴充）。

### C. endpointing A/B（`STT_ENDPOINTING_MS=200`）
- [ ] 各跑一輪 300（不設）vs 200 → 比較「顧客講完到機器人反應」的體感。
- [ ] 200 是否切掉中途停頓的顧客（話講一半被當講完）？
- **結論**：200 明顯更好且沒切話 → 告訴我，我把它記進 `~/.bashrc` 設定流程 + `raspberry_pi_setup.md`；否則維持 300（移除 env 即可，不動碼）。

## 回報
- A/B/C 各項 OK / NG，NG 附現象 + 終端 log。
- B 的 `[計時]` log 整段貼回（決定下一步是否再動 endpointing / 走 prewarm 擴充）。
- 整體一問一答體感有沒有變即時。
