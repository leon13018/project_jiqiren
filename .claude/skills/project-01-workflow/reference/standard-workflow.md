# 標準任務收尾循環（滿足條件才做）

> **🎯 何時讀本檔**：本輪有 tracked 檔改動要收尾（git status → add → commit → push → sync），或要處理 Pi sync / pycache。

每次任務若本輪有 **git 會追蹤的檔案**改動，主 agent 必須跑這套 git 收尾循環。本 reference 定義 git 收尾的**內核步驟**（status → add → commit → push → sync），會內嵌在 [`worktree.md`](worktree.md) 階段 2 / 3a-3b（commit）與階段 4（push / sync）內。差別只在「誰寫」——派 subagent 寫 vs 主 agent 自己寫。

> **背景 session 限制**：所有 tracked 檔的編輯都要走 [`worktree.md`](worktree.md) 5 階段（不論派 subagent 或主 agent 自己改純文件 / memory bootstrap）。改 gitignored 檔則不需進 worktree（worktree 看不到該檔）。

> **核心心態（為何不是「每輪都做」）**：很多輪任務只是聊天、查資料、討論方案，沒動任何檔案 → 沒東西可 commit，跑 git / sync 是空操作浪費時間。**正確心態：先判斷本輪有沒有實際產出檔案改動，再決定要不要跑收尾。** 簡單測試法：跑一次 `git status`，乾淨就不做收尾。

---

## 觸發條件

本輪有任何 **git 會追蹤的檔案**改動（即 `.gitignore` 之外的檔案，新增 / 修改 / 刪除皆算）→ 觸發收尾。判斷依據：跑 `git status`，若有 modified / new file / deleted（在 `.gitignore` 之外的範圍）→ 觸發。

### 不觸發 → 直接結束本輪，跳過所有收尾

- 純聊天 / 解答問題 / 上網查資料 / 解釋程式碼
- Plan mode 規劃討論（還沒實際動手寫檔）
- 變更全在 ignored 路徑（`resources/presentation/` PDF、`resources/userPrompt/` 個人 prompt、`sync_pi.ps1`、`.claude/settings.local.json`、`.claude/worktrees/`）→ `git status` 看不到任何 diff
- 完全沒有檔案改動

> 變更只影響 ignored 路徑 → `git status` 乾淨 → 跳過收尾，但**仍要告知使用者**「只動了 ignored 檔案，沒有 git 變動可同步」。

---

## 觸發時依序執行的 5 步

### 1. `git status` + `git diff` — 確認變更範圍與內容

### 1a.（條件性）撰寫 Pi 端操作說明書

若本輪變更涉及 Pi 端動作（觸發清單見 [`pi-and-structure.md`](pi-and-structure.md) §pi-side），主 agent 統整步驟，**新增一個檔**到 `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`（**append-only：既有檔不動、不改、不刪**；檔名 / 內容結構規範見 [`pi-and-structure.md`](pi-and-structure.md) §pineedtodo——**寫新檔前必讀**），納入下一步的 `git add`。

寫完後**提醒使用者回報安裝狀況**（使用者明確回報成功的項目，主 agent 會更新 `resources/requirements/raspberry_pi_setup.md` Pi 已安裝清單；失敗 / 未回報項目絕不寫入）。不觸發直接跳過。

### 1b.（條件性）結構變動 → 更新 code_map / SKILL.md 路由表

若本輪變更改動到專案資料結構（檔案 / 資料夾增刪移 / 改名，包括 gitignored；或修改 `.gitignore`；觸發清單見 [`pi-and-structure.md`](pi-and-structure.md) §結構變動維護）：**結構 → 更新 `.claude/code_map.md`**（skill 內部檔案則更 `SKILL.md` 路由表）。納入下一步的 `git add`。不觸發直接跳過。

### 2. `git add <具體檔名>`

不用 `git add -A` / `git add .`（PreToolUse hook 會擋），明確列檔名避免誤加 ignored / 敏感檔。

### 3. `git commit -m "..."`

