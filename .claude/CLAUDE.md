# Project_01 — 互動式銷售輔助機器人

人形機器人課程期末專題。Raspberry Pi 4 上的規則匹配點餐 / 收款模擬系統。

---

## ⛔ 絕對禁止（違反就壞東西）

1. **不要修改 `myProgram/ActionGroupControl.py` 和 `myProgram/Board.py`**
   廠商 Hiwonder TonyPi SDK，內含 Pi-only 路徑（`/home/pi/TonyPi/...`）與底層庫 import（`pigpio` / `RPi.GPIO` / `BusServoCmd` / `PWMServo` / `smbus2`）。改了直接破壞硬體通訊。只能 `Read` 引用、`import` 使用。
2. **不要在 Windows 本機安裝任何依賴**（`pip` / `npm` / `apt`）
   本機只負責編輯與 git，執行環境是 Pi。
3. **不要嘗試在 Windows import / 執行任何依賴廠商 SDK 的程式碼** — 必 ImportError。
4. **不要用 `git add -A` / `git add .`** — 明確列出檔名，避免誤加。

---

## 🌏 輸出語言規範

所有 **程式碼註解、字串輸出、文件、commit message、markdown 內的中文** 一律使用 **繁體中文**。即使使用者用簡體中文跟我溝通也不影響此規則 — 最終成果在 **中國台灣** 展示。
（對話回覆本身可繼續簡繁混合，這條只規範**產出物**。）

---

## 👥 Subagent / Agent Teams 派發協議

我（主對話 agent）是工程部「總負責人」，subagent / agent teams 是底下執行任務的工程師團隊。

**派發時機（預設行為）：** plan mode 完成後 → 一律派 subagent（單一任務）/ agent teams（複雜任務）執行，**除非使用者明確要求主 agent 直接寫**。主 agent 留做規劃 / 審查 / 邊界判斷。

**預設模型：** `Agent({model: "sonnet"})`。Agent 工具不接受 `effort` / `thinking` / context window 參數，要 high effort 必須**在 prompt 內明確要求**「extended thinking、仔細思考、嚴格依規範執行」。

**派發前必做：**
1. **EnterWorktree** — 派發前主 agent 先進 worktree，subagent 繼承 cwd 自動在隔離環境內工作。完整流程見下方「🌳 Worktree 工作流程」。
2. **挑選當前任務可能涉及的 CLAUDE.md 規則** 塞進他們的 context — subagent 是全新 context window，預設讀不到本檔。不要全塞，只塞**可能踩到**的部分。原則：寧多勿漏。
3. **附上 `karpathy-guidelines` Skill** — 編寫程式碼的最佳實踐。
4. **明確要求他們嚴格遵守以上全部規範。**

**派發後必做：**
- 逐項核對產出是否符合 CLAUDE.md。
- 小細節不符 → 我自己直接修，省往返。
- 大量偏差 → 退回要求重做。
- **絕不直接把不符合規範的產出交給使用者。**

詳細協議 → memory `subagent-dispatch`

---

## 🌳 Worktree 工作流程（派發 subagent / team 寫程式時必用）

每次派發 subagent / agent teams 編寫或修改程式碼，**主 agent 必須先 EnterWorktree**，提供隔離工作環境。Subagent 在 worktree 內改檔 / commit，避免污染主 checkout 與其他平行任務。

**5 個階段：**

1. **派發前**：主 agent `EnterWorktree(name="<task-name>")` → cwd 切到 `.claude/worktrees/<task-name>/`，新分支 `worktree-<task-name>`。
2. **編輯**：subagent / team 在 worktree 內改檔 + commit（明確列檔名 `git add <files>`，禁用 `-A` / `.`）。
3. **審查**：主 agent Read worktree 內檔案，逐項對照 CLAUDE.md 規範。不合規退回重做。
4. **收尾（合規後）**：
   - `ExitWorktree(action="keep")` → 切回主 checkout
   - `git merge worktree-<task-name> --ff-only`
   - `git push origin main`
   - `& "C:\Users\LIN HONG\Desktop\Project_01\sync_pi.ps1"`
5. **清理（push + sync 成功後立即執行）**：
   - `git worktree remove .claude/worktrees/<task-name>`
   - `git branch -d worktree-<task-name>`
   - 確認 `git worktree list` 與 `git branch` 乾淨

**例外：**
- Merge 衝突或非 FF → 保留 worktree，跟使用者討論。
- 任務只涉及 gitignored 檔（`resources/userPrompt/`、`resources/presentation/`）→ subagent **不受 worktree 隔離限制**，可直接編輯主 checkout 路徑下的 gitignored 檔；但主 agent 在 worktree mode 下 Edit/Write 主 checkout 會被擋。所以這類任務派 subagent 處理最順。

詳細協議 → memory `worktree-workflow`

---

## ✅ 標準任務收尾循環（滿足條件才做）

