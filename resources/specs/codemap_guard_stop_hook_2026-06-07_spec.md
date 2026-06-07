# code_map 強制守門 Stop hook — 設計 spec

> 日期：2026-06-07 ｜ 狀態：設計已批准，待寫 implementation plan
> 觸發：使用者要求「不想靠模型記得，要一個強制偵查並更新 code_map 的機制」。
> 對應 watchlist：W-3（code_map 巢狀維護成本）——本機制落地後 W-3 可 close。

## 問題

巢狀 code_map（root + 各層 `.claude/code_map.md`）目前的維護全靠非確定性防線：

1. **CLAUDE.md / skill 維護原則**（advisory，靠 Claude 自律）。
2. **`codemap-health.ps1`**：只抓「死引用」（索引提到但已不存在的路徑），且**要手動跑**。
3. **stop-reflect**：機率性、只提議。

兩個缺口：「**新增檔案漏登錄**」完全沒人抓；「死引用」健檢沒有自動觸發點。

## 設計決策（已逐項與使用者確認）

| 決策點 | 結論 |
|---|---|
| 更新執行者 | hook 確定性**偵測** + Stop block 強制 **Claude** 補語意（script 寫不出有意義的描述；同 sales-dirty→pytest 守門哲學） |
| 偵測方式 | **Stop 時 git 快照比對**（非 PostToolUse flag）——連 Bash mv/rm、使用者手動建檔都抓得到 |
| 過關條件 | **block 一次**（同變動集第二次 Stop 放行）——「已涵蓋」情境不逼假 edit，不卡死 session |
| 事件範圍 | 新增 + 刪除 + 改名，**並把 codemap-health 死引用健檢併入自動跑** |
| 噪音控制 | hook 內建**排除清單**（glob），預填 append-only / 目錄級描述已涵蓋的路徑 |

## 元件

### 1. State（`.claude/hooks/state/codemap/`，gitignored）

- `last-snapshot.txt`：上次「檢查過關」時的檔案清單（排序、每行一路徑、no-BOM UTF-8）。
- `reminded.txt`：本輪已 block 過的「待處理集合」逐行清單（防無限 block；**包含比對而非 hash**——Claude 被擋後修掉部分項目會使集合縮小，hash 等值會誤擋第二次，「當前 ⊆ 已提醒」才是正確放行語意）。
- `acked-deadrefs.txt`：已提醒過的死引用逐行清單（同一批只擋一次，新死引用才再擋；過關時以當前清單覆寫，修好的自動移出）。

### 2. 新 Stop hook `stop-check-codemap.ps1`

- 事件：`Stop`，無 matcher。第 4 支 stop hook，範本沿用 `stop-check-sales-pytest.ps1`（hardcoded main checkout、UTF-8、fail-open）。
- 邏輯：
  ```
  if $env:CLAUDE_REFLECT_CHILD → exit 0           # 反思 worker 防迴圈（與其他三支一致）
  if 在 worktree（git rev-parse --git-dir ≠ --git-common-dir）→ exit 0   # 見邊界 case
  S  = git -c core.quotePath=false ls-files + status --porcelain 的 untracked   # 自然排除 gitignored
  S  = S 過濾排除清單（見 §3）
  S0 = read last-snapshot.txt（不存在 → 寫入 S，exit 0；首次安裝不回溯）
  C  = diff(S0, S)                                 # 新增/刪除集合（改名 = 刪+增成對，兩邊都需關注）
  D  = codemap-health.ps1 的死引用 errors，扣掉 acked-deadrefs 已提醒過的
  O  = C + D（outstanding）
  if O 空 → 前移 last-snapshot ← S、acked ← 當前死引用全集、清 reminded，exit 0
  if O ⊆ reminded.txt 集合 → 放行：前移 snapshot、ack 死引用、清 reminded，exit 0
  else → 寫 reminded ← O，decision:block，reason 列出 O 具體路徑 + 指示
  ```
- block reason（繁中）指示 Claude：「逐項處理——更新對應層 `code_map.md`，或逐項判定已被現有目錄級描述涵蓋後直接再次收工」。
- log：`.claude/hooks/stop-check-codemap.log`（>1MB 輪轉 `.1`，沿用慣例）。

### 3. 排除清單（hook 內建 glob，確定性規則，可日後增刪）

預填（rationale：append-only 或「目錄級描述已涵蓋、逐檔登錄無意義」）：

- `resources/changelogs/`、`resources/pineedtodo/`、`resources/specs/`、`resources/plans/`、`resources/reviews/`
- `resources/evals/iteration-*/`、`resources/evals/baseline/`
- `**/.claude/code_map.md`（索引本身的新增不觸發——否則「補建子層索引」會再觸發一次 block）

注意：gitignored 路徑（`reflections/`、`presentation/`、`userPrompt/`、`state/`、`worktrees/`、`*.log`）不需列——`git ls-files` + untracked 本來就看不到。

### 4. codemap-health.ps1 重用

- 以子程序呼叫現有腳本（`-RepoRoot` 主 checkout），解析 stdout 的 `❌ 死引用：` 行 + exit code。
- 不改其邏輯；僅需驗證它在 hook 運行時（PowerShell 5.1）下可跑（原註解寫 pwsh）。

