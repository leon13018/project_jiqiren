# Harness 自進化（錯誤→eval 閉環 + watch-list 重訪）

> 🎯 **何時讀本檔**：處理反思 / 整併提議的採納時；要把踩雷補成 eval 場景時；session 快照出現「model 已換代」提醒或 watch-list 觸發訊號出現時。

## 錯誤→eval 轉換（採納時順問）

採納一條踩雷（proposals.md / memory_ledger.md 的 adopted 條目）後追問：「可否轉 eval 場景？」三判準**全符**才轉：

1. **可判定**——期望行為能從 navigator transcript 客觀判定（assertion 寫得出、兩位專家會同判 pass/fail）
2. **協議層**——屬 skill / 協議知識（非一次性 code bug；code bug 由 pytest 回歸守）
3. **會再犯**——同型錯誤在未來任務可能重現

符合 → 在 `resources/evals/scenarios_*.json` 加場景（格式 `{id, task, asserts[3]}`，可選 `model`）；assertion 評**產出不評路徑**、客觀可驗。

**Graduation（畢業儀式）**：新場景必須先跑一次 EDD 驗證（具名觸發 `skill-edd-regression`、args 只帶新場景）——assertion 可判定且不誤殺，才算正式進回歸題庫。誤殺 → 修 assert 重跑，不硬塞。

## Watch-list 重訪

- 單一事實來源：`resources/watchlist.md`（散落來源報告為歸檔，不再各自追蹤）。
- 觸發：(1) **model 換代**——SessionStart hook 比對 state 自動提醒（harness 元件＝對舊 model 弱點的賭注，換代＝重押時機）；(2) 條目自帶訊號；(3) 每 ~3 個月整單掃。
- 處理：逐條問「移掉 / 升級會不會出錯」——敢移除過時 scaffolding；條目改 status（closed + 一行結果與 commit），不刪行。
