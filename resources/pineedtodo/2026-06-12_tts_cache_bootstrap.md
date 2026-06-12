# TTS 快取預熱＋資產進 git（perf_w5）

- 建立日期：2026-06-12
- 對應提交：`fb48423` — perf(tts): content-addressed disk cache for synthesized speech；
  `ffb635c` — feat(tts): prewarm script for fixed utterances
- 簡介：TTS 改內容定址磁碟快取——固定語音預熱後**零合成零網路**、demo 斷網也能播。
  需要您在 Pi 跑一次預熱並把產物 commit 進 git（一次性 bootstrap）。無新依賴。

## 操作步驟

1. 確認 Pi 已同步到含上述 commit 的 main：
   `cd /home/pi/Desktop/project_jiqiren && git log --oneline -3`
2. 跑預熱（需網路，約 1–3 分鐘，逐句印結果）；**demo 必須是關閉狀態**
   （prewarm 與 demo 同時跑會互踩同句的 .tmp 暫存檔）：
   `python3.11 -m myProgram.tts_prewarm`
   結尾應印 `[預熱] 完成：N 句新合成 / 0 句已存在 / 0 句失敗`（首跑 N 估 60–100）。
   若有失敗句：通常是網路抖動，**重跑同指令**即可（已存在的會 skip、只補失敗的）。
3. 資產 commit 進 git（一次性；之後文案改動重跑預熱後同法補 commit）：
   ```bash
   cd /home/pi/Desktop/project_jiqiren
   git add myProgram/tts_cache
   git commit -m "chore(tts): prewarmed speech cache assets"
   git push origin main
   ```
   （Windows 端之後 `git pull` 取得資產即可，我會處理。）

## 驗證段（預期輸出／行為）

- **即播驗證**：跑 demo——所有固定語音（叫賣、進場詢問、致謝等）應「即說即播」，
  只剩 mpg123 啟動的 ~百 ms 級延遲；不再有逐句 0.5–2 秒合成等待。
- **斷網驗證（可選但推薦）**：拔網線／關 Wi-Fi 重啟 demo——固定語音全部照播；
  動態句（金額等首見句）會印 `[語音] ⚠️ TTS 失敗（階段=synth）` 後跳過（預期行為）。
- **自我增長驗證**：連網跑一次含結帳的完整劇本後，
  `ls /home/pi/Desktop/project_jiqiren/myProgram/tts_cache | wc -l` 應比預熱後變多
  （金額句已自動入快取）；同金額第二次結帳即播。
- **故障排除**：若某句永遠重新合成——SSH log 看該句文字是否每次不同
  （動態插值），屬預期；若固定句仍合成，回報我查 hash key。
- **回報**：預熱句數＋即播/斷網結果，回報後此單關閉
  （前一單 2026-06-12_tts_prefetch_verify.md 的場景 A/B 可順帶一起驗，
  快取命中後句間應完全無縫）。
