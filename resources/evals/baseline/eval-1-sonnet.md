# Baseline transcript — eval 1 (SDD/reviewer cluster), model=sonnet（多模型對照）

> T0 baseline，現行 verbose skill。場景同 eval-1-opus。

## Navigator 回覆

現況釐清：`timing.py` `L4_TOTAL_BUDGET=36`（v3，2026-05-31 從 v2 30s 改，36=12×3）；唯一 24s 是 `L4_C_CONFIRM_TIMEOUT`（客服 confirm）。建議先確認改哪個常數；下列流程兩種皆適用。

規劃要點：
- 規模判定：依 dispatch.md「超級小」定義，純值替換偏超級小，但 cross-file propagation（l4.py docstring 引用 + L4_v3 spec 的 36=12×3 說明）一旦牽動就超標 → 保守傾斜按「中小」派 sales-coder（引歷史案例 7661f10）。
- 要不要 spec → 要，SDD 強制。mini spec 5 行範本（給了範例）；若連動 docstring/倍數關係→完整版。
- 完整 SDD 4 階段流程（對齊+spec→實作 A 主 agent patch / B 派 sales-coder→Iron Law+spec-reviewer→code-quality-reviewer→3c 結構→收尾）。
- 驗收表：pytest 全綠 / branch --contains / diff --stat / Pi 端倒數人工驗收。
- side-effect：30 破壞 36=12×3（30=12×2.5，最後循環只 6s）；L4_v3_dual_timer_spec.md 狀態「規劃中」需 append 變更。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：sdd.md → sales-tts-ux.md → dispatch.md → sales-dialog-design.md(前100) → L4_v3_dual_timer_spec.md(前50)（另 Grep l4.py / timing.py）。
- reference→reference：SKILL 路由表分別帶到 4 個 reference；sales-dialog-design → L4_v3_dual_timer_spec（確認 spec 狀態）。
- 缺漏：「24s」來源不明確；L4_v3 spec 標「規劃中」但 code 已 36s 落地，狀態欄未更新落差。

> 註：sonnet 版同樣正確抓到 v2/v3 與常數歧義，導航與 opus 一致（路由表足夠）。
