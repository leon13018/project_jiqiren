# Pi sync Stop hook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development 或 superpowers:executing-plans 逐 task 實作。步驟用 `- [ ]` 追蹤。
> **依據**：spec `resources/specs/pi_sync_stop_hook_2026-06-03_spec.md` + 研究 `resources/research/CC_hooks_automation_best_practices_2026-06-03.md`。

**Goal:** 用 Stop hook（每 turn 結束、所有 session 類型可靠 fire）取代非確定性的 PostToolUse auto-sync，靠 marker 比對 `origin/main` 自我修正地同步 Pi。

**Architecture:** 新增 `stop-sync-pi.ps1`（Stop 事件，exit0 永不 block）；`.claude/hooks/state/last-synced-commit.marker`（gitignored）存上次成功 sync 的 origin/main SHA；落後才跑 `sync_pi.ps1` + 清 Pi pycache，成功才寫 marker。移除 `auto-sync-pi.ps1` 與其 PostToolUse entry。

**Tech Stack:** PowerShell 5.1（UTF-8 BOM + OutputEncoding override）、git、ssh、Claude Code hooks（`.claude/settings.json`）。

> **執行環境鐵則**：本任務改 `.claude/` 下 tracked 檔（hook + settings + docs）→ **必走 worktree**（NOTES §10）。hook 腳本一律 hardcode main checkout 路徑（`C:/Users/LIN HONG/Desktop/Project_01`），故「stdin 模擬單測」在 worktree 內也能跑（讀寫的是 main checkout 的 state / sync_pi.ps1）；但「Stop hook 真的被 Claude Code 觸發」的 live/background 實測，**只能在 merge 回 main + settings reload（重啟 session）後做**（Task 7）。

---

## 檔案結構

| 動作 | 路徑 | 責任 |
|---|---|---|
| Create | `.claude/hooks/stop-sync-pi.ps1` | Stop hook：marker 比對 + 落後才 sync + 寫 marker |
| Modify | `.claude/settings.json` | Stop 陣列加 stop-sync entry；PostToolUse/Bash 移除 auto-sync entry |
| Delete | `.claude/hooks/auto-sync-pi.ps1` | 移除非確定性 PostToolUse sync |
| Modify | `.claude/skills/project-01-workflow/reference/standard-workflow.md` | 步驟 4/5 + Background 段改為 Stop hook 自動同步 |
| Modify | `.claude/hooks/NOTES.md` | §1 表（換 row）、§2（marker pattern）、gotcha N（標已繞過） |
| (runtime) | `.claude/hooks/state/last-synced-commit.marker` | gitignored，hook 自建，不進 repo |

---

## Task 0：進 worktree

- [ ] **Step 1**：依 `project-01-workflow` skill 的 `reference/worktree.md` 階段 1 EnterWorktree（feature 名如 `stop-sync-pi`）。後續所有編輯在 worktree 內。

---

## Task 1：建立 `stop-sync-pi.ps1`

**Files:**
- Create: `.claude/hooks/stop-sync-pi.ps1`

- [ ] **Step 1：寫入腳本**（完整內容如下）

