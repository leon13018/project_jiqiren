# myProgram/sales/ — 本層導引

> **本層檔案結構索引在 `.claude/code_map.md`——任何「sales 裡的檔在哪 / 結構」務必第一優先讀它。**
> 深入子目錄（`states/` / `constants/`）→ 讀 `<子目錄>/.claude/code_map.md`（若無，以本層 code_map 說明為準）。

銷售對話業務邏輯**核心**：規則匹配點餐 / 收款的多層對話狀態機（L0–L5）+ NLU 意圖辨識 + 商品解析 + 購物車。

- 改本層任何 `.py` → 走 **SDD 流程**（含 BDD/TDD）；改後須跑 `python -m pytest tests/sales/`（Stop hook 會守）。
- 領域設計（對話狀態機 / 跨層流程 / TTS UX）見 `project-01-workflow` skill 的 `sales-dialog-design.md` / `sales-tts-ux.md`；完整安全紅線見 root `CLAUDE.md`。
