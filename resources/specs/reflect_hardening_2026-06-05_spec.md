# 反思 hook 強化三項（逆向比對採納 1-3）— Spec

> 日期：2026-06-05 ｜ 狀態：設計已核可（brainstorming 兩題：restore 選 A、輪轉範圍含 stop-sync-pi.log）
> 依據：`resources/research/security_guidance_reverse_comparison_2026-06-05.md` §4 採納清單 1-3。
> 基底：`resources/specs/reflective_stop_hook_2026-06-04_spec.md`（本檔是其增量強化，不重述既有設計）。
> 後續：plan → `resources/plans/reflect_hardening_2026-06-05_plan.md`。

## 1. 目標

修掉手搓反思 hook 與官方藍本比對出的三個真差距：

| # | 差距 | 官方對應 |
|---|---|---|
| 1 | claude 呼叫失敗時該輪素材永久跳過（marker 派發時即前移） | `restore_unreviewed_stop_state()`：失敗回復 state，下輪重審 |
| 2 | 中文檔名在 git diff 輸出為八進位轉義，評審模型看到亂碼 | 全域 `git -c core.quotePath=false`（gitutil.py:29-39） |
| 3 | reflect.log / stop-sync-pi.log 無上限增長 | debug log 1MB 自動輪轉（_base.py:53-71） |

**成功標準**：(1) worker 失敗 → marker 不動 → 下輪 T1 重審同素材；成功（含 NONE）→ marker 前移到擷取時 SHA。(2) 中文檔名以原始 UTF-8 進素材檔。(3) log >1MB 時輪轉成 `.1`（覆蓋舊 `.1`），新 log 重新累積。(4) 既有行為（守衛 / 觸發 / lock / 提示）零迴歸。

## 2. 改動設計

### 改動 1 — marker 成功才前移

- `stop-reflect.ps1`：T1 派發路徑**移除** marker 寫入；`Start-Process` 參數追加 `-MarkerSha ('"{0}"' -f $headSha)`（$headSha = 素材擷取當下 `git rev-parse HEAD`，T1 既有取值）。T2 不傳 MarkerSha。
- `reflect-worker.ps1`：`param()` 加 `[string]$MarkerSha = ''`；claude 呼叫成功（解析出 NONE 或 ≥1 條提議）後、釋放 lock 前，若 `$MarkerSha` 非空 → 寫入 `last-reflected-commit.txt`。失敗 / timeout / 解析異常路徑不寫。
- marker 語意：「最後**成功反思**的 commit」。worker 在跑期間下輪 T1 重複命中由既有 lock 擋（不重複派發）；worker 成功後若 HEAD 已再前移，下輪 T1 正確接 `marker..新HEAD`。

### 改動 2 — quotePath

- `stop-reflect.ps1` 素材收集的全部 git 指令（`status --porcelain`、未提交 diff、`marker..HEAD` 範圍 diff）加 `-c core.quotePath=false`。
- 只加此 flag；官方另兩個隔離 flag（`core.hooksPath=/dev/null`、`core.fsmonitor=false`）不抄——本 repo 無自訂 git hooks，YAGNI。

### 改動 3 — log 輪轉

- 邏輯（inline 3 行，hooks 間無共用 module、依既有慣例各寫一份）：
  寫 log 前 `if (檔案存在 且 Length -gt 1MB) { Move-Item <log> <log>.1 -Force }`。
- 放置：`stop-reflect.ps1` 開頭管 `reflect.log`（每 turn 必跑；worker 不重複檢查）；`stop-sync-pi.ps1` 開頭管 `stop-sync-pi.log`。
- `.gitignore`：現有 `*.log` 不匹配 `*.log.1` → 補一條（實作時確認現行 pattern 再定寫法）。

## 3. 不做清單

- ❌ `stop_hook_active` 第二道守衛（採納清單 #4，冗餘保險，留觀察）。
- ❌ asyncRewake（#5，違反「只提議不打擾」，待欄位支援度驗證另議）。
- ❌ 風險排序截斷（#6，觸發率低）。

## 4. 驗證計畫（Iron Law：逐項跑過才宣告完成）

1. **失敗不前移**：暫改 worker model 為無效值（或以參數注入）手動跑 → claude 失敗 → marker 檔內容不變、log 記錯誤、lock 釋放。
2. **成功前移**：正常 T1 手測 → worker 成功（NONE 亦可）→ marker = 派發時傳入的 SHA。
3. **quotePath**：working tree 造一個中文檔名變動 → 觸發素材收集 → 素材暫存檔內見原始 UTF-8 檔名、無 `\3xx` 轉義。
4. **輪轉**：灌 >1MB 假內容進 reflect.log 與 stop-sync-pi.log → 各跑一次對應 hook → `.1` 出現、原檔重新累積；再跑一次未滿 1MB → 不動。
5. **迴歸**：三 Stop hook 守衛測（`CLAUDE_REFLECT_CHILD=1` 靜默退出）+ 乾淨樹 no-op 測 + BOM 全檔複查。
6. **真實 session 觀察**：下一個有變動 turn，reflect.log 見正常 T1 紀錄。

## 5. 實作與收尾規範

- `.claude/` 改動 → 強制 worktree 5 階段；meta-task → 主 agent 自實作（基底 spec §10 既有例外）。
- PS1 慣例：UTF-8 with BOM（改完逐檔複查）、`-NoProfile`、絕對路徑、try/catch + log；`Start-Process` 路徑參數手動包引號（NOTES §12 踩坑 #6）。
- 完工同步：NOTES.md §12 行為段更新（marker 時機 / quotePath / 輪轉）；基底 spec 加修訂註記。
