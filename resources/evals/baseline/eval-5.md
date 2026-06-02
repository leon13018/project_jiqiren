# Baseline transcript — eval 5 (dormant/conventions cluster), model=opus

> T0 baseline，現行 verbose skill。場景：新增 sales 業務邏輯（新優惠規則）重啟 BDD+TDD？流程？繁簡規範？

## Navigator 回覆

一、要不要重啟 BDD+TDD：**要**。「新增 sales/ 業務邏輯」命中重啟條件。流程目前 DORMANT（2026-05-25），playbook + 245 條既有測試（regression 網）仍在。重啟條件（任一）：新增 sales/ 業務邏輯 / 改 L0-L5 規格書致 prod 要動。不重啟例外：純註解/docstring、一行 fix、純 refactor、constants 調數字、SDK 整合測試。

二、流程 4 階段（每層獨立一輪、禁跨層合併）：
1. 主 agent 寫 BDD spec（只註解+空函數 pass 骨架，禁 import prod/禁實作）→ AskUserQuestion 確認 scenarios。
2. 主 agent plan mode 規劃 TDD+Implementation（列改檔/測試檔/fixture/輪數）→ ExitPlanMode 審。
3. 派單一 subagent 走 TDD（EnterWorktree、prompt 塞規範；RED→GREEN→REFACTOR；同一 subagent 連走完；全 scenarios 完一個 commit、git add 明列檔名；警告 dispatcher pitfall 禁 ENTRY 一次寫全路由）。
4. 主 agent 審查 + 自己跑 pytest 全綠（Iron Law）+ 條件性 3a/3b + 收尾。
測試指令：`python -m pytest tests/sales/ -v`。

三、繁簡規範：一律繁體中文（程式碼註解/字串/.md/commit 中文）；不適用對話本身。台灣慣用詞（執行緒/佇列/資料/網路/字串/伺服器/檔案）；環境 quirk＝Windows cp936(GBK)；派 subagent 務必把繁中規則塞進 context。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：bdd-tdd.md + conventions.md（同批平行）。
- reference→reference：不需跳轉，SKILL 路由表分成兩獨立候選（bdd-tdd 管流程、conventions 管繁簡），各自足。bdd-tdd 內連結 dispatch/worktree/standard-workflow/incremental-rebuild/sdd/vendor 屬執行階段才深入，說明流程層級 bdd-tdd 自足。
- 缺漏：「優惠規則」無現成範本/專屬章節（重啟例子是新商品/新分支/新 L 層，未涵蓋折扣這種橫切邏輯，需階段1讀規格書定位）；既有 tests 總數文中不一致（245/248/233），應以 SessionStart 快照為準、驗收用「>=N 無 failed」非寫死。
