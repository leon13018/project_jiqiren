# 自進化閉環補完 — Spec（2026-06-07）

## 目標

補上 agent 自進化的最後兩個缺口（調研 `agent_self_evolution_research_2026-06-04.md` §11 對照盤點）：

1. **錯誤→eval 閉環**（§11-3，S2「源自真實失敗的 task」+ graduation）：踩雷採納後制度化轉成 eval 場景餵題庫
2. **watch-list 集中 + 重訪節奏**（§11-1，S3「harness 元件＝對舊 model 弱點的賭注」）：散落三處的留觀察項目集中 + model 換代自動提醒

其餘四條啟示已落地：EDD 回歸（§11-2）、generator/grader 分離（§11-4）、memory 精煉（§11-5）、git 回退（§11-6）。

## 設計決策（brainstorm 定案）

| 決策點 | 定案 |
|---|---|
| 主標的 | 兩個缺口一輪做完 |
| 重訪觸發 | SessionStart hook 偵測 model 換代（state 檔比對）+ 條目自帶訊號 + 每 ~3 個月手動 |
| 新場景驗證 | 只跑 3 個新場景（~7 agent，Workflow opt-in 已得） |
| hook 實作策略 | **防禦式**：`$payload.model` 存在才比對、不存在靜默跳過——不依賴官方欄位保證；WebFetch 官方 hooks 文檔僅為 NOTES 記載準確 |

## 元件

### 1. `​.claude/skills/project-01-workflow/reference/harness-evolution.md`（新）

🎯 何時讀：處理反思/整併採納時、要補 eval 場景時、model 換代提醒或 watch-list 訊號出現時。

- **錯誤→eval 轉換三判準**：(a) 行為可從 navigator transcript 客觀判定（assertion 寫得出）(b) 屬協議/skill 層知識（非一次性 bug）(c) 同型錯誤會再發生。符合 → 寫場景進 `resources/evals/scenarios_*.json`
- **graduation**：新場景先跑 EDD 驗證（不誤殺、可判定）才算進回歸題庫——capability→regression 的畢業儀式（S2 §4.2）
- **watch-list 重訪節奏**：單一事實來源 `resources/watchlist.md`；觸發 = model 換代（hook 提醒）/ 條目訊號 / ~3 個月
- SKILL.md 路由表 +1 行

### 2. `resources/watchlist.md`（新，tracked）

收編三處散落項目成單表（# | 項目 | 觸發訊號 | 來源 | status）：

- scaffolding audit §C（C-1 Iron Law、C-2 pineedtodo 堆積、C-3 code_map 巢狀、C-4 Gotcha M 文檔、C-5 sales-dirty 三方、C-6 子層提醒；**C-7 memory/skill 雙載已由 79ac6ad 解決——記 closed**，餘下 block-windows-install 文案部分獨立成條）
- 逆向比對 §4：#4 stop_hook_active（冗餘保險）、#5 asyncRewake（觀察）、#6 風險排序（不急）
- 反思機制「已報未修不去重」設計想法（觸發 = adopted-but-recurring 實際發生）
- scaffolding 範圍外備註：skill 指回 memory 的 pointer 建議（觸發 = agent 漏看 memory 致錯）

檔頭寫重訪節奏 + 指回 harness-evolution.md。EDD verdict 的 pineedtodo 場景建議**本輪以 s7 落實**，不進 watch-list。

### 3. 題庫 +3 場景（`resources/evals/scenarios_workflow_routing.json`）

沿用既有格式 `{id, task, asserts[3]}`：

- **s7-pi-ops-boundary**：Pi 端非 git 操作（清 `__pycache__` / 改設定）——測 SSH 授權邊界（僅限 git/同步修復）vs 寫 pineedtodo；交叉壓測 79ac6ad 升層後的 standard-workflow.md
- **s8-workflow-authoring**：要求把多 agent 流程寫成 dynamic workflow 腳本——測路由到 workflow-authoring.md + args 字串守衛 + 不硬編路徑
- **s9-memory-health**：使用者喊 memory 健檢——測路由到 memory-management.md + script 只報告不改檔 + 人定奪/帳本疫苗

驗證：Workflow 具名觸發 `skill-edd-regression`，args 只帶這 3 場景。

### 4. `​.claude/hooks/session-start-context.ps1` 增量（model 換代偵測）

- 在 `$flagNote` 之後加 `$modelNote` 區塊：`$payload.model` 存在（相容 string 與 `{id}` 物件）→ 與 state 檔 `.claude/hooks/state/last-model.txt` 比對；不同且 state 非空 → 快照尾加「⚠️ model 已換代（X→Y）…建議重訪 resources/watchlist.md」；任何變化都更新 state（UTF-8 無 BOM）
- model 欄位不存在 → 靜默跳過（零行為差異）；state 寫入包 try/catch（提醒功能失敗不能毀快照）
- NOTES.md 同步記載（含官方文檔查證結論）

### 5. 帳本檔頭（gitignored，直接改）

`proposals.md` 與 `memory_ledger.md` 檔頭各加一句：「採納時順問：可否轉 eval 場景？（判準 → skill reference/harness-evolution.md）」

## 驗收

1. hook fixture 四連測（用 powershell.exe 5.1 對齊運行時）：無 model 欄位→無提醒無 state；首次有 model→無提醒、state 建立；同 model→無提醒；換 model→提醒一行 + state 更新。快照其餘輸出不變
2. 3 新場景 EDD 通過（graduation：assertion 可判定、不誤殺；誤殺則修 assert 重跑）
3. watch-list 收編後三處來源逐條對照零遺漏（C-7 記 closed）
4. WebFetch 官方 hooks 文檔，NOTES 記載 model 欄位實況

## 流程約束

- reference + SKILL.md + hook + NOTES → worktree 5 階段；watchlist + 場景 + 帳本檔頭 + code_map → resources/ 或 gitignored 直接 main
- 寫碼前 invoke karpathy-guidelines（每輪實作）
- 順序：resources 先行（hook 提醒指向的 watchlist.md 要先存在）
