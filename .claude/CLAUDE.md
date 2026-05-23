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

**派發時機：** plan mode 完成後 → 預設派 subagent（單一任務） / team（複雜任務），除非使用者明確要求主 agent 直接寫。
**預設模型：** `Agent({model: "sonnet"})`；高 effort 在 prompt 內要求（無 API 參數）。
**派發前 4 步：** （1） EnterWorktree（見「🌳」節） → （2） 塞相關 CLAUDE.md 規則進 subagent context → （3） 附 `karpathy-guidelines` Skill → （4） 明確要求嚴格遵守。
**派發後審查：** 不合規必修 / 退回，絕不直接交付使用者。

詳細協議 / 規則對應表 / 心態原則 → memory [[subagent-dispatch]]

---

## 🌳 Worktree 工作流程（編寫 tracked 檔時必用）

**5 階段：**
1. **派發前** `EnterWorktree(name="...")` → cwd 切到 `.claude/worktrees/<name>/`，新分支 `worktree-<name>`
2. **編輯** subagent / 主 agent 在 worktree 內改檔 + commit（`git add <檔名>` 禁 `-A`）
3. **審查** 主 agent Read worktree 內檔案逐項對照規範
4. **收尾** `ExitWorktree(keep)` → `git merge --ff-only` → `git push origin main` → `& sync_pi.ps1`
5. **清理** `git worktree remove` + `git branch -d`

**條件性子步驟：** 階段 3a 寫 pineedtodo（見「🚦」節） / 階段 3b 更新 projectStructure.md（見「📂」節）。

例外（merge 衝突 / 純 gitignored 任務 / bootstrap） + 視野範圍速查 + cleanup 原理 → memory [[worktree-workflow]]

---

## ✅ 標準任務收尾循環（git 內核 5 步，內嵌在 Worktree 階段 2 / 3a-b / 4 內）

**觸發：** `git status` 非空（tracked 檔有改動）。純聊天 / plan 討論 / 只動 gitignored → 不觸發。

**5 步：** （1） `status` + `diff` → **（1a） 條件性寫 pineedtodo（見「🚦」）** → **（1b） 條件性更新 projectStructure.md（見「📂」）** → （2） `git add <檔名>` 禁 `-A` → （3） commit 附 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>` → （4） `git push origin main` → （5） `& "C:\Users\LIN HONG\Desktop\Project_01\sync_pi.ps1"`

不觸發列表細節 / 補充準則 / 歷史 bug 教訓 → memory [[standard-workflow]]

---

## 🚦 Pi 端操作觸發條件（給工作流程 1a / 3a 參考）

**觸發 ✅：**
- 新增 / 移除 Python 套件 import → `pip install / uninstall`
- 新增 / 移除 apt 系統套件 → `sudo apt install / remove`
- 硬體介面啟用（I2C / Camera / Audio / SPI） → `raspi-config`
- 音訊裝置 / 音量（`alsamixer`、raspi-config Audio）
- 新增 systemd service / 自啟動腳本
- 一次性測試 / 校準 / 配置流程
- 任何修改 Pi 系統設定 / 環境變數 / 檔案權限

**不觸發 ❌：** 純程式邏輯改 / 純文件 / `.gitignore` / CLAUDE.md 規範自身改。

**輸出：** `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`（**append-only：既有檔不動**）。**檔名規範 + 內容結構 → memory [[pineedtodo-spec]]**（寫新檔前必讀）。

**寫完後流程：**
1. 主 agent 提醒使用者回報「哪些**成功**裝上 / 啟用」（apt / pip 套件名、raspi-config 啟用項、systemd service 等）
2. 收到回報 → 主 agent 更新 `resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單）。**禁止自動推測 / 假設**，失敗 / 未回報項目絕不寫入。

---

## 📂 專案資料結構維護觸發條件（給工作流程 1b / 3b 參考）

**觸發 ✅：** 新增 / 刪除 / 移動 / 改名 **檔案 or 資料夾**（包括 gitignored 路徑下的變動）；修改 `.gitignore`。
**不觸發 ❌：** 純內容修改 / commit message / git config。

**輸出：** 編輯 `resources/projectStructure/projectStructure.md` 同步：（1） 完整結構目錄樹 （2） 對應職責表 （3） 「更新紀錄」加一行 `<YYYY-MM-DD>` 簡述。

**場景 B：** 使用者手動改結構 → 回報主 agent → 觸發本事件，走「✅ 標準收尾」5 步。

---

## 🌐 部署資訊

- Pi SSH `pi@raspberrypi.local`，遠端路徑 `/home/pi/Desktop/project_jiqiren`
- GitHub: `https://github.com/leon13018/project_jiqiren.git`
- 部署：本機 push → 跑 `sync_pi.ps1` → SSH 自動 `git pull`

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
| pineedtodo/ 檔名 + 內容結構（寫新檔前必讀） | memory: `pineedtodo-spec` |
| 廠商 SDK 關鍵 API（編 .py 時 path-scoped 自動載入） | `.claude/rules/vendor-sdk-api.md` |
| Linux 路徑規範（寫 code / Pi 設定時 path-scoped 自動載入） | `.claude/rules/path-conventions.md` |

---

## ⚙️ 操作習慣

- 優先 `Read` / `Edit` / `Write` / `Glob` / `Grep` —— Windows shell 只給 git 用。
- 規劃階段（還沒確定要做什麼） → 暫停確認，不要先 commit。
- 任務完成回報應包含：（1） 改了什麼、（2） 是否觸發 1a / 3a 寫了 pineedtodo、（3） Pi 是否同步成功、（4） 是否需要使用者後續行動（Pi 端操作 + 回報安裝狀況）。如有 Pi 動作，明確標示「請完成後回報哪些成功裝上」。

---

## 📋 維護原則

- **本檔保持 < 200 行**（官方建議；超過會消耗 context 並降低遵守度）。
- **執行細節**（5 階段全文 / 派發前 4 步全文 / 5 步收尾全文 / spec 規範） → 拆到 memory `<topic>.md`，CLAUDE.md 留 inline 摘要 + `[[]]` pointer。
- **條件性 / 路徑特定規則**（只在編特定檔案類型才需要的） → 拆到 `.claude/rules/<topic>.md` 加 `paths: [...]` frontmatter，做 path-scoped 載入（Claude 動到符合檔案時才進 context）。
- **意圖觸發規則**（如 🚦 Pi 端動作判斷、📂 結構變更判斷） → 留 CLAUDE.md，因為無法用 file path 描述觸發條件。
- 維護用 metadata（最後審查日期、人類備註）可用 `<!-- HTML 註解 -->` — 不會進 Claude context；但 git log 通常已足，不必過度使用。
