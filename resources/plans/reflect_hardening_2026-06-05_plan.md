# 反思 hook 強化三項 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修掉反思 hook 三差距——marker 成功才前移（失敗不丟素材）、git 素材 quotePath=false（中文檔名不亂碼）、log 1MB 輪轉。

**Architecture:** 全部是 `.claude/hooks/` 既有兩檔（stop-reflect.ps1 / reflect-worker.ps1）+ stop-sync-pi.ps1 + .gitignore 的小幅 Edit；無新檔、無新依賴。spec → `resources/specs/reflect_hardening_2026-06-05_spec.md`。

**Tech Stack:** PowerShell 5.1（hook 端）。鐵則：每次 Edit 後逐檔複查 UTF-8 BOM（EF BB BF）；`.claude/` 改動全程在 worktree。

**驗證哲學：** hook 是 PS1 非 pytest 範疇——每步用「手測指令 + 預期輸出」代替單元測試（沿用基底 plan 慣例）。測試跑的是 **worktree 副本**，但 hook 內 `$mainCheckout` 錨定主 checkout，state / git 讀寫都打主 checkout（與既有手測慣例一致）。

---

### Task 0: 進 worktree

- [ ] **Step 0.1:** `EnterWorktree(name="reflect-hardening")` → cwd 切到 `.claude/worktrees/reflect-hardening/`，以下所有 Edit 都對 worktree 內檔案。

---

### Task 1: log 輪轉（改動 3）

**Files:**
- Modify: `.claude/hooks/stop-reflect.ps1`（常數區後、try 前）
- Modify: `.claude/hooks/stop-sync-pi.ps1`（`$logFile` 定義後）
- Modify: `.gitignore`（第 3 行後）

- [ ] **Step 1.1: stop-reflect.ps1 插入輪轉**——在 `$workerPath = Join-Path $mainCheckout '.claude/hooks/reflect-worker.ps1'` 之後、`try {` 之前插入：

```powershell

# ── log 輪轉：>1MB 改名 .1（覆蓋舊 .1；仿官方 security-guidance _base.py 1MB rotate）──
$logFile = Join-Path $mainCheckout '.claude/hooks/reflect.log'
if ((Test-Path $logFile) -and ((Get-Item $logFile -ErrorAction SilentlyContinue).Length -gt 1MB)) {
    Move-Item $logFile ($logFile + '.1') -Force -ErrorAction SilentlyContinue
}
```

- [ ] **Step 1.2: stop-sync-pi.ps1 插入輪轉**——在 `$logFile    = Join-Path $mainCheckout '.claude/hooks/stop-sync-pi.log'` 之後插入（注意在 try 內，縮排 4 空格）：

```powershell
    if ((Test-Path $logFile) -and ((Get-Item $logFile -ErrorAction SilentlyContinue).Length -gt 1MB)) {
        Move-Item $logFile ($logFile + '.1') -Force -ErrorAction SilentlyContinue
    }
```

- [ ] **Step 1.3: .gitignore 補 `.1`**——`.claude/hooks/*.log` 那行之後加一行：

```
.claude/hooks/*.log.1
```

- [ ] **Step 1.4: 驗證輪轉**（對主 checkout 的 log 灌假內容，跑 worktree 副本 hook）：

```powershell
$main = 'C:\Users\LIN HONG\Desktop\Project_01'
$wt   = "$main\.claude\worktrees\reflect-hardening"
# 備份真 log 再灌 1.1MB
Copy-Item "$main\.claude\hooks\reflect.log" "$env:TEMP\reflect.log.bak" -ErrorAction SilentlyContinue
[System.IO.File]::AppendAllText("$main\.claude\hooks\reflect.log", ('x' * 1200000))
'{"session_id":"rot-test"}' | powershell -NoProfile -File "$wt\.claude\hooks\stop-reflect.ps1"
"rotated = " + (Test-Path "$main\.claude\hooks\reflect.log.1")
"new log exists = " + (Test-Path "$main\.claude\hooks\reflect.log")
```
預期：`rotated = True`；新 log 不存在或很小（rotation 後由後續寫入重建）。**測完還原**：`Move-Item "$env:TEMP\reflect.log.bak" "$main\.claude\hooks\reflect.log" -Force`，刪 `.log.1`。注意此測會使 turn-count +1，測完把 `turn-count.txt` 減回。stop-sync-pi.log 同法測一次（其 stdin 同樣 echo JSON 即可；marker=HEAD 時 no-op 不影響）。

