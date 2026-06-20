# myProgram/tts_cache/ — code_map（本層索引）

> 顆粒：粗。內容定址（content-addressed）TTS 語音快取——**生成資產目錄，無 code**。

## 檔案
- `<sha1>.mp3` — edge-tts 合成的語音檔，檔名 = 文案字串的 SHA1。`tts.py` 合成前先查命中即跳合成（perf_w2/w5）。
  - **預熱資產 tracked**（`tts_prewarm.py` 固定文案一次合成、commit 進版控 → 斷網 / 首播零延遲）；**執行期新文案自我增長**（runtime 生成）。
- 快取資產無索引 / 無 code；本目錄**不手改 / 不手建 / 不手刪**——由 `myProgram/tts.py` 快取邏輯 + `myProgram/tts_prewarm.py` 管理。

## 其他
- `CLAUDE.md` — 本層導引。
- `.claude/code_map.md` — 本檔。