英文簡短訊息（對照現有 commit 風格），附 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`。

### 4. `git push origin main`

push 後 PostToolUse hook 會嘗試自動跑 `auto-sync-pi.ps1`（async + 120s timeout）→ SSH 到 Pi `git pull`。但這是「最佳努力」、**不可依賴**（background session 內非 deterministic，見下方專段）。

### 5. 永遠手動跑 `& sync_pi.ps1`

```powershell
& sync_pi.ps1
```

用 PowerShell tool（不要用 Bash tool——`&` 是 PowerShell syntax）。

**統一規則，不分 session 類型**：步驟 4 的 hook 即使偶有自動跑，手動再跑一次也只是 idempotent no-op（git pull → `Already up to date`），~3s SSH latency 成本可接受。省得判斷 session 類型 / 記憶 hook 觸發行為——「下意識手動跑」比「先查 session 類型再決定」更穩，養成 push 後接 sync 的反射。

> 🪝 自動化說明：步驟 4 的 hook 是「最佳努力」、不是依賴；步驟 5 才是收尾保證。失敗 / 重跑 / background-session-skip 細節見 `.claude/hooks/NOTES.md` §6 Gotcha N。

---

## Background session 雙保險（為何步驟 5 永遠手動跑）

**Claude Code background job session 內 PostToolUse hook 觸發行為非 deterministic——有時跑有時不跑，視為不可依賴。**

**判斷 session 類型（每輪 session 啟動時自己 check）：**
- system context 含 `# Background Session` 段 + 提到 `$CLAUDE_JOB_DIR` 路徑 → **background**
- 否則 → **live**

但**不需要靠判斷 session 類型來決定要不要手動 sync**——統一規則就是「永遠手動跑」，理由如上（idempotent no-op、省記憶成本）。判斷類型的 check 僅供理解 hook 為何有時不觸發。

**Why（2026-05-27 實證）：** S3 同步動作 push commit `16a90bd` 後使用者 Pi demo 動作沒出來。檢查發現 Pi HEAD 仍停在上一輪 `028ac3f`——該 push 沒進 `auto-sync-pi.log`。手動 invoke hook script 跑得起來 → 確認 hook script 本身沒問題。同日後續觀察推翻「完全不觸發」的假設：同一個 background session 內三次 push 行為不一致：

| commit | hook 觸發？ |
|---|---|
| `16a90bd`（S3 落地） | ❌ |
| `aae2338`（hook fix） | ❌ |
| `f084aba`（CLAUDE.md docs） | ✅ |

規律未明（command 結構 / timing race / async hook + 120s timeout 互動？均為 hypothesis），未在官方文檔明確記載。Live session hook 通常正常跑，但仍照統一規則手動跑。

**規則層補強位置（已落地）：**
- 本 reference 步驟 5「永遠手動跑」段
- [`worktree.md`](worktree.md) 階段 4 末註
- `.claude/hooks/NOTES.md` Section 6 Gotcha N

**相關：** [pi-and-structure.md](pi-and-structure.md) §git-sync-verify（debug 前先對 Pi HEAD，2026-05-27 此 finding 又踩一次驗證）/ 下方 §Pi 端 pycache stale（手動 sync 同時要清 pycache）。

---

## Pi 端 pycache stale（sync 時 hook 會順手清，理解現象用）

**Rule：** Pi 上每次 `git pull` 拉到新 commit 後，必須主動清光 project 樹下所有 `__pycache__` 目錄，避免 Python import 走 stale `.pyc` 跑舊邏輯。**Windows dev 端不必清**（mtime invalidation 自然 work）。

### 現象（2026-05-27 Pi 實機踩過）

使用者 Pi 端跑 `python3.11 -m myProgram` demo 時，在 L3「請問還有額外需要購買的嗎？」對「沒」回應，看到「不好意思我聽不太懂」（L3_B1_CLARIFY，unclear path）。但：
- `git log -1 --oneline` 顯示 latest commit `f61a497`（含 Wave 3 HP-1「沒」strict_short → 結帳意圖 修補）
- Pi 端 NLU standalone test 跑 `classify_intent("沒", "normal")` 返回**「結帳」**（NLU 邏輯對的）
- 主 agent simulation 跑整段 user 序列 → dialog 走 confirm path（**「您即將結帳，總共 ... 正確嗎？」**）

