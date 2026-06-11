# tts_punct_sweep — Mini SDD spec

- **檔**：`myProgram/tts.py:56,57,99,190,248`
- **改前**：CJK 文字間半形逗號「,」——1 處 print 字串（`此字略過,繼續下一字`）+ 4 處註解
- **改後**：全形「，」
- **Why**：quality_fix_w1 code-quality reviewer 標記殘留；對齊全檔（與全 codebase）全形標點慣例。print 字面屬 console log（非 TTS 語音內容），測試未釘該字面（已 grep `test_tts_worker.py` 確認）。
- **驗證**：`python -m pytest tests/sales/` → 503 passed
