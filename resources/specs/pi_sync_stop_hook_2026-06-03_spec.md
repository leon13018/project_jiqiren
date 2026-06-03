# Pi sync 改用 Stop hook 觸發 — 設計 spec

> 日期：2026-06-03 ｜ 狀態：設計已批准，待寫 implementation plan
> 觸發：使用者要求「遠端 Pi sync 目前靠手動判斷，想寫個 hook 更穩定觸發」。

## 問題

目前 Pi sync 有兩層、都不可靠：

1. **`auto-sync-pi.ps1`（PostToolUse/Bash，async）**：偵測 `git push origin main` → 跑 `sync_pi.ps1` + 清 Pi pycache。**但 background session 下 PostToolUse 觸發非確定性**（NOTES gotcha N，Claude Code 端行為、hook 改不掉）。
2. **手動規則**：`standard-workflow.md` 步驟 5「永遠手動跑 `& sync_pi.ps1`」當保險——依賴 agent 記得。

使用者確認痛點「live 與 background **兩種都會**漏 sync」。目標：換一個**不分 session 類型、可靠、自我修正**的觸發點，把「agent 記得手動跑」從迴路裡拿掉。

## 設計決策

採 **Stop hook + last-synced marker，single source of truth**。

- **為何 Stop hook**：官方文檔確認 Stop hook 在所有 session 類型（含 headless/background）都可靠 fire（「When Claude finishes responding」）。gotcha N 的非確定性是 **async PostToolUse** 特有；Stop 是同步事件，不受影響。
- **為何 marker**：讓 turn 結束的檢查極便宜（純本地 `git rev-parse`，無 SSH），且讓機制自我修正（漏掉的 sync 下個 turn 自動補）。
- **為何 single source（移除 auto-sync）**：符合專案 single-source-of-truth 哲學；少一個觸發點、少一份 marker 維護、推理簡單。代價：sync 改在 turn 結束跑（而非 push 後立即），但不會在 turn 中間跑 Pi demo，差幾秒無感。（使用者已在 2 選項中選此案。）

## 元件

### 1. Marker 檔
- 路徑：`.claude/hooks/state/last-synced-commit.marker`（`state/` 已 gitignored）。
- 內容：上次成功 sync 到 Pi 的 `origin/main` commit SHA（單行）。

### 2. 新 Stop hook `stop-sync-pi.ps1`
- 事件：`Stop`，無 matcher（Stop 不支援 matcher）。
- 範本沿用 `stop-check-sales-pytest.ps1`：hardcoded main checkout 路徑、UTF-8 OutputEncoding、fail-safe。
- 邏輯：
  ```
  mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
  pushed   = git -C <mainCheckout> rev-parse origin/main   # push 後本地 remote-tracking ref 已更新
  lastSync = read marker（無檔則空）
  if pushed 空 (無 origin/main ref) → exit 0
  if pushed == lastSync → exit 0          # Pi 已是最新，零 SSH
  else:
      跑 sync 動作（見 §3）
      if sync_pi.ps1 exit==0 → 寫 pushed 進 marker
  exit 0  （永不輸出 decision:block——sync 是 side effect，不阻斷 turn）
  ```
- 比對 `origin/main` 而非 `HEAD`：Pi 是 `git pull` 從 origin 拿，只該同步「已 push 上去」的 commit。本機是唯一 push 來源，故本地 `origin/main` ref 在 push 後即等於遠端。
- **可選**：實際跑了 sync 時，輸出 `{"systemMessage":"✓ Pi synced to <sha7>"}` 給使用者回饋；未 sync 時純靜默。

### 3. Sync 動作（從 auto-sync-pi.ps1 移植，DRY 到 Stop hook 內）
⚠️ **關鍵**：清 Pi `__pycache__` 的邏輯目前在 `auto-sync-pi.ps1`、**不在 `sync_pi.ps1`**。移除 auto-sync 後這段必須搬進 Stop hook，否則退化成跑 stale `.pyc`（NOTES 記載過的坑）。

