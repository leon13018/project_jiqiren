# Condensed (iteration-1) transcript — eval 1, model=opus

> cluster 1 精簡後（sdd 249 / dispatch 145 / examples 45+49）。場景同 baseline eval-1。

## Navigator 回覆（摘要）
- 先釐清前提：code 是 `L4_TOTAL_BUDGET=36`（v3，timing.py:99，非 24/30）；唯一 24s 是 `L4_C_CONFIRM_TIMEOUT`（客服，被 L2/L3/qty 共用）；兩常數都在 timing.py、不在 l4.py（純改值不需動 l4.py）→ 動手前 AskUserQuestion 對齊改哪個。
- 要不要 spec：要（myProgram/.py 強制）。單一純值替換→mini spec（5 行）；改 L4_TOTAL_BUDGET 破壞 36=12×3 不變式 / 連動 docstring → 升級完整 spec。
- 派誰：超級小→主 agent patch（先 invoke karpathy）；沾不變式/多檔註解→派 sales-coder + 三段 reviewer。
- worktree 5 階段；Iron Law（必跑 pytest 看 N passed）；default-value 測試會被打到需同步更新（grep 受影響 test）；branch --contains 驗落 worktree；Pi 手動 sync。
- 標記：sales-dialog-design §L4 budget stale（v2 30s vs code v3 36s）。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：sdd.md → dispatch.md → sales-tts-ux.md → sales-dialog-design.md → timing.py → l4.py（另 Glob/Grep）。
- reference→reference：SKILL 路由表 → sdd + dispatch（判 spec/派誰）；sales-tts-ux → sales-dialog-design（L4 budget，§94 指引）；reference 矛盾 → 回 source code 確認。
- 缺漏：sales-dialog-design L4 budget stale（cluster 4 範圍）；使用者 24s 前提待澄清。SDD/dispatch/worktree 流程資訊**齊全**。