```powershell
# Stop hook：每個 turn 結束時，若 origin/main 已前進到 marker 未記錄的 commit → 自動 sync 到 Pi。
#
# 取代舊 auto-sync-pi.ps1（PostToolUse async，background 觸發非確定性 = NOTES gotcha N）。
# Stop hook 在所有 session 類型（含 headless/background）可靠 fire（官方確認）。
# 自我修正：任何原因漏掉的 sync，下個 turn 結束自動補（marker 未更新就重試）。
#
# 設計：exit 0 always、永不 decision:block（sync 是純 side effect；不阻斷 turn；
#       不受官方「Stop 連續 block 8 次強制 override」cap 影響，不可能 deadlock）。
# marker：.claude/hooks/state/last-synced-commit.marker（gitignored）存上次成功 sync 的 origin/main SHA。
#
# 輸入：stdin JSON（Stop hook；內容用不到，僅 drain）。
# 輸出：log → .claude/hooks/stop-sync-pi.log（gitignored）；實際 sync 成功時 systemMessage 回饋 user。

$ErrorActionPreference = 'Continue'

# PS 5.1 預設 OutputEncoding 為系統 code page（本機 cp936）；輸出 systemMessage 繁中需 UTF-8。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

try {
    # drain stdin（Stop hook 不需內容，但要讀掉避免 broken pipe）
    $null = [Console]::In.ReadToEnd()

    $mainCheckout = 'C:/Users/LIN HONG/Desktop/Project_01'
    $markerFile = Join-Path $mainCheckout '.claude/hooks/state/last-synced-commit.marker'
    $logFile    = Join-Path $mainCheckout '.claude/hooks/stop-sync-pi.log'
    $syncScript = Join-Path $mainCheckout 'sync_pi.ps1'

    # 當前已 push 到遠端的 commit（push 後本地 origin/main remote-tracking ref 即更新；worktree 共用 ref store）
    $pushed = (& git -C $mainCheckout rev-parse origin/main 2>$null)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($pushed)) {
        exit 0   # 無 origin/main ref（如剛 clone 未 push）→ 不做事
    }
    $pushed = $pushed.Trim()

    # 上次成功 sync 的 commit（防禦性去 BOM + trim）
    $lastSync = ''
    if (Test-Path $markerFile) {
        $raw = Get-Content $markerFile -Raw -Encoding utf8 -ErrorAction SilentlyContinue
        if ($null -ne $raw) { $lastSync = $raw.TrimStart([char]0xFEFF).Trim() }
    }

    if ($pushed -eq $lastSync) {
        exit 0   # Pi 已是最新 → 零 SSH（純聊天 / 無 push 的 turn 走這條）
    }

    # --- origin/main 落後於 marker → 跑 sync ---
    if (-not (Test-Path $syncScript)) {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync_pi.ps1 not found at $syncScript" | Out-File -FilePath $logFile -Append -Encoding utf8
        exit 0
    }

    $logDir = Split-Path $logFile -Parent
    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
    "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] origin/main=$pushed marker=$lastSync -> syncing" | Out-File -FilePath $logFile -Append -Encoding utf8

    # 跑 sync_pi.ps1（Pi git pull）。inline EAP=Continue 處理 ssh/git stderr 雜訊，靠 $LASTEXITCODE 判斷成敗。
    $eapBackup = $ErrorActionPreference
    $syncExit = 1
    try {
        $ErrorActionPreference = 'Continue'
        & $syncScript 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
        $syncExit = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $eapBackup
    }

    if ($syncExit -eq 0) {
        # 清 Pi __pycache__（best-effort，獨立 try，失敗不影響 marker；避免 stale .pyc 攔截 latest source）
        try {
            $ErrorActionPreference = 'Continue'
            ssh "pi@raspberrypi.local" "find /home/pi/Desktop/project_jiqiren -name '__pycache__' -type d -exec rm -rf {} +" 2>&1 | Out-File -FilePath $logFile -Append -Encoding utf8
        } catch {
        } finally {
            $ErrorActionPreference = $eapBackup
        }
        # 只有 sync 成功才寫 marker（失敗 → marker 不動 → 下個 turn 自動重試）。no-BOM 寫入避免 SHA 比對受 BOM 干擾。
        [System.IO.File]::WriteAllText($markerFile, $pushed, (New-Object System.Text.UTF8Encoding $false))
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] synced ok, marker=$pushed" | Out-File -FilePath $logFile -Append -Encoding utf8
        # 回饋 user（exit 0 + systemMessage；非 decision，不阻斷 turn）
        $sha7 = $pushed.Substring(0, [Math]::Min(7, $pushed.Length))
        (@{ systemMessage = "Pi synced to $sha7" } | ConvertTo-Json -Compress)
    } else {
        "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] sync exit=$syncExit, marker NOT updated (下個 turn 重試)" | Out-File -FilePath $logFile -Append -Encoding utf8
    }
    exit 0
} catch {
    exit 0   # fail-open：任何例外都不阻斷 turn
}
```

- [ ] **Step 2：補 UTF-8 BOM**（Write 工具寫的 .ps1 無 BOM，PS 5.1 讀含中文會 parse error — NOTES gotcha A）

Run（在 worktree 根目錄）:
```bash
f=".claude/hooks/stop-sync-pi.ps1"
python -c "import io,sys; p=sys.argv[1]; d=open(p,encoding='utf-8').read(); open(p,'w',encoding='utf-8-sig',newline='').write(d)" "$f"
head -c 3 "$f" | od -An -tx1
```
Expected: `ef bb bf`