兩步，各自獨立 try + inline `EAP='Continue'` + `$LASTEXITCODE`（沿用 auto-sync 既有寫法處理 ssh/git stderr 雜訊）：
1. `& sync_pi.ps1`（git pull on Pi）→ 取 exit code，決定是否寫 marker。
2. SSH 清 Pi pycache：`ssh pi@raspberrypi.local "find /home/pi/Desktop/project_jiqiren -name '__pycache__' -type d -exec rm -rf {} +"`（best-effort，失敗不擋 marker 寫入）。
- log 寫 `.claude/hooks/stop-sync-pi.log`（gitignored，`*.log` 已 ignore）。

### 4. 移除 `auto-sync-pi.ps1`
- 刪 `settings.json` PostToolUse/Bash 下的 auto-sync-pi entry（保留同陣列的 `state-clear-on-pytest`）。
- 刪 `.claude/hooks/auto-sync-pi.ps1` 檔。

## 行為

- **觸發 sync**：turn 結束且 `origin/main` 前進到 marker 沒記錄的 commit（即本輪有 push，或前輪 push 漏同步）。
- **不觸發**：純聊天 / 沒 push / Pi 已最新 → 只跑一個本地 `git rev-parse`。
- **自我修正**：任何原因漏掉的 sync，下個 turn 結束自動補（marker 未更新就會重試）。
- **成本**：只有 origin/main 前進的 turn 付 ~3s SSH（與現行手動跑一次同成本）；其餘 turn 近零成本。

## 錯誤處理

- `sync_pi.ps1` 非零 → **不寫 marker** → 下個 turn 自動重試；log 記錄。
- pycache 清理失敗 → 不影響 marker（source 已同步，pycache 是 best-effort）。
- hook 自身解析/執行例外 → `catch { exit 0 }` fail-open，絕不阻斷 turn。
- **force-push 後 Pi divergence**：sync_pi.ps1（`git pull`）會失敗 → 不寫 marker → 每 turn 重試失敗（log 可見）。本 spec 不解此情境；使用者已授權 Pi 端 git 修復可直接 SSH（`git reset --hard origin/main`），屬手動修復範疇。

## 邊界 case

| 情境 | 行為 |
|---|---|
| 首次安裝（marker 不存在） | pushed != 空 → sync 一次 → 寫 marker |
| worktree session 內 push | 共用 .git，本地 origin/main 更新；Stop hook 讀 main checkout 的 ref，照常觸發 |
| 使用者手動跑過 `& sync_pi.ps1` | marker 未更新 → 下個 turn 多一次 idempotent no-op sync（~3s，可接受） |
| 連續多 turn 無 push | 每 turn 一個本地 rev-parse，無 SSH |

## 連帶文檔更新

- `standard-workflow.md`：步驟 5 + 「Background session 雙保險」段 → 改為「Stop hook 自動同步，手動 `& sync_pi.ps1` 降為可選（需立即同步時用）」。
- `.claude/hooks/NOTES.md`：§1 一覽表（移除 auto-sync、新增 stop-sync）、§2 flag pattern（可補 last-synced marker）、gotcha N 標註「已用 Stop hook 繞過」。

## 驗證計畫（Iron Law：跑過才算完成）

1. 本地單測 Stop hook：模擬 stdin，分別測 marker==origin/main（靜默）、marker 落後（觸發 sync 並更新 marker）、marker 不存在（首次 sync）。
2. **background session 實測**：在 background job 內 push，確認 Stop hook 真的 fire 並同步（驗證官方文檔說法、補 NOTES gotcha N 對照）。
3. BOM 檢查：新 .ps1 頭 3 byte = `ef bb bf`。
4. 端到端：改一個小檔 → commit → push → 確認 turn 結束 Pi `git log -1` 前進到新 commit、pycache 已清。

## 不做（YAGNI）

- 不做 async Stop hook（要同步才能可靠寫 marker；~3s 阻塞可接受）。
- 不改 `sync_pi.ps1`（gitignored、使用者所有；pycache 邏輯留在 hook 端）。
- 不處理 force-push divergence 自動修復（手動 SSH 修，已授權）。
- 不保留 auto-sync 作雙層（使用者選 single source）。
