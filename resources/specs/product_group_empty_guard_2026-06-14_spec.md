# product_group_empty_guard — Mini SDD spec

> 採納反思 `product-group-unguarded-empty-parse`（2026-06-14）。defense-in-depth；超級小自 patch（sdd.md ≤10 行條件微調）。

- **檔**：`myProgram/sales/states/l2_l3_dialog.py:107`（`_product_group`）
- **改前**：`return parse_products(s)[0][0]`
- **改後**：`result = parse_products(s)` / `return result[0][0] if result else s`；並於 `_PRODUCT_PHONETIC_CANDIDATES` 加註「候選須可被 parse_products 解析」。
- **Why**：候選若不在 KEYWORD_MAP → `parse_products` 回 `[]` → `[0]` IndexError **炸整個 dialog session**。今天 3 候選皆可解（安全），守衛防後人擴充候選時踩雷（crash-class）。
- **驗證**：`python -m pytest tests/sales/`（基線 556）+ 新增 `test_product_group_unparseable_candidate_returns_fallback`（不可解析→fallback、既有候選正確、不炸）。
