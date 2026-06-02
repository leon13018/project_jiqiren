# Condensed (iteration-1) transcript — eval 1, model=sonnet

> cluster 1 精簡後。場景同 baseline eval-1-sonnet。

## Navigator 回覆（摘要）
- 釐清：L4_TOTAL_BUDGET 現 36（非 30，v3 36=12×3）；唯一 24s 是 L4_C_CONFIRM_TIMEOUT（客服）。動手前確認改哪個。
- 情況 A 改 L4_TOTAL_BUDGET：有不變式 `% L4_QR_REFRESH_INTERVAL==0`（須 12 倍數），改 30 會讓 test_constants 守不變式的 assertion FAIL → 屬架構變更走完整 spec。情況 B 改 L4_C_CONFIRM_TIMEOUT：單一常數純值替換。
- 完整流程（以 B 為例）：mini spec 5 行範本 → self-review 4 點 → AskUserQuestion approval → worktree + 主 agent patch（先 invoke karpathy；但 `{seconds}` 文案若硬編碼需一起改→超門檻則派 sales-coder）→ Iron Law pytest → git 收尾 + sync。
- A 情況升級完整 SDD（更新 L4_v3 spec + docstring + test assertion + 派 sales-coder + 三段 reviewer）。
- 驗收通用：pytest 全綠 / branch --contains worktree-* / sync 成功。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：sdd.md → sales-tts-ux.md → sales-dialog-design.md → dispatch.md → 3 層 code_map → timing.py → L4_v3_dual_timer_spec.md → l4.py。
- reference→reference：sales-tts-ux → sales-dialog-design（§94 指引 + 開頭「矛盾以最新為準」）；timing.py → L4_v3_dual_timer_spec（註解引用 + 發現值 36≠reference 30）。
- 缺漏：sales-dialog-design L4 budget section 是 v2 stale（已按 code v3 為準跳過）。SDD/dispatch 流程資訊齊全。
