# Iteration-2 transcript — eval 5 (dormant/conv cluster), model=opus

> round-2 去噪後（bdd-tdd 去 DORMANT 日期 + DEGRADED「三次實測」+ commit 範圍 episode；conventions 去 cp936/bug-scan 日期戳。/goal 段已於前置 commit 移出 resources/）。場景同 baseline eval-5。

## Navigator 回覆（摘要）
一、要重啟：DORMANT；「新增 sales 業務邏輯（新優惠規則）」命中重啟條件之一（另一是改 L0-L5 規格書致 prod 動）；反例純 bug fix/refactor/const 調數字不重啟（仍跑既有 tests 當回歸網、絕不刪）。
二、4 階段鳥瞰（每層獨立、禁跨層）：(1) 主 agent 寫 BDD spec（只註解+空函數 pass + AskUserQuestion 確認，禁 import prod）(2) plan mode 規劃 TDD+Impl（ExitPlanMode 審）(3) 派單一 subagent 走 RED-GREEN-REFACTOR（EnterWorktree、塞規範、同一 subagent 連走、git add 明列含 spec 檔）(4) 主 agent 審 + 自跑 pytest 全綠（Iron Law）+ 收尾。pitfalls：dispatcher ENTRY 禁一次寫完整路由 / 純函式 prod 嚴格不容許 DEGRADED（容許條款僅限 L1-L5 dispatcher）/ 選項 C 不 import SDK。
三、繁簡：產出物中文一律繁體（適用註解/字串/.md/commit；不適用對話）；派 subagent 務必塞；繁簡對照表（佇列/執行緒/資料/網路…）；cp936 環境 quirk。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：SKILL.md → bdd-tdd.md → conventions.md（路由表兩列平行命中）。
- reference→reference：**否**。兩個正交主題（BDD+TDD 流程 vs 繁簡規範）各自指向不同 reference、各自自足；讀 conventions 是為第二個獨立問題、非為補第一個。
- 缺漏（pre-existing，非去噪造成；baseline 亦標）：(1)「優惠規則」具體落哪層/哪 prod 檔（dispatcher vs 純函式 → 決定容不容許 DEGRADED）需開規格書才知；(2) bdd-tdd 無「新增一條規則到既有 L 層」的微型路徑分級，顆粒度需主 agent 自判。