> 註：用 Python 補 BOM 避免 PS `Set-Content -Encoding UTF8` 在 pwsh7 反而洗掉 BOM（NOTES gotcha B 補充）。或用 NOTES §6.A 的 `WriteAllText`+`UTF8Encoding $true` 一行。

- [ ] **Step 3：單測 A — 已最新 → 靜默**（marker == origin/main，預期零輸出、無 sync）

Run:
```bash
MAIN="/c/Users/LIN HONG/Desktop/Project_01"
PUSHED=$(git -C "$MAIN" rev-parse origin/main)
mkdir -p "$MAIN/.claude/hooks/state"
printf '%s' "$PUSHED" > "$MAIN/.claude/hooks/state/last-synced-commit.marker"
echo '{"hook_event_name":"Stop"}' | powershell -NoProfile -File "$MAIN/.claude/hooks/stop-sync-pi.ps1"; echo "[exit=$?]"
```
Expected: 無任何 stdout，`[exit=0]`（marker 已等於 origin/main → 早退，不 SSH）。

- [ ] **Step 4：單測 B — 落後 → 觸發 sync + 寫 marker**（marker 設成假 SHA）

Run:
```bash
MAIN="/c/Users/LIN HONG/Desktop/Project_01"
printf '0000000000000000000000000000000000000000' > "$MAIN/.claude/hooks/state/last-synced-commit.marker"
echo '{"hook_event_name":"Stop"}' | powershell -NoProfile -File "$MAIN/.claude/hooks/stop-sync-pi.ps1"; echo "[exit=$?]"
echo "marker now: $(cat "$MAIN/.claude/hooks/state/last-synced-commit.marker")"
echo "origin/main: $(git -C "$MAIN" rev-parse origin/main)"
tail -5 "$MAIN/.claude/hooks/stop-sync-pi.log"
```
Expected: stdout 一行 `{"systemMessage":"Pi synced to <sha7>"}`；`[exit=0]`；marker == origin/main；log 有 `synced ok`。（這會對 Pi 跑一次真實 idempotent sync，正常。）

- [ ] **Step 5：單測 C — marker 不存在 → 首次 sync**

Run:
```bash
MAIN="/c/Users/LIN HONG/Desktop/Project_01"
rm -f "$MAIN/.claude/hooks/state/last-synced-commit.marker"
echo '{"hook_event_name":"Stop"}' | powershell -NoProfile -File "$MAIN/.claude/hooks/stop-sync-pi.ps1"; echo "[exit=$?]"
echo "marker created: $(cat "$MAIN/.claude/hooks/state/last-synced-commit.marker" 2>/dev/null || echo MISSING)"
```
Expected: 觸發 sync，`[exit=0]`，marker 被建立 = origin/main。

- [ ] **Step 6：Commit**

```bash
git add .claude/hooks/stop-sync-pi.ps1
git commit -m "feat(hooks): add stop-sync-pi.ps1 (Stop hook reliable Pi sync via marker)"
```

---

## Task 2：settings.json — 註冊 stop-sync + 移除 auto-sync

**Files:**
- Modify: `.claude/settings.json`

- [ ] **Step 1：Stop 陣列加入 stop-sync entry**

把 `Stop` 區塊（目前只有 stop-check-sales-pytest 一個 group）改為兩個 group：
```json
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell",
            "args": ["-NoProfile", "-File", "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop-check-sales-pytest.ps1"]
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "powershell",
            "args": ["-NoProfile", "-File", "${CLAUDE_PROJECT_DIR}/.claude/hooks/stop-sync-pi.ps1"]
          }
        ]
      }
    ]
```

- [ ] **Step 2：PostToolUse/Bash 移除 auto-sync entry**（保留 state-clear-on-pytest）

把 PostToolUse 的 Bash group（目前含 auto-sync-pi + state-clear-on-pytest 兩個 hook）改為只剩 state-clear：
```json
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "powershell",
            "args": ["-NoProfile", "-File", "${CLAUDE_PROJECT_DIR}/.claude/hooks/state-clear-on-pytest.ps1"]
          }
        ]
      },
```

- [ ] **Step 3：驗證 JSON 合法**

Run:
```bash
python -c "import json,sys; json.load(open(sys.argv[1])); print('OK')" "/c/Users/LIN HONG/Desktop/Project_01/.claude/settings.json"
```
Expected: `OK`（無 trailing comma / 語法錯）。

- [ ] **Step 4：Commit**