## 行為

- **觸發 block**：turn 結束時有未處理的結構變動（排除清單外的新增/刪除）或新死引用 → 擋一次、列清單。
- **放行**：Claude 處理後（或判定已涵蓋）再次收工 → 同 hash → 放行 + 前移 marker。
- **不觸發**：純聊天 / 變動全在排除清單 / 快照無 diff → 靜默前移，近零成本（本地 git + 秒級健檢掃描）。
- **自我修正**：漏掉的 turn（中斷、API error）由下個正常 Stop 吸收——snapshot diff 是累積性的。

## 錯誤處理

- hook 自身任何例外 → `catch { exit 0 }` fail-open，絕不卡死收工。
- codemap-health 呼叫失敗 → 跳過 D（log 記錄），C 照常檢查。
- state 檔損毀（集合比不上）→ 行為退化成「多 block 一次」，無更壞後果。

## 邊界 case

| 情境 | 行為 |
|---|---|
| 首次安裝（snapshot 不存在） | 初始化為當前快照，不回溯歷史，exit 0 |
| worktree session 內 | 跳過（state 不進 worktree、gitignored 檔在 worktree 看不到會誤報死引用）；merge 回 main 後主 checkout 下一輪 Stop 自然抓到全部新檔 |
| block 後 Claude 又新增檔案（如補建子層 code_map） | 索引本身已在排除清單；其他新檔 → 不在已提醒集合 → 再擋一次（正確：是新的未處理變動） |
| add 後同 turn 又刪掉 | snapshot diff 淨值為零 → 不觸發 |
| 切到舊 branch | 檔案集大變 → 擋一次，回 main 後下輪前移吸收（main checkout 切 branch 罕見，可接受） |
| user 中斷（Ctrl-C）/ API error | Stop 不 fire → 下個正常 turn 吸收 |
| 連續 8 次 block cap（官方 stop_hook_active） | 不可能觸及——同變動集最多 block 一次（reminded 集合去重） |

## 連帶文檔更新

- `hooks-system.md`：一覽表加列 + flag 架構段補 codemap state 家族。
- `.claude/` 層（或 root）code_map：登錄新 hook 檔。
- `resources/watchlist.md`：W-3 → closed（一行結果 + 本 spec 路徑）。
- CLAUDE.md「新增 / 移動檔案 → 同步更新 code_map」字句保留（advisory 與 hook 並存，同紅線慣例）。

## 驗證計畫（Iron Law：跑過才算完成）

1. 本地 stdin 模擬，逐案測：無變動（靜默+前移）｜新增檔（block 一次列路徑）｜同狀態第二次 Stop（放行+前移）｜排除清單內新增（靜默）｜死引用（暫時改名一個被索引檔 → block）｜同批死引用第二次（放行）｜worktree 內（跳過）。
2. codemap-health.ps1 在 PowerShell 5.1 實跑一次確認相容。
3. BOM 檢查：新 .ps1 頭 3 byte = `ef bb bf`；state 檔寫入 no-BOM。
4. `/hooks` menu 確認註冊；settings.json 改後重啟 session 保險。
5. 端到端：真實 turn 建一個新檔 → 收工被擋 → 更新 code_map → 再收工放行、marker 前移。

## 實作偏差記錄（2026-06-07 實作完成後 append）

1. **codemap-health.ps1 一行編碼修復（scope 例外，主 agent 授權）**：`-NoProfile` PS 5.1（cp936）下 `Get-Content` 預設編碼誤解碼繁中行 → 幽靈死引用、每個 Stop 誤 block。修法 `Get-Content … -Encoding UTF8`（gotcha #4 同類）；「不改 codemap-health」原意是不改偵測邏輯，編碼防呆不在此限。commit `2d3e544`。
2. **死引用解析只用 stdout、不用 exit code**：§4「+ exit code」未實作——`死引用：` 行存在 ⟺ exit 2，功能等價，以本段修正 spec 文字（不改 code）。匹配錨點後收緊為 `死引用：`（quality review Minor，commit `22cd125`）。
3. **tracked 檔未 stage rename 不產生「刪除」行**：`git ls-files` 對未 stage 的 rename 仍列原檔名 → 快照 diff 只見「新增」；缺失由死引用健檢（filesystem Test-Path）補抓，block 仍如期觸發。行為正確，§驗證計畫的預期輸出以此為準。
4. **block-once 保證的是「必被提醒一次」非「必被解決」**：Claude 被擋後若判定不修，死引用會被 ack、不再重複擋（設計本意，與 sales-dirty 一致）。

## 不做（YAGNI）

- 不做 script 自動改寫 code_map 內容（語意描述只能由 Claude 寫，純清單會降級索引品質）。
- 不做語意「已涵蓋」自動判斷（交給被 block 的 Claude）。
- 不做 `FileChanged`+`watchPaths` 即時觸發（Stop 比對已涵蓋所有來源，含 session 外變動）。
- 不改 codemap-health.ps1 偵測邏輯（只重用；它的「漏登錄反向比對」缺口正是由本 hook 的快照 diff 補上）。
- 不偵測「檔案內容大改但 code_map 描述過時」（語意問題，留給 reflect 機率性抓）。