- [ ] **Step 1.5: BOM 複查 + commit**

```powershell
# BOM 檢查（無輸出=齊）
Get-ChildItem "$wt\.claude\hooks\*.ps1" | ForEach-Object { $b=[System.IO.File]::ReadAllBytes($_.FullName)[0..2]; if (-not($b[0]-eq 0xEF -and $b[1]-eq 0xBB -and $b[2]-eq 0xBF)){"NO-BOM: $($_.Name)"} }
git add .claude/hooks/stop-reflect.ps1 .claude/hooks/stop-sync-pi.ps1 .gitignore
git commit -m "feat(hooks): rotate reflect/sync logs at 1MB"
```

---

### Task 2: quotePath（改動 2）

**Files:**
- Modify: `.claude/hooks/stop-reflect.ps1`（T1 素材收集的三個 git 呼叫）

- [ ] **Step 2.1: 三個 git 呼叫加 flag**（Edit 三處，舊→新）：

```powershell
# (1) status
$statusOut = (& git -C $mainCheckout status --porcelain 2>$null)
# →
$statusOut = (& git -C $mainCheckout -c core.quotePath=false status --porcelain 2>$null)

# (2) 範圍 diff
$parts += ((& git -C $mainCheckout diff "$marker..$head" 2>$null) | Select-Object -First $DIFF_CAP_LINES | Out-String)
# →
$parts += ((& git -C $mainCheckout -c core.quotePath=false diff "$marker..$head" 2>$null) | Select-Object -First $DIFF_CAP_LINES | Out-String)

# (3) 未提交 diff
$parts += ((& git -C $mainCheckout diff 2>$null) | Select-Object -First $DIFF_CAP_LINES | Out-String)
# →
$parts += ((& git -C $mainCheckout -c core.quotePath=false diff 2>$null) | Select-Object -First $DIFF_CAP_LINES | Out-String)
```
（`rev-parse HEAD` 不輸出路徑，不加。）

- [ ] **Step 2.2: 驗證中文檔名**——在主 checkout 造一個中文檔名 tracked 變動（用已 tracked 的中文檔最穩；若無，臨時 `git add -N` 一個新檔即可入 status）：

```powershell
$main = 'C:\Users\LIN HONG\Desktop\Project_01'
"測試" | Out-File "$main\resources\中文檔名測試.md" -Encoding utf8
& git -C $main -c core.quotePath=false status --porcelain   # 應顯示原始中文
& git -C $main status --porcelain                           # 對照組：應顯示 "\344\270\xxx" 轉義
Remove-Item "$main\resources\中文檔名測試.md"
```
預期：加 flag 的輸出見原始「中文檔名測試.md」；不加的見八進位轉義（證明 flag 必要且有效）。
（不必跑完整 stop-reflect——素材寫入只是把這些指令的輸出原樣落檔。）

- [ ] **Step 2.3: BOM 複查 + commit**

```powershell
git add .claude/hooks/stop-reflect.ps1
git commit -m "feat(hooks): core.quotePath=false so Chinese filenames reach reviewer raw"
```

---

### Task 3: marker 成功才前移（改動 1）

**Files:**
- Modify: `.claude/hooks/stop-reflect.ps1`（移除派發時 marker 寫入；dispatch 參數加 MarkerSha）
- Modify: `.claude/hooks/reflect-worker.ps1`（param + 成功後寫 marker）

- [ ] **Step 3.1: stop-reflect.ps1 移除派發時前移**——刪掉 T1 素材區尾的這行：

```powershell
            if ($head) { [System.IO.File]::WriteAllText($markerFile, $head, [System.Text.UTF8Encoding]::new($false)) }
```

- [ ] **Step 3.2: dispatch 改條件式參數陣列**——把整段 Start-Process 替換：