```bash
git add .claude/settings.json
git commit -m "feat(hooks): register stop-sync-pi, remove PostToolUse auto-sync"
```

---

## Task 3：刪除 `auto-sync-pi.ps1`

**Files:**
- Delete: `.claude/hooks/auto-sync-pi.ps1`

- [ ] **Step 1：刪檔並 commit**

```bash
git rm .claude/hooks/auto-sync-pi.ps1
git commit -m "chore(hooks): remove obsolete auto-sync-pi.ps1 (superseded by stop-sync-pi)"
```
> 註：`.claude/hooks/auto-sync-pi.log`（gitignored）留著當歷史，不刪。

---

## Task 4：更新 `standard-workflow.md`

**Files:**
- Modify: `.claude/skills/project-01-workflow/reference/standard-workflow.md`

- [ ] **Step 1：改步驟 4 + 5**

old:
```
4. **`git push origin main`** — push 後 PostToolUse hook 會「嘗試」自動跑 `auto-sync-pi.ps1`（async，最佳努力、**不可依賴**）。
5. **永遠手動跑 `& sync_pi.ps1`**（PowerShell tool，非 Bash——`&` 是 PS 語法）。即使 hook 自動跑過，手動再跑只是 idempotent no-op（`Already up to date`，~3s）。
```
new:
```
4. **`git push origin main`** — push 後本地 `origin/main` ref 即更新。
5. **同步交給 Stop hook**：`stop-sync-pi.ps1` 在本 turn 結束時自動比對 `origin/main` 與 marker，落後就 sync Pi（含清 pycache）並回報 `Pi synced to <sha>`。**不再需要手動跑**。需要 turn 結束前就立即同步（少見）時，可選手動 `& sync_pi.ps1`（idempotent no-op）。
```

- [ ] **Step 2：改「Background session 雙保險」段**

old（整段）:
```
## Background session 雙保險（為何步驟 5 永遠手動）

**Claude Code background job session 內 PostToolUse hook 觸發非 deterministic——有時跑有時不跑，視為不可依賴**（同一 background session 內多次 push，hook 可能只觸發其中一次）。統一規則「**永遠手動跑**」省得判斷 session 類型（idempotent no-op、~3s）。
```
new:
```
## 為何用 Stop hook 而非 PostToolUse

**舊 PostToolUse `auto-sync-pi.ps1` 在 background session 觸發非 deterministic**（NOTES gotcha N，Claude Code 端行為）。已改用 **Stop hook `stop-sync-pi.ps1`**：官方確認 Stop 在所有 session 類型（含 headless/background）可靠 fire，且靠 marker 自我修正（漏掉的 sync 下個 turn 補）。手動 `& sync_pi.ps1` 因此降為可選。
```

- [ ] **Step 3：改目錄列**

把目錄裡 `- Background session 雙保險（為何永遠手動 sync）` 改為 `- 為何用 Stop hook 而非 PostToolUse`。

- [ ] **Step 4：Commit**

```bash
git add .claude/skills/project-01-workflow/reference/standard-workflow.md
git commit -m "docs(workflow): sync 改由 Stop hook 自動觸發，手動降為可選"
```

---

## Task 5：更新 `.claude/hooks/NOTES.md`

**Files:**
- Modify: `.claude/hooks/NOTES.md`

- [ ] **Step 1：§1 一覽表 — 換 row**

移除 auto-sync row：
```
| `auto-sync-pi.ps1` | PostToolUse (async, 120s) | Bash | `git push origin main` 後自動跑 sync_pi.ps1 | 中（log 偶寫 ERROR 但功能正常，見 §6）|
```
新增 stop-sync row（放在 stop-check 附近）：
```
| `stop-sync-pi.ps1` | Stop | (無 matcher) | 每 turn 結束比對 origin/main vs marker，落後則 sync Pi + 清 pycache，成功寫 marker | 中（同步阻塞 turn end ~3s，僅落後時）|
```

- [ ] **Step 2：§1 settings.json 結構圖更新**

PostToolUse/Bash 移除 auto-sync；Stop 加 stop-sync：
```
PostToolUse:
  Bash → [state-clear-on-pytest]
  Edit|Write → [state-mark-sales-dirty, check-traditional-chinese]
Stop:
  → [stop-check-sales-pytest, stop-sync-pi]
```

- [ ] **Step 3：gotcha N 標註已繞過**

