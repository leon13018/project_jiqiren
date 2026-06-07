# Harness Watch-list（留觀察項目單一事實來源）

> **重訪節奏**：(1) model 換代——SessionStart hook 自動提醒（state 比對）；(2) 條目自帶觸發訊號出現；(3) 每 ~3 個月整單掃一遍。
> **協議**：判準與處理方式見 skill `reference/harness-evolution.md`。處理後條目改 status（closed + 一行結果），不刪行——留痕防重提。
> 理論依據：harness 每個元件＝對舊 model 弱點的一條賭注，值得壓力測試（`resources/research/agent_self_evolution_research_2026-06-04.md` §2）。

| # | 項目 | 觸發訊號 | 來源 | status |
|---|---|---|---|---|
| W-1 | Iron Law 條件化（信任 sales-coder 回報） | 驗證成本顯著上升（套件 >1 分鐘） | scaffolding audit C-1 | open |
| W-2 | pineedtodo append-only 堆積 | 檔數 >15 或使用者回報追蹤困難 | scaffolding audit C-2 | open |
| W-3 | code_map 巢狀維護成本 | 連續 ≥2 次結構變動漏更新 code_map | scaffolding audit C-3 | open |
| W-4 | Gotcha M 驗證 + 文檔縮編 | 再 2 個月零發生（至 2026-08）+ harness changelog 證實修復 → worktree.md 該段縮編（NOTES 已於 2026-06-07 墓碑化，hook 側殘留在 hooks-gotchas.md #19） | scaffolding audit C-4 | open |
| W-5 | sales-dirty 三方協作 hooks | sales 業務凍結或 flag 誤動作 | scaffolding audit C-5 | open |
| W-6 | 子層 pytest/SDD 提醒重複疑慮 | 子層行數超標或官方指引改變 | scaffolding audit C-6 | open |
| W-7 | memory / skill 雙載（Pi SSH 授權） | — | scaffolding audit C-7 | **closed**（2026-06-06 整併：memory 條目刪除、standard-workflow.md 為唯一權威，commit 79ac6ad） |
| W-8 | block-windows-install reason 文案重複 | 該段落再膨脹 | scaffolding audit C-7 餘項 | open |
| W-9 | stop_hook_active 第二道守衛 | env var 守衛（CLAUDE_REFLECT_CHILD）出現失效案例 | 逆向比對 §4#4 | open |
| W-10 | asyncRewake 升級反思 hook | 本機 CC 驗證支援 `asyncRewake`+`rewakeMessage`，且出現紅線級提議需主動敲醒的需求 | 逆向比對 §4#5 | open |
| W-11 | 反思素材風險排序代替位置截斷 | turn 級 diff 常態超 30 檔 | 逆向比對 §4#6 | open |
| W-12 | 反思「已報未修」去重機制 | adopted-but-recurring 實際發生（同型提議二度出現） | 反思機制設計討論 2026-06-05 | open |
| W-13 | skill 指回 memory 的 pointer | agent 因漏看 memory 內容而犯錯 | scaffolding audit 範圍外備註（Agent ④） | open |
