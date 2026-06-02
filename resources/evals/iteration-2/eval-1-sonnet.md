# Iteration-2 transcript — eval 1 (SDD/reviewer cluster), model=sonnet

> round-2 去噪後。場景同 baseline eval-1。多模型驗證（spec-reviewer 實際用 sonnet）。

## Navigator 回覆（摘要）
- 載入 `project-01-workflow`，讀 `sdd.md` + `dispatch.md` + `sales-tts-ux.md` + 多層 code_map。
- 正確區分 L4 兩計時器：`L4_TOTAL_BUDGET=36s`（整層）vs `L4_C_CONFIRM_TIMEOUT=24s`（鏈路 C 客服確認，**=使用者要改的**）。確認文案用 `{seconds}` 模板自動帶入、不需手改。
- 規模判定「超級小」（1 行、單檔、純值替換、無簽名/cross-file）→ **Mini SDD spec（5 行單檔）、主 agent 自 patch、不派 sales-coder、豁免三段 reviewer**。
- 流程：對齊 → invoke karpathy → 寫 mini spec → approval → EnterWorktree + commit spec → Edit timing.py + grep test 斷言 → Iron Law `pytest -v` → 收尾 ff-merge/push/手動 sync。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：sdd.md → dispatch.md → sales-tts-ux.md → 4 層 code_map；grep l4.py/timing.py/l4_text.py。
- reference→reference：判「是」——sales-tts-ux 矩陣只寫「L4 service 24s」未標常數名，且其 v3 36s 備註指向 sales-dialog-design，一度以為要再讀那份；最終靠 grep code 確認，未實跳 sales-dialog-design。
- 缺漏：(1) sales-tts-ux 矩陣未標 `service=L4_C_CONFIRM_TIMEOUT` 常數名，問「24s 在哪定義」得 grep code。(2) **⚠️ 矩陣備註「L4 entry budget 60s→30s→v3 36s」歷史脈絡害一度誤以為要改 entry budget**——round-2 去噪標的（cluster 4 sales-tts-ux 待清此歷史敘事）。