在 §6 gotcha N 標題下加一行：
```
**✅ 2026-06-03 已繞過**：sync 改用 Stop hook（`stop-sync-pi.ps1`）觸發——Stop 在所有 session 類型可靠 fire，不受本 gotcha（async PostToolUse 非確定性）影響。本 gotcha 記錄保留作歷史 + auto-sync 移除前的背景。
```

- [ ] **Step 4：§2 補 last-synced marker pattern（簡述）**

在 §2 末尾加一小段，說明 stop-sync 用 `last-synced-commit.marker` 存 origin/main SHA、比對落後才 sync、成功才更新（自我修正），與 sales-dirty flag 同屬 state/ flag-file 架構。

- [ ] **Step 5：Commit**

```bash
git add .claude/hooks/NOTES.md
git commit -m "docs(notes): NOTES 反映 stop-sync 取代 auto-sync + gotcha N 標已繞過"
```

---

## Task 6：worktree 收尾（merge 回 main + push + sync）

- [ ] **Step 1**：依 `worktree.md` 階段 3-4：worktree 內驗證乾淨 → ff-merge 回 main checkout → `git push origin main`。
- [ ] **Step 2**：push 後**手動** `& sync_pi.ps1`（此刻 stop-sync 尚未在 main 的 settings 生效 / session 未 reload，故仍手動一次）。
- [ ] **Step 3**：依 `worktree.md` 階段 5 cleanup worktree。

---

## Task 7：merge 後 live + background 實測（Stop hook 真的觸發）

> 只能在 Task 6 merge + **重啟 session**（讓 main 的 settings.json 載入 stop-sync）後做。

- [ ] **Step 1：`/hooks` 確認註冊** — Stop 事件下應見 stop-check-sales-pytest + stop-sync-pi 兩個。

- [ ] **Step 2：live turn 實測** — 做一個小 tracked 改動 → commit → push（**不手動 sync**）→ 讓 turn 結束 → 觀察是否出現 `Pi synced to <sha>` systemMessage。

Run（驗證 Pi 前進）:
```
! ssh pi@raspberrypi.local "cd /home/pi/Desktop/project_jiqiren && git log -1 --oneline"
```
Expected: Pi HEAD == 剛 push 的 commit；`stop-sync-pi.log` 有 `synced ok`。

- [ ] **Step 3：background session 實測**（補 NOTES gotcha N 對照）— 在 background job 內 push 一個小 commit，turn 結束後確認 Pi 同步、log 有對應 entry。記錄結果到 NOTES（Stop hook 在 background 是否如官方所說可靠 fire）。

- [ ] **Step 4：純聊天 turn 零成本確認** — 一個沒 push 的 turn 結束，確認 `stop-sync-pi.log` 無新 entry（marker == origin/main → 早退）。

- [ ] **Step 5**：若 background 實測證實可靠，於 NOTES gotcha N 補一句實證；若不可靠，記錄並評估是否保留 auto-sync 作 background 補強（回頭找使用者討論）。

---

## Self-Review（對照 spec）

- **spec §2 Stop hook 邏輯** → Task 1 完整實作（origin/main 比對、exit0 無 block、pushed 空早退）✓
- **spec §3 sync + pycache** → Task 1 腳本含 sync_pi.ps1 + pycache SSH（從 auto-sync 移植）✓
- **spec §4 移除 auto-sync** → Task 2 Step 2 + Task 3 ✓
- **spec §5 錯誤處理**（sync 失敗不寫 marker / fail-open）→ Task 1 腳本 `if syncExit -eq 0` + `catch{exit 0}` ✓
- **spec §邊界 case**（首次/worktree/手動/interrupt）→ Task 1 Step 3-5 測首次與已同步；worktree 由 hardcode 路徑處理；interrupt 為 runtime 自我修正（Task 7 Step 4 旁證）✓
- **spec §連帶文檔** → Task 4（standard-workflow）+ Task 5（NOTES）✓
- **spec §驗證計畫**（含 /hooks、background、timeout/async）→ Task 7 + Task 1 腳本未設 timeout/async ✓
- **marker gitignored** → state/ 已在 .gitignore，marker 不進 repo、無需改 gitignore ✓
- Placeholder scan：無 TBD/TODO，腳本與指令完整 ✓
- 型別/命名一致：marker 路徑、變數名（$pushed/$lastSync/$markerFile）全 task 一致 ✓