```powershell
        # ⚠️ Start-Process 的 ArgumentList 不自動加引號——路徑含空白（LIN HONG）必須手動包 "
        # MarkerSha 只在 T1 傳：worker 成功（claude 有回應）才前移 marker，失敗下輪重審（spec 改動1）
        $workerArgs = @(
            '-NoProfile','-File', ('"{0}"' -f $workerPath),
            '-MaterialFile', ('"{0}"' -f $materialFile),
            '-TriggerType', $trigger,
            '-MainCheckout', ('"{0}"' -f $mainCheckout)
        )
        if ($trigger -eq 'T1' -and $head) { $workerArgs += @('-MarkerSha', $head) }
        Start-Process -FilePath 'powershell' -WindowStyle Hidden -ArgumentList $workerArgs | Out-Null
```
（SHA 是十六進位無空白，不需包引號。）

- [ ] **Step 3.3: reflect-worker.ps1 param 加 MarkerSha**：

```powershell
param(
    [Parameter(Mandatory=$true)][string]$MaterialFile,
    [Parameter(Mandatory=$true)][string]$TriggerType,
    [Parameter(Mandatory=$true)][string]$MainCheckout,
    [string]$MarkerSha = ''
)
```

- [ ] **Step 3.4: worker 成功點寫 marker**——在 `if (-not $output) { Write-Log 'claude -p 無輸出'; exit 0 }` 之後、NONE 判斷之前插入：

```powershell
    # claude 已成功回應（含 NONE / 解析不出內容）→ 本輪素材視為已審，前移 marker。
    # 失敗路徑（CLI 不存在 / 逾時 / 無輸出 / 例外）不會走到這裡 → marker 不動 → 下輪 T1 重審（spec 改動1）
    if ($MarkerSha) {
        [System.IO.File]::WriteAllText((Join-Path $stateDir 'last-reflected-commit.txt'), $MarkerSha, [System.Text.UTF8Encoding]::new($false))
    }
```

- [ ] **Step 3.5: 驗證失敗路徑（不前移）**——清空 PATH 讓 `Get-Command claude` 失敗：

