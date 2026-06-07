# ./ — code_map（本層索引）

> Project_01 專案根。顆粒：粗。

## 子目錄
- `myProgram/` — 機器人主程式（Raspberry Pi 上執行）。點餐 / 收款規則匹配系統：`main.py` 進入點與 worker、`vendor/` 廠商 SDK（🔒 禁改）、核心 `sales/` 銷售對話業務邏輯（L0–L5 多層狀態機 + 取消 / 服務確認等跨層流程、NLU、商品解析、購物車、文案常數）。
- `resources/` — 專案文件與產出物（非 code）：SDD 規格 / 計畫 / 審查、研究筆記、架構契約、Pi 需求與待辦、範例、報告、prompt 存檔、roadmap / changelog。
- `tests/` — pytest 測試：sales 業務邏輯回歸網 + spec 測試。
- `.claude/` — Claude Code 配置：`code_map.md`(本檔)、`skills/`（`project-01-workflow` 等）、`hooks/`（自動化 hook；文檔在 `skills/project-01-workflow/reference/` 的 hooks-system 與 hooks-gotchas 兩檔）、`workflows/`（dynamic workflow 腳本：`skill-edd-regression` EDD 回歸 harness，場景庫在 `resources/evals/`）、`agents/`（`sales-coder`）、`settings*.json`。

## 檔案
- `CLAUDE.md` — 專案主規範入口（核心紅線 + 繁中規範 + skill 觸發表 + 本層 code_map 指標）；root 直接放。
- `pytest.ini` — pytest 設定。
- `.gitignore` — Git 忽略清單。
- `sync_pi.ps1` — （gitignored）把 `myProgram/` 同步到 Raspberry Pi 的腳本；push 後手動執行。
