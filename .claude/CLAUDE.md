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
3a. **（條件性）撰寫 Pi 端操作說明書**：階段 3 審查通過後，主 agent 統整「subagent 回報 + 自身判斷」，確認本輪變更**實際**涉及任何 Pi 端動作（見下方「🚦 Pi 端操作觸發條件」節）→ **新增一個檔**到 `resources/pineedtodo/<檔名>.md`（**append-only：既有檔不動**），在 worktree 內 `git add` + `git commit`（subagent 的 code commit 之上多一個 commit）。不觸發直接進階段 4。
3b. **（條件性）更新 projectStructure.md**：階段 3 審查通過後，主 agent 判斷本輪變更是否**改動到專案資料結構**（觸發清單見下方「📂 專案資料結構維護觸發條件」節）→ 觸發則編輯 `resources/projectStructure/projectStructure.md`（目錄樹 + 職責表 + 更新紀錄），在 worktree 內一併 `git add` + `git commit`（可與 3a 的 commit 合併為單一 commit）。不觸發直接進階段 4。
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

> **背景 session 限制：所有 tracked 檔的編輯都要走「🌳 Worktree 工作流程」5 階段**（不論派 subagent 或主 agent 自己改純文件 / memory bootstrap）。本節定義 git 收尾的**內核步驟**，會內嵌在 Worktree 階段 2 / 3a（commit）與階段 4（push / sync）內。差別只在「誰寫」 — 派 subagent 寫 vs 主 agent 自己寫。
> 改 gitignored 檔則不需進 worktree（worktree 看不到該檔）。

**觸發條件：** 本輪有任何 **git 會追蹤的檔案**改動（即 `.gitignore` 之外的檔案，新增 / 修改 / 刪除皆算）。判斷依據：`git status` 是否非空。

**不觸發 → 直接結束，跳過收尾：**
- 純聊天 / 解答問題 / 上網查資料
- Plan mode 規劃討論（尚未動手實作）
- 變更全在 ignored 路徑（`resources/presentation/` / `resources/userPrompt/` / `sync_pi.ps1` / `.claude/settings.local.json` / `.claude/worktrees/`）→ `git status` 看不到任何 diff
- 沒有任何檔案改動

**觸發時依序執行（5 步）：**
1. `git status` + `git diff` 確認變更範圍
1a. **（條件性）撰寫 Pi 端操作說明書**：若本輪變更涉及 Pi 端動作（見下方「🚦 Pi 端操作觸發條件」節），主 agent **新增一個檔**到 `resources/pineedtodo/<檔名>.md`（**append-only：既有檔不動**），納入下一步的 `git add`。不觸發直接跳過。
1b. **（條件性）更新 projectStructure.md**：若本輪變更改動到專案資料結構（見下方「📂 專案資料結構維護觸發條件」節），主 agent 編輯 `resources/projectStructure/projectStructure.md`（目錄樹 + 職責表 + 更新紀錄），納入下一步的 `git add`。不觸發直接跳過。
2. `git add <具體檔名>`（不用 `-A` / `.`）
3. `git commit -m "..."` 英文簡短訊息，附 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
4. `git push origin main`
5. **`& "C:\Users\LIN HONG\Desktop\Project_01\sync_pi.ps1"`** — SSH 自動 pull 到 Pi（退出碼 0 = 完成）

---

## 🚦 Pi 端操作觸發條件（給上面兩個工作流程內 1a / 3a 步驟參考）

主 agent 在審查後須判斷本輪變更**實際**會否導致使用者要在 Pi 終端手動做事。

**觸發 ✅：**
- 新增 / 移除 Python 套件 import → `pip install / uninstall`
- 新增 / 移除 apt 系統套件 → `sudo apt install / remove`
- 硬體介面啟用（I2C / Camera / Audio / SPI）→ `raspi-config`
- 音訊裝置 / 音量設定（`alsamixer`、raspi-config Audio）
- 新增 systemd service / 自啟動腳本
- 一次性測試 / 校準 / 配置流程
- 任何修改 Pi 系統設定 / 環境變數 / 檔案權限的指令

**不觸發 ❌：**
- 純程式邏輯修改 / 重構（無新依賴）
- 純文件 / markdown / memory / `.claude/` 內檔案更新
- `.gitignore` / `sync_pi.ps1` / git 相關設定變動
- CLAUDE.md / 規範自身修訂

**輸出位置與行為：**
- 位置固定：`resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`
- **Append-only**：每輪只**新增**新檔，**既有檔不動、不改、不刪**。即使發現先前檔內容有誤，也是新開一個檔做修正紀錄，不回頭改既有檔。理由：當作歷史紀錄，方便日後查閱「某輪在 Pi 上做了什麼事」。
- **檔名規範：**
  - `<YYYY-MM-DD>` = 該輪 commit 日期（台灣時區）
  - `<short_name>` = 主 agent 依任務性質決定的英數 + 底線描述（如 `TTS` / `camera_install` / `whisper_debug`）
  - **不強制 `_setup` 後綴**，保留彈性適應 install / config / test / debug 各種任務
  - 同日多輪用更具體 `short_name` 區隔（例：`2026-05-23_TTS_install.md` 與 `2026-05-23_TTS_debug.md`）
