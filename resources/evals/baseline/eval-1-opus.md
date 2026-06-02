# Baseline transcript — eval 1 (SDD/reviewer cluster), model=opus

> T0 baseline，現行 verbose skill。場景：L4 預算 24→30s 改動該走什麼流程。

## Navigator 回覆

關鍵發現：使用者前提與 code 對不上——code 是 v3 雙計時器（`L4_TOTAL_BUDGET=36s` + `L4_QR_REFRESH_INTERVAL=12s`），`sales-dialog-design.md` 仍記 v2 單一 30s（stale）；無「L4 結帳預算=24s」，唯一 24s 是 `L4_C_CONFIRM_TIMEOUT`（客服 confirm）。

規劃要點：
- 動手前必 AskUserQuestion 對齊「改哪個常數」（客服 confirm 24→30 vs 結帳總預算 36→30）。
- 要不要寫 spec → 要，強制（任何 myProgram/.py 不分規模）。單一常數純值替換→mini spec；改 `L4_TOTAL_BUDGET` 破壞 `36=12×3` 不變式→完整 spec。
- 常數實際在 `myProgram/sales/constants`（l4.py 只 import）→ 改檔可能是 constants 那支。
- 派誰：超級小→主 agent patch（先 invoke karpathy）；完整 spec→派 sales-coder + 三段 reviewer。全程 worktree。
- 驗收：Iron Law（必跑 pytest 看 N passed）；既有 default-value 測試會擋、需同步更新；git branch --contains 驗落 worktree；Pi 端人工驗收倒數；改完更新 stale 的 sales-dialog-design §L4 budget + l4.py docstring。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read 順序：sdd.md → dispatch.md → sales-tts-ux.md → l4.py → sales-dialog-design.md。
- reference→reference 跳轉：sales-tts-ux.md → sales-dialog-design.md（tts-ux 註腳指 L4 budget 權威在 dialog-design）；再回 l4.py 交叉比對發現 v2/v3 矛盾。
- 缺漏：sales-dialog-design §L4 budget 整段 stale 在 v2 30s（code 已 v3 36s）；使用者「24s」前提無法對應唯一常數；constants 定義檔未深讀（實作階段工作）。
