# myProgram/tts_cache/ — 本層導引

> **本層結構索引：`.claude/code_map.md`。**

內容定址 TTS 語音快取（`<sha1>.mp3`，檔名 = 文案 SHA1）——**純生成資產、無 code**。

- **不要手改 / 手建 / 手刪 mp3**：快取由 `myProgram/tts.py`（合成前查命中）+ `myProgram/tts_prewarm.py`（預熱）管理；要重建跑 `python3.11 -m myProgram.tts_prewarm`。
- 預熱資產 tracked（斷網可播）、執行期新文案自我增長。
- 完整安全紅線 + 繁中規範見 root `CLAUDE.md`，本檔不重述。