矛盾：source 對、NLU test 對、simulation 對，但 demo 仍跑舊邏輯。

### 根因

Python 3 對 `.py` source 跟 `.pyc` 用 mtime-based invalidation（PEP 552 後也支援 hash-based 但預設仍 mtime）。Pi `git pull` 把新 commit 的 `.py` 檔 mtime **設成該 commit 的 commit timestamp**（不是 pull 當下時間）。如果 commit timestamp < 上次跑 demo 留下 `.pyc` 的 mtime → Python 認為 source 沒變 → 用 stale `.pyc`。

**驗證**：使用者跑 `find . -name '__pycache__' -type d -exec rm -rf {} +` 清光後重 demo，「沒」立刻走結帳 confirm path ✓。

### How to apply

**Pi 端（已實作）**：`.claude/hooks/auto-sync-pi.ps1` 在 `sync_pi.ps1`（git pull）完成後，用**獨立 try/catch** 跑一條 SSH 清 pycache：

```powershell
try {
    & $syncScript 2>&1 | Out-File ...
    "[...] sync_pi.ps1 completed" | Out-File ...
} catch {
    # git pull 的 stderr progress msg（"From https://..."）會被 PowerShell
    # ($ErrorActionPreference=Stop) 當 ErrorRecord 拋出來這裡，git pull 本身
    # 通常仍成功（這標籤是誤標）。
    "[...] sync_pi.ps1 ERROR: $_" | Out-File ...
}

# **獨立 try/catch**：sync_pi.ps1 即使被誤標 error 也仍要清 pycache
try {
    "[...] Clearing Pi __pycache__ ..." | Out-File ...
    ssh "pi@raspberrypi.local" "find /home/pi/Desktop/project_jiqiren -name '__pycache__' -type d -exec rm -rf {} +" 2>&1 | Out-File ...
    "[...] Pi __pycache__ cleared" | Out-File ...
} catch {
    "[...] Pi __pycache__ clean ERROR: $_" | Out-File ...
}
```

**關鍵設計**：兩個獨立 try/catch——若把清 pycache 放在 `sync_pi.ps1` 同個 try 內，git progress msg 拋出會跳過清理（commit `600a4cc` 第一版踩到，`034846d` 拆獨立修補）。idempotent——沒 pycache 也只是 find 返 0 個結果，cost ~50ms SSH latency。

**Windows dev 端（不必加）**：
- 主 agent 用 Edit/Write 直接寫 source → mtime = 當下系統時間 → 一定 > 之前 pytest 留下的 .pyc → Python invalidate 自動重編 ✓
- git ff-merge 改主 checkout source mtime → 也是當下 → 重編 ✓
- 從未踩過 stale 害 pytest 跑錯邏輯

唯一相關 issue 是 [`worktree.md`](worktree.md) cleanup 階段「Windows 偶 lock `.pyc`」害 `git worktree remove` fail——但那是檔案鎖問題不是 stale 邏輯問題，已有 PowerShell `Remove-Item -Recurse -Force` fallback 處理。

### 判定何時值得加清 pycache 的 hook

| 訊號 | 是否加清理 |
|---|---|
| `git pull` 拉新 commit 後立刻跑代碼 | ✅ 加（Pi 場景） |
| 本機 Edit/Write 寫 source → 重 import | ❌ 不必（mtime 自動 invalidate） |
| ff-merge / rebase → 重 import | ❌ 不必（mtime = 當下） |
| `git checkout <branch>` 切回舊 branch | ⚠️ 可能踩 stale（取決於 git 設定）——暫不加，踩到再加 |

### 歷史 commits

- `600a4cc` 初版（清 pycache 跟 sync_pi.ps1 在同 try）——失敗，從 hook log 看 `>>> Repository exists, pulling latest...` 後直接 `sync_pi.ps1 ERROR:` 進 catch，沒印 `Clearing Pi __pycache__`
- `034846d` 拆獨立 try/catch——成功，log 印兩條 `Clearing` + `cleared`，Pi 端 `find . -name '__pycache__'` 確認空

---

## Windows 端工作邊界（能做 / 不能做）

**Claude Code 在本專案只負責檔案編輯與 git 管理，不要在 Windows 本機執行任何安裝或部署指令。**

