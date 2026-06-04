# Scaffolding 盤點報告 2026-06-04

> 來源：spec `resources/specs/scaffolding_audit_slimming_2026-06-04_spec.md`；4 個唯讀 fresh-eyes subagent 盤點波結果，經主 agent 去重、抽查證據、複核後彙整。
> 證據品質註記：Agent ③（流程門檻）抽查不過——「NOTES.md 記載官方已修補 Gotcha M」查無此文、pineedtodo 數量報 8 實為 5、多處比率（95%/85%）無出處。已逐條複核其檔案引述（屬實者保留）、**剔除全部統計類偽證據**；其 Iron Law / code_map 兩項建議經複核降為留觀察。

## A. 刪除組（高信心）

| # | 位置 | 現況 | 為何 overhead | 證據 | 誤刪風險 |
|---|---|---|---|---|---|
| A-1 | `.claude/hooks/auto-sync-pi.log` | 161KB 舊 log，停更於 2026-06-03 | 產生它的 `auto-sync-pi.ps1` 已於 commit `82b04cd` 移除（被 stop-sync-pi 取代），純堆積 | `ls` 實測 mtime 停更；git log 確認 hook 已刪；gitignored 不入版控 | 無（活躍 log 在 stop-sync-pi.log） |
| A-2 | `myProgram/vendor/CLAUDE.md:7` | 重述「禁改、只能 Read/import」紅線 + pointer | root ⛔#1 為權威版；root 維護原則明文「子層不重述紅線、只留薄 pointer」；hook 才是強制層 | 原文引述已驗；root CLAUDE.md 維護原則章 | 極低（hook `block-vendor-edit` 仍強制擋；L8「為何禁改」細節保留） |

## B. 降級組（中信心：恆載 → 按需 / 規則調參）

| # | 位置 | 現況 | 降到哪 | 證據 | 風險 |
|---|---|---|---|---|---|
| B-1 | 子層 CLAUDE.md ×7 的「下沉」句 | 「下沉：深入子目錄 → 讀 `<子目錄>/.claude/code_map.md`（不存在則以本層說明為準）」逐字重複 7 檔 | 刪重複句，root CLAUDE.md L39 已完整說明機制；各層只留「本層結構索引：`.claude/code_map.md`」一行 | grep 實證 7/8 檔同文案 | 低（root 恆載必中） |
| B-2 | code_map ×8 開頭模板教學句 | 「本層索引：只列…直接子項目，一行一項」+「下沉…」每檔重複 | 縮為一行（保留「顆粒：粗/中/細」標註——這是各層有效資訊） | 8 檔首段套同模板 | 極低（格式自明） |
| B-3 | `dispatch.md:40` 自 patch 門檻 | 「超級小」= ≤3 行（同時滿足 5 條件）才可主 agent 自 patch | 放寬至 **≤10 行**：單檔、純值/字串/條件微調、無簽名變動、無跨檔傳播、先 invoke karpathy-guidelines；灰色地帶仍派 | dispatch.md:33-42 原文已驗；門檻為 5 月底對舊 model 的保守設定 | 中（放太寬累積失誤；10 行上限 + 條件不變可控） |
| B-4 | `worktree.md:11` 觸發範圍 | 「編寫/修改**任何** tracked 檔必先 EnterWorktree」（含純文件一行修正） | 分層：`myProgram/`、`.claude/`（hooks/agents/settings）維持強制；`resources/` 純文件**新增**與**小修**可直接 main（git add 明列 + hook 防線仍在） | worktree.md:11 原文已驗；**實務已脫節**——本 session spec 筆誤修正即直接 main Edit+commit，未進 worktree | 中低（main 上文件改壞可 revert；code 類仍強制隔離） |
| B-5 | `sdd.md:105` 三段 reviewer 跳過條件 | 現只有「Mini spec（≤3 行）跳三段」與 Meta-task 例外 | 跳過門檻與 B-3 連動放寬：≤10 行小改 → 跳 spec-reviewer（主 agent 自驗 spec 對照）+ 保留 code-quality-reviewer 或反之擇一；中大改動三段不變 | sdd.md:90/105/120 結構已驗 | 中（審查覆蓋下降；以 Iron Law 自驗補） |

## C. 留觀察組（低信心，不動）

| # | 位置 | 疑點 | 回頭處理的觸發訊號 |
|---|---|---|---|
| C-1 | Iron Law（sdd.md:120） | Agent ③ 建議條件化（信任 sales-coder 回報）；複核：pytest 成本僅數秒、其證據捏造、與驗證優先哲學牴觸 → 不動 | 驗證成本顯著上升（套件 >1 分鐘）才重議 |
| C-2 | pineedtodo 協議（pi-and-structure.md） | append-only 堆積疑慮；實測僅 5 份、Pi 環境已穩定新增少 | 檔數 >15 或使用者回報追蹤困難 |
| C-3 | code_map 巢狀維護 | Agent ③ 建議子層改可選；複核：架構是近期刻意所建、維護成本目前低 → 不動 | 連續 ≥2 次結構變動漏更新 code_map（負擔顯性化） |
| C-4 | Gotcha M 驗證 + 文檔（worktree.md:78-97） | 驗證指令秒級、文檔按需載；「官方已修補」說法無據 | 再 2 個月零發生 + harness changelog 證實修復 → 縮文檔為 NOTES pointer |
| C-5 | sales-dirty 三方協作（3 hooks） | 單支看似 99% 空轉，但為機制必要環 | sales 業務凍結或 flag 誤動作 |
| C-6 | 子層 pytest/SDD 提醒（sales/states/tests 三層） | Agent ② 視為重複；複核：這正是子層 CLAUDE.md「局部慣例」本職、各層按需獨立載入 → 不動 | 子層行數超標或官方指引改變 |
| C-7 | Pi SSH 授權雙載（memory + standard-workflow.md:67）；block-windows-install reason 文案 | 各一句話等級的重複，受眾不同（memory=why、skill=操作） | 該段落再膨脹 |

## D. 確認健康（無需動）

- 10 支 hooks：3 支豁免防線（block-*）+ 6 支健康（session-start-context ~200-400ms 合理、subagent-inject-rules 已於 `4e646c7` 優化、check-traditional-chinese 純警示、sales-dirty 三方、stop-sync-pi 官方模式背書 + log 證實自我修正）。
- CLAUDE.md ×8 全數行數合規（root 55/100、子層 7-9/60）；code_map ×8 無壞 pointer、無結構不符。
- memory ×4 精簡無過時；lean_doc memory 與歷史 spec 非雙重恆載（spec 是歸檔非 context）。
- settings.json 註冊與 script 一一對應，無孤兒。

> 範圍外備註：Agent ④ 兩項「補 pointer」建議（skill 指回 memory）屬加法非瘦身，未納入；如需另案處理。

## E. 使用者裁決紀錄（2026-06-04 核可關）

| 組 | 裁決 |
|---|---|
| A（×2） | **照單執行**（A-1、A-2） |
| B（×5） | 逐項裁決後 **B-1～B-5 全部執行**（B-3 選 ≤10 行非折衷 ≤5；B-5 選跳 spec-reviewer、保 code-quality-reviewer） |
| C（×7） | **確認留觀察**，觸發訊號如 §C |
