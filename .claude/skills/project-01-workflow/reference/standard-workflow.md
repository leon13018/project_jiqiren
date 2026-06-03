# 標準任務收尾循環（git 收尾 + sync 權威）

> **🎯 何時讀本檔**：本輪有 tracked 檔改動要收尾（status → add → commit → push → sync），或要懂 sync 自動化（Stop hook）/ Pi pycache。

## 目錄
- 觸發 / 不觸發
- 觸發時 5 步
- 為何用 Stop hook 而非 PostToolUse
- Pi 端 pycache stale
- Windows 端工作邊界
- 補充準則

本檔定義 git 收尾**內核**（status → add → commit → push → sync），會內嵌在 [worktree.md](worktree.md) 階段 2/4。差別只在「誰寫」（subagent vs 主 agent）。

> **先 `git status`，乾淨就不做收尾**（沒改檔的輪次不必跑收尾）。

---

## 觸發 / 不觸發

- **觸發**：本輪有 `.gitignore` 之外的檔 modified/new/deleted（`git status` 有 diff）。
- **不觸發**（直接結束本輪）：純聊天 / 解答 / 查資料｜plan mode 還沒動手｜變更全在 ignored 路徑（`resources/presentation/`、`resources/userPrompt/`、`sync_pi.ps1`、`.claude/settings.local.json`、`.claude/worktrees/`）→ `git status` 乾淨｜完全沒改檔。
  > 變更只影響 ignored 路徑 → 仍**告知使用者**「只動了 ignored 檔，沒有 git 變動可同步」。

---

## 觸發時 5 步

1. **`git status` + `git diff`** — 確認範圍與內容。
1a. **（條件性）寫 Pi 端操作說明書**：本輪涉 Pi 端動作 → 新增 `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`（append-only）納入 add；寫完提醒使用者回報成功項。**觸發清單 + 檔名/結構規範見 [pi-and-structure.md](pi-and-structure.md) §Pi 端操作觸發條件 / §pineedtodo。**
1b. **（條件性）結構變動 → 更新 code_map / SKILL.md 路由表**：納入 add。**觸發 + 巢狀判準見 [pi-and-structure.md](pi-and-structure.md) §結構變動維護。**
2. **`git add <具體檔名>`** — 不用 `-A`/`.`（hook 擋），明列避免誤加 ignored / 敏感檔。
3. **`git commit -m "..."`** — 英文簡短 + `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。
4. **`git push origin main`** — push 後本地 `origin/main` ref 即更新。
5. **同步交給 Stop hook**：`stop-sync-pi.ps1` 在本 turn 結束時自動比對 `origin/main` 與 marker，落後就 sync Pi（含清 pycache）並回報 `Pi synced to <sha>`。**不再需要手動跑**。需要 turn 結束前就立即同步（少見）時，可選手動 `& sync_pi.ps1`（PowerShell tool，idempotent no-op）。

---

## 為何用 Stop hook 而非 PostToolUse

**舊 PostToolUse `auto-sync-pi.ps1` 在 background session 觸發非 deterministic**（NOTES gotcha N，Claude Code 端行為、hook 改不掉）。已改用 **Stop hook `stop-sync-pi.ps1`**：官方確認 Stop 在所有 session 類型（含 headless/background）可靠 fire，且靠 `last-synced-commit.marker` 比對 `origin/main` 自我修正（漏掉的 sync 下個 turn 補）。手動 `& sync_pi.ps1` 因此降為可選（需立即同步時）。

---

## Pi 端 pycache stale（sync 時 hook 順手清，理解現象用）

**Rule**：Pi 每次 `git pull` 拉到新 commit 後，必須清光 project 樹下所有 `__pycache__`，避免 Python import 走 stale `.pyc` 跑舊邏輯。**Windows dev 端不必清**（mtime invalidation 自然 work）。

**根因**：Python 用 mtime-based invalidation；`git pull` 把新 `.py` 的 mtime 設成 commit timestamp，若 < 上次 demo 留下的 `.pyc` mtime → Python 認為 source 沒變 → 用 stale `.pyc`（症狀：source/test/simulation 全對，demo 仍跑舊邏輯。手動清：`find . -name __pycache__ -type d -exec rm -rf {} +`）。

**已實作**：`.claude/hooks/auto-sync-pi.ps1` 在 `sync_pi.ps1` 完成後，用**獨立 try/catch** SSH 清 Pi pycache。**關鍵設計**：清理放獨立 try/catch（不與 git pull 同 try）——否則 git progress msg 被當 error 拋出會跳過清理。

**何時值得加清 pycache**：
| 訊號 | 加清理 |
|---|---|
| `git pull` 拉新 commit 後立刻跑代碼（Pi） | ✅ |
| 本機 Edit/Write 寫 source 後重 import | ❌（mtime 自動 invalidate） |
| ff-merge / rebase 後重 import | ❌（mtime = 當下） |
| `git checkout <branch>` 切回舊 branch | ⚠️ 可能踩，暫不加、踩到再加 |

---

## Windows 端工作邊界

**Claude Code 在本專案只負責檔案編輯與 git 管理，不在 Windows 本機跑任何安裝 / 部署。** Why：開發流程 Windows（編輯）→ GitHub（版控）→ Pi（部署執行）；本機非執行環境。

- **可做 ✅**：Read/Write/Edit/Glob/Grep｜git status/diff/log/add/commit/push（經使用者確認）｜WebSearch/WebFetch｜跑 pytest（`python -m pytest tests/sales/`，純測試框架、與 production 無關；pytest 已全域裝為例外）｜`& sync_pi.ps1`｜**Pi 端 git / 同步修復**（fetch / reset / log / status 等唯讀或版控修復指令）可直接 SSH（`ssh pi@raspberrypi.local`，repo `/home/pi/Desktop/project_jiqiren`；使用者 2026-06-03 授權，例：force-push 後 Pi divergence 用 `git reset --hard origin/main` 修）。
- **不做 ❌**：`pip/npm/apt install`、執行專案 .py、啟 dev server｜在 Pi 上跑 / 啟動 production 應用或裝依賴（Pi 是執行環境，實機驗證一律使用者做）｜本機 import/執行依賴廠商 SDK 的 code（必 ImportError）。

---

## 補充準則

- 不確定變更範圍（還在規劃）→ **先停下確認**，不要先 commit。
- `sync_pi.ps1` 失敗 → 先診斷、提修法與使用者確認再改（腳本 gitignored，改動不進 git）。
- SSH 傳 bash 腳本若路徑需 tilde 展開，別在 `[ -d ... ]` 雙引號內用 `~`（不展開），改 `$HOME` / 絕對路徑。

---

**相關 reference**：[worktree.md](worktree.md) / [dispatch.md](dispatch.md) / [pi-and-structure.md](pi-and-structure.md) ｜ hook 細節 `.claude/hooks/NOTES.md`