- **內容結構（鬆散指引 + 2 個固定要素）：**
  - **檔頭區（必有，置頂）**：`**建立日期：** YYYY-MM-DD` + `**對應提交：** <commit_hash> — <commit 標題>`
  - **驗證段（必有，置尾）**：跑什麼指令確認 Pi 端操作成功 + 預期輸出 / 行為
  - 其他章節（Step 1..N / 故障排除 / 完成後）→ 主 agent 視任務性質自由決定
  - 參考範例：`resources/pineedtodo/2026-05-22_TTS_setup.md`

**寫完 pineedtodo 後 → 主 agent 必須提醒使用者回報安裝狀況：**
> 「請在 Pi 上完成操作後跟我回報哪些**成功**裝上 / 啟用了（apt / pip 套件名、raspi-config 啟用項、systemd service 等），我會更新 `resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單）。失敗 / 未完成的不必回報，我們再討論。」

**收到使用者回報成功 → 主 agent 更新已安裝清單：**
- Read `resources/requirements/raspberry_pi_setup.md` → 把使用者**明確**回報成功的項目（套件名 / 啟用項 / 服務名）加進對應區塊 → 標準 5 步收尾流程（純文件編輯例外，主 agent 自己改）
- **禁止自動推測 / 假設使用者已裝什麼**，必須有明確回報才寫
- 失敗 / 未回報項目絕不寫入

---

## 📂 專案資料結構維護觸發條件（給上面兩個工作流程內 1b / 3b 步驟參考）

主 agent 在審查後須判斷本輪變更是否會**動到專案目錄結構**（不論 tracked 或 gitignored）。

**觸發 ✅：**
- 新增 / 刪除 / 移動 / 改名 **檔案**
- 新增 / 刪除 / 移動 / 改名 **資料夾**
- **包括 gitignored 路徑下的變動**（例如 `resources/userPrompt/` 內新增檔案）
- 修改 `.gitignore`（會改變 projectStructure.md 內 tracked vs ignored 標註）

**不觸發 ❌：**
- 純內容修改（檔名 / 路徑不變）
- commit message / git config 等不影響結構的變動

**輸出位置與主 agent 動作：**
- 編輯 `resources/projectStructure/projectStructure.md`
- 同步更新：(1) 完整結構目錄樹、(2) 對應職責表（新檔加職責；刪掉的撤行）、(3) 「更新紀錄」加一行 `<YYYY-MM-DD>` 簡述變更

**場景 B：使用者手動改結構 → 回報 → 主 agent 更新**
使用者在 VSCode / 檔案總管手動改了目錄結構 → 跟主 agent 回報「我改了 X」→ 主 agent 觸發此事件，純文件編輯例外，走「✅ 標準任務收尾循環」5 步收尾。

---

## 🌐 部署資訊

| 項目 | 值 |
|---|---|
| Pi SSH | `pi@raspberrypi.local` |
| Pi 路徑 | `/home/pi/Desktop/project_jiqiren` |
| GitHub Repo | `https://github.com/leon13018/project_jiqiren.git` |
| 部署方式 | 本機 push → 跑 `sync_pi.ps1` → SSH 自動 `git pull` |

---

## 🔗 我需要更多細節時 → 看這裡

| 我要找... | 路徑 |
|---|---|
| 完整目錄結構 / 每檔職責 | `resources/projectStructure/projectStructure.md` |
| Pi 上目前已安裝什麼（snapshot） | `resources/requirements/raspberry_pi_setup.md` |
| 過去每一輪 Pi 上做了什麼操作（歷史細節） | `resources/pineedtodo/` |
| 專案背景 / 進度報告 | `resources/presentation/人形機器人期末專題5.7進度報告.pdf` |
| 廠商 SDK 完整 API 清單 | memory: `vendor-files` |
| 完整 5 步收尾流程細節 | memory: `standard-workflow` |
| 工作邊界（能做不能做） | memory: `workflow-constraints` |
| 使用者背景 | memory: `user-profile` |
| 部署細節（IP / repo / 路徑） | memory: `project-deployment` |
| Worktree 完整流程 + cleanup 規則 | memory: `worktree-workflow` |
| 廠商 SDK 關鍵 API（編 .py 時 path-scoped 自動載入） | `.claude/rules/vendor-sdk-api.md` |
| Linux 路徑規範（寫 code / Pi 設定時 path-scoped 自動載入） | `.claude/rules/path-conventions.md` |
---

## ⚙️ 操作習慣

- 優先 `Read` / `Edit` / `Write` / `Glob` / `Grep` —— Windows shell 只給 git 用。
- 規劃階段（還沒確定要做什麼）→ 暫停確認，不要先 commit。
- 任務完成回報應包含：(1) 改了什麼、(2) 是否觸發 1a / 3a 寫了 pineedtodo、(3) Pi 是否同步成功、(4) 是否需要使用者後續行動（Pi 端操作 + 回報安裝狀況）。如有 Pi 動作，明確標示「請完成後回報哪些成功裝上」。

---

## 📋 維護原則

- **本檔保持 < 200 行**（官方建議；超過會消耗 context 並降低遵守度）。
- **條件性 / 路徑特定規則**（只在編特定檔案類型才需要的）→ 拆到 `.claude/rules/<topic>.md` 加 `paths: [...]` frontmatter，做 path-scoped 載入（Claude 動到符合檔案時才進 context）。
- **意圖觸發規則**（如 🚦 Pi 端動作判斷、📂 結構變更判斷）→ 留 CLAUDE.md，因為無法用 file path 描述觸發條件。
- 維護用 metadata（最後審查日期、人類備註）可用 `<!-- HTML 註解 -->` — 不會進 Claude context；但 git log 通常已足，不必過度使用。