```powershell
$main = 'C:\Users\LIN HONG\Desktop\Project_01'
$wt   = "$main\.claude\worktrees\reflect-hardening"
$mk   = "$main\.claude\hooks\state\reflect\last-reflected-commit.txt"
$before = Get-Content $mk -Raw
[System.IO.File]::WriteAllText("$env:TEMP\mat-fail.txt", "test material", [System.Text.UTF8Encoding]::new($false))
powershell -NoProfile -Command "& { `$env:Path=''; & '$wt\.claude\hooks\reflect-worker.ps1' -MaterialFile '$env:TEMP\mat-fail.txt' -TriggerType T1 -MainCheckout '$main' -MarkerSha 'deadbeef' }"
"marker unchanged = " + ((Get-Content $mk -Raw) -eq $before)
```
預期：`marker unchanged = True`；reflect.log 出現「claude CLI 不存在，跳過」。

- [ ] **Step 3.6: 驗證成功路徑（前移）**——真呼叫一次 haiku（耗 1 次 daily call）：

```powershell
[System.IO.File]::WriteAllText("$env:TEMP\mat-ok.txt", "## 測試素材`n（無實質內容，預期回 NONE）", [System.Text.UTF8Encoding]::new($false))
& "$wt\.claude\hooks\reflect-worker.ps1" -MaterialFile "$env:TEMP\mat-ok.txt" -TriggerType T1 -MainCheckout $main -MarkerSha 'cafebabe1234'
Get-Content $mk -Raw    # 預期 = cafebabe1234
```
跑完**還原 marker**：`[System.IO.File]::WriteAllText($mk, $before, [System.Text.UTF8Encoding]::new($false))`（$before 是真 SHA）。
（worker 前台跑會佔終端至多 120s——直接等它跑完即可；它 finally 會自清 lock 與 material。）

- [ ] **Step 3.7: e2e T1 派發鏈**——echo stdin 跑 worktree 副本 stop-reflect（主 checkout 需有變動或 HEAD≠marker；測前看 `git -C $main status` 與 marker 決定是否臨時造變動）：

```powershell
'{"session_id":"e2e","transcript_path":""}' | powershell -NoProfile -File "$wt\.claude\hooks\stop-reflect.ps1"
# 等 lock 釋放（worker 跑完）後：
Get-Content "$main\.claude\hooks\reflect.log" -Tail 3
Get-Content $mk -Raw    # 預期 = 派發當下主 checkout HEAD（成功後才出現）
```
預期：log 有本次 T1 紀錄；marker = 派發時 HEAD。注意 daily-calls 又 +1、turn-count 歸 0——e2e 屬真實行為，不還原。

- [ ] **Step 3.8: BOM 複查 + commit**

```powershell
git add .claude/hooks/stop-reflect.ps1 .claude/hooks/reflect-worker.ps1
git commit -m "feat(hooks): advance reflect marker only on successful review"
```

---

### Task 4: 迴歸測試

- [ ] **Step 4.1: 守衛迴歸**——三個 Stop hook 在 `CLAUDE_REFLECT_CHILD=1` 下靜默 exit 0：

```powershell
$env:CLAUDE_REFLECT_CHILD = '1'
foreach ($s in 'stop-check-sales-pytest','stop-sync-pi','stop-reflect') {
  $out = '{"session_id":"guard"}' | powershell -NoProfile -File "$wt\.claude\hooks\$s.ps1"
  "{0,-28} exit={1} out=[{2}]" -f $s, $LASTEXITCODE, ($out -join '|')
}
$env:CLAUDE_REFLECT_CHILD = $null
```
預期：三行皆 `exit=0 out=[]`。

- [ ] **Step 4.2: 乾淨樹 no-op**——主 checkout 樹乾淨且 marker=HEAD 時（若 e2e 後不滿足，先把 marker 設為 HEAD）echo stdin 跑 stop-reflect → 無輸出、無 lock、turn-count +1（測完減回）。

---

### Task 5: 文檔同步

**Files:**
- Modify: `.claude/hooks/NOTES.md`（§12 行為段）
- Modify: `resources/specs/reflective_stop_hook_2026-06-04_spec.md`（修訂註記）

- [ ] **Step 5.1: NOTES.md §12**——行為段更新三點：marker 改「worker 成功後前移（失敗下輪重審）」；素材 git 指令帶 `core.quotePath=false`；reflect.log / stop-sync-pi.log >1MB 輪轉 `.1`。措辭照 §12 既有風格（一行一機制，不解釋預設行為）。

- [ ] **Step 5.2: 基底 spec 修訂註記**——`reflective_stop_hook_2026-06-04_spec.md` 開頭修訂行追加：

```markdown
> **修訂 2026-06-05（逆向比對採納輪）**：marker 改 worker 成功後前移（失敗不丟素材）；素材 git 指令加 `core.quotePath=false`；log 1MB 輪轉。spec → `reflect_hardening_2026-06-05_spec.md`。
```

- [ ] **Step 5.3: commit**

```powershell
git add .claude/hooks/NOTES.md resources/specs/reflective_stop_hook_2026-06-04_spec.md
git commit -m "docs(hooks): sync NOTES and base spec for hardening trio"
```

---

### Task 6: 收尾（worktree 5 階段之 4-5）

- [ ] **Step 6.1:** `ExitWorktree(action="keep")` → 回主 checkout。
- [ ] **Step 6.2:** `git merge worktree-reflect-hardening --ff-only && git push origin main`（push 後 Stop hook 自動 sync Pi）。
- [ ] **Step 6.3:** `git worktree remove .claude/worktrees/reflect-hardening && git branch -d worktree-reflect-hardening`。
- [ ] **Step 6.4:** 回報：改了什麼 / 無 pineedtodo（純 Windows 端）/ Pi sync 由 Stop hook 確認 / 驗證證據逐項列出（Iron Law）。

---

## Self-Review 紀錄

- **Spec 覆蓋**：改動 1→Task 3、改動 2→Task 2、改動 3→Task 1、驗證 §4.1-4.5→Steps 3.5/3.6/2.2/1.4/4.x、§4.6 真實觀察→merge 後被動進行、文檔同步→Task 5。無缺口。
- **Placeholder**：無 TBD；所有 Edit 給了完整新舊碼。
- **一致性**：`-MarkerSha` 參數名在 3.2/3.3/3.5/3.6 一致；`$workerArgs` 僅 Task 3 使用；輪轉條件式兩處同款。