> **派 subagent / team 寫 code 時** → 改用上面「🌳 Worktree 工作流程」的 5 階段；本節是**主 agent 自己改檔**（不派 subagent）時用的。

**觸發條件：** 本輪有任何 **git 會追蹤的檔案**改動（即 `.gitignore` 之外的檔案，新增 / 修改 / 刪除皆算）。判斷依據：`git status` 是否非空。

**不觸發 → 直接結束，跳過收尾：**
- 純聊天 / 解答問題 / 上網查資料
- Plan mode 規劃討論（尚未動手實作）
- 變更全在 ignored 路徑（`resources/presentation/` / `resources/userPrompt/` / `sync_pi.ps1` / `.claude/settings.local.json` / `.claude/worktrees/`）→ `git status` 看不到任何 diff
- 沒有任何檔案改動

**觸發時依序執行（5 步）：**
1. `git status` + `git diff` 確認變更範圍
2. `git add <具體檔名>`（不用 `-A` / `.`）
3. `git commit -m "..."` 英文簡短訊息，附 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
4. `git push origin main`
5. **`& "C:\Users\LIN HONG\Desktop\Project_01\sync_pi.ps1"`** — SSH 自動 pull 到 Pi（退出碼 0 = 完成）

---

## 🌐 部署資訊

| 項目 | 值 |
|---|---|
| Pi SSH | `pi@raspberrypi.local` |
| Pi 路徑 | `/home/pi/Desktop/project_jiqiren` |
| GitHub Repo | `https://github.com/leon13018/project_jiqiren.git` |
| 部署方式 | 本機 push → 跑 `sync_pi.ps1` → SSH 自動 `git pull` |

---

## 📝 Pi 端要做的事 → 寫進 markdown，不執行

所有 `apt install` / `pip install` / `raspi-config` / systemd / 一次性指令
→ **條列到 `resources/requirements/raspberry_pi_setup.md`**，由使用者在 Pi 終端手動執行。
寫程式引入新套件時，**同步**更新該檔。

---

## 🔗 我需要更多細節時 → 看這裡

| 我要找... | 路徑 |
|---|---|
| 完整目錄結構 / 每檔職責 | `resources/projectStructure/projectStructure.md` |
| Pi 安裝什麼 / 跑什麼 bash | `resources/requirements/raspberry_pi_setup.md` |
| 專案背景 / 進度報告 | `resources/presentation/人形機器人期末專題5.7進度報告.pdf` |
| 廠商 SDK 完整 API 清單 | memory: `vendor-files` |
| 完整 5 步收尾流程細節 | memory: `standard-workflow` |
| 工作邊界（能做不能做） | memory: `workflow-constraints` |
| 使用者背景 | memory: `user-profile` |
| 部署細節（IP / repo / 路徑） | memory: `project-deployment` |
| Worktree 完整流程 + cleanup 規則 | memory: `worktree-workflow` |

---

## 🛠️ 廠商 SDK 關鍵 API（直接 import 使用）

**`ActionGroupControl`**（播放 `/home/pi/TonyPi/ActionGroups/*.d6a` 動作）
- `runAction(actName, lock_servos='')`
- `runActionGroup(actName, times=1, with_stand=False, lock_servos='')`
- `stopAction()` / `stopActionGroup()`

**`Board`**（舵機 / 蜂鳴器）
- `setBusServoPulse(id, pulse, use_time)` — 總線舵機，pulse 0–1000
- `setPWMServoPulse(servo_id, pulse, use_time)` — PWM 舵機 1–2，pulse 500–2500
- `setBuzzer(state)`
- 各種 servo getter/setter（deviation / angle limit / temp / vin / pulse）

---

## ⚙️ 操作習慣

- 優先 `Read` / `Edit` / `Write` / `Glob` / `Grep` —— Windows shell 只給 git 用。
- 規劃階段（還沒確定要做什麼）→ 暫停確認，不要先 commit。
- 任務完成回報用 1-2 句話：改了什麼、Pi 是否同步成功。

---

## 📍 路徑規範（寫程式 / 設定檔時必遵守）

程式最終在 **Raspberry Pi 4 (Linux)** 上執行，所有檔案路徑必須符合：

1. **Linux 路徑格式** — 正斜線 `/`，不用反斜線 `\`；大小寫敏感。
2. **絕對路徑** — 從 `/` 開始的完整路徑；**不要**用：
   - Windows 路徑（`C:\Users\...`）
   - 相對路徑（依賴執行時 cwd，容易在不同呼叫方式下失效）
   - `~` 或 `~/`（bash 引號內 / subprocess / 某些 context 不會展開）

### 常用 Pi 端絕對路徑

| 用途 | 路徑 |
|---|---|
| 專案根目錄 | `/home/pi/Desktop/project_jiqiren` |
| 廠商動作檔（`.d6a`） | `/home/pi/TonyPi/ActionGroups/` |
| 廠商 SDK | `/home/pi/TonyPi/HiwonderSDK/` |
| Pi 使用者家目錄 | `/home/pi` |
