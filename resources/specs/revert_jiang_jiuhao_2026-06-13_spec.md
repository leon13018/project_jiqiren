# 撤回「醬就好」NLU hardcode — Mini SDD spec

- **檔**：`myProgram/sales/nlu.py:92`（`_KEYWORDS_CHECKOUT`）+ `tests/sales/test_nlu.py`（`test_nlu_jiang_jiu_hao_homophone_classified_as_checkout`）
- **改前**：`_KEYWORDS_CHECKOUT` 含「醬就好」（本 session commit `7014579` 加）；test 斷言 `classify_intent("醬就好")=="結帳"`
- **改後**：移除「醬就好」keyword + 刪除 `test_nlu_jiang_jiu_hao_homophone` function
- **Why**：「醬就好」是「這樣就好」的台灣合音誤聽（zhè-yàng 連讀成 jiàng）、**非真實存在的詞**。hardcode 進 CHECKOUT 等於把一個誤聽固化成正式 keyword，污染 keyword list（使用者 2026-06-13 指出）。改由**拼音糾錯層的「合音還原」**（醬→這樣）處理——還原成「這樣就好」後，既有 keyword 自然命中。NLU keyword 回歸只含**真詞**。
- **保留**：「這樣就好」（真實口語結帳表達）留在 CHECKOUT，不動。
- **空窗**：撤回後至糾錯層上線前，「醬就好」回「無法判斷」（回 baseline，非 regression——醬就好本 session 才加）。糾錯層合音還原上線後接手。
- **驗證**：`python -m pytest tests/sales/test_nlu.py -q` + 全量；`classify_intent("這樣就好")=="結帳"` 仍通過（真詞保留），`classify_intent("醬就好")` 回「無法判斷」。