**Why：** 使用者的開發流程是 Windows（編輯）→ GitHub（版控）→ Raspberry Pi 4（部署執行）。本機 Windows 不是執行環境，安裝任何套件都沒意義；真正需要套件的是 Pi。SSH 同步腳本 `sync_pi.ps1` 已由使用者測試成功，部署工作流不需要 Claude 介入。

**可做 ✅：**
- Read / Write / Edit / Glob / Grep 專案檔案
- git status / diff / log / add / commit / push（經使用者確認後）
- WebSearch / WebFetch 找解決方案
- **跑 pytest 測試**（`python -m pytest tests/sales/ -v`，2026-05-24 更新）——純測試框架，跟 production 執行環境無關。**僅限 Windows 端的 sales/ unit test，且 sales/ 嚴格不 import 廠商 SDK**
- **全域裝 pytest**（2026-05-24 pytest 例外條，使用者已執行）——純測試框架例外，因為它不影響 production execution。其他套件仍守原規（不 pip / npm / apt）
- **`sync_pi.ps1`**（2026-05-21 授權 / 2026-05-25 起 hook 自動執行）——由 PostToolUse hook 偵測 `git push origin main` 自動觸發；統一規則仍永遠手動補跑（見步驟 5）

**不做 ❌：**
- `pip install`、`npm install`、`apt install`、執行專案 .py、啟動 dev server
- 除 `sync_pi.ps1` 之外的任意 Pi 端 SSH 操作
- 在本機嘗試 import / 執行任何依賴廠商 SDK 的程式碼——那些檔案有 Pi-only 依賴（`pigpio`、`RPi.GPIO`、`BusServoCmd` 等），本機必定 ImportError。實際驗證一律由使用者在 Pi 上執行
- Windows 本機 bash / PowerShell 工具盡量不用，git 操作除外

**Pi 端指令統整：** 所有需要在 Pi 上執行的指令（apt / pip / raspi-config / systemd / 一次性設定）必須統整寫成 `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`（append-only，既有檔不動），詳細規範見 [`pi-and-structure.md`](pi-and-structure.md) §pi-side + [`worktree.md`](worktree.md) 階段 3a。寫完後主 agent 提醒使用者回報安裝狀況；使用者明確回報成功 → 主 agent 更新 `resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單）。失敗 / 未回報項目絕不寫入清單。

---

## 補充行為準則

- 不確定變更範圍（例如還在規劃階段）→ **先停下來跟使用者確認**，不要先 commit。
- 變更只影響 ignored 路徑 → `git status` 乾淨 → 跳過收尾，但**仍要告知使用者**「只動了 ignored 檔案，沒有 git 變動可同步」。
- `sync_pi.ps1` 失敗 → 先診斷錯誤，提出修法後與使用者確認再修腳本（腳本本身 gitignored，改動不進 git）。

### 為何要做（觸發時）

使用者 2026-05-21 明確授權「執行 `sync_pi.ps1`」作為標準任務收尾。這推翻了舊規則「Claude 不執行 sync_pi.ps1」——觸發後**必須完整跑完 5 步**，否則任務不算完成、Pi 上代碼版本會落後。

### 歷史 bug（2026-05-21，已修復）

`sync_pi.ps1` 中 `$REMOTE_PATH = "~/Desktop/..."`，bash 的 `[ -d "$REMOTE_PATH" ]` 引號內 tilde 不展開，導致「repo 已存在」時誤走 clone 分支失敗。已改為絕對路徑 `/home/pi/Desktop/project_jiqiren`。

**教訓：** 透過 SSH 傳 bash 腳本時，路徑若需 tilde 展開，要嘛不要在 `[ -d ... ]` test 裡用雙引號、要嘛改用 `$HOME` / 絕對路徑。這類 cross-shell 變數展開問題，未來修改 `sync_pi.ps1` 或寫類似腳本時需留意。

---

**相關 reference**：[`worktree.md`](worktree.md) / [`dispatch.md`](dispatch.md) / [`pi-and-structure.md`](pi-and-structure.md) / [`CLAUDE.md`](../../../CLAUDE.md)
