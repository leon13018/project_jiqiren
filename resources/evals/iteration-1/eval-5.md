# Condensed (iteration-1) transcript — eval 5 (dormant/conv cluster), model=opus

> cluster 5 精簡後（bdd-tdd 56 / conventions 60）。場景同 baseline eval-5。

## Navigator 回覆（摘要）
一、要重啟：DORMANT（2026-05-25），「新增 sales 業務邏輯（新優惠規則）」命中重啟條件之一（另一是改 L0-L5 規格書致 prod 動）；不重啟＝純 bug fix/refactor/const 調數字/SDK 整合測試。
二、4 階段鳥瞰（每層獨立、禁跨層）：(1) 主 agent 寫 BDD spec（只註解+空函數 pass，AskUserQuestion 確認）(2) plan mode 規劃 TDD+Impl（ExitPlanMode 審）(3) 派單一 subagent 走 RED-GREEN-REFACTOR（EnterWorktree、塞規範、同一 subagent 連走、git add 明列含 spec 檔）(4) 主 agent 審查 + 自跑 pytest 全綠（Iron Law）+ 收尾。pitfalls：dispatcher ENTRY 禁一次寫完整路由 / DEGRADED-TDD-PARTIAL 僅限 L1-L5 dispatcher 容許（純函式不容許）/ Iron Law 精神（空白模組批次 fail 算守）/ commit 範圍含 spec 檔 / tests 是 regression net 以快照為準 / 選項 C 不 import SDK。
三、繁簡：產出物中文一律繁體（權威 root CLAUDE.md，hook 簡體警示）；適用註解/字串/.md/commit；不適用對話本身；派 subagent 務必塞繁中；繁簡對照表（佇列/執行緒/資料/網路…）；cp936 環境 quirk。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：SKILL.md → bdd-tdd.md → conventions.md（依路由表兩列平行定位）。
- reference→reference：**無被迫跳讀**。bdd-tdd 對流程自成完整（4 階段+pitfall+產出同檔）、conventions 完整覆蓋繁簡；bdd-tdd 末 cross-link（dispatch/worktree/sdd/incremental/vendor）是「實作時才深入」、回答流程+繁簡不需展開。
- 缺漏：本層級無缺漏；規格書/範本檔（業務程式邏輯規劃 L?.md / bdd規範.txt / bdd-寫法範例.txt）未開啟驗證存在（任務只規劃故未查；真重啟時要確認新優惠規則對應哪 L 層）。
