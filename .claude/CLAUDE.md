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

派發 subagent / team 寫程式時的協議：觸發時機、預設模型 (`Agent({model: "sonnet"})`)、派發前 4 步、派發後審查。
→ **詳細：`.claude/rules/subagent-dispatch-protocol.md`**

---

## 🌳 Worktree 工作流程

編寫 tracked 檔時必走的 5 階段（EnterWorktree → 編輯 + commit → 審查 → ff-merge + push + sync → cleanup），含條件性子步驟 3a / 3b。
→ **詳細：`.claude/rules/worktree-workflow.md`**

---

## ✅ 標準任務收尾循環

git 內核 5 步（status → add → commit → push → sync），內嵌在 Worktree 階段 2 / 3a-b / 4 內。觸發條件 = `git status` 非空。
→ **詳細：`.claude/rules/standard-workflow.md`**

---

## 🚦 Pi 端操作觸發條件

判斷本輪變更是否需要使用者去 Pi 上做事（pip install / apt / raspi-config / 硬體啟用 / systemd 等）。觸發則寫 pineedtodo 並提醒使用者回報。
→ **詳細：`.claude/rules/pi-side-trigger.md`**

---

## 📂 專案資料結構維護觸發條件

判斷本輪是否動到專案目錄結構（檔案 / 資料夾增刪 / 改名 / 改 `.gitignore`）。觸發則更新 projectStructure.md。
→ **詳細：`.claude/rules/projectstructure-trigger.md`**

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
| Subagent / Team 派發協議完整版 | `.claude/rules/subagent-dispatch-protocol.md` |
| Worktree 工作流程完整版 | `.claude/rules/worktree-workflow.md` |
| 標準收尾循環完整版 | `.claude/rules/standard-workflow.md` |
| Pi 端操作觸發完整條件 + 流程 | `.claude/rules/pi-side-trigger.md` |
| 專案資料結構維護觸發完整條件 | `.claude/rules/projectstructure-trigger.md` |
| 廠商 SDK 關鍵 API（編 .py 時 path-scoped 自動載入） | `.claude/rules/vendor-sdk-api.md` |
| Linux 路徑規範（寫 code / Pi 設定時 path-scoped 自動載入） | `.claude/rules/path-conventions.md` |
| 多線程規範（編 `myProgram/*.py` path-scoped 自動載入） | `.claude/rules/threading-conventions.md` |
| 廠商已驗證範例代碼（學 pattern 用，可讀可仿） | `resources/examples/` |
| 廠商 SDK 完整 API 清單 + 禁改背景 | memory: `vendor-files` |
| 派發協議：心態原則 / 規則對應表 | memory: `subagent-dispatch` |
| Worktree：視野範圍速查 / cleanup 原理 | memory: `worktree-workflow` |
| 標準收尾：補充準則 / 歷史 bug 教訓 | memory: `standard-workflow` |
| pineedtodo/ 檔名 + 內容結構(寫新檔前必讀) | memory: `pineedtodo-spec` |
| 工作邊界（能做不能做） | memory: `workflow-constraints` |
| 使用者背景 | memory: `user-profile` |
| 部署細節（IP / repo / 路徑） | memory: `project-deployment` |
| 輸出語言規範（簡繁對照） | memory: `output-language` |

---

## ⚙️ 操作習慣

- 優先 `Read` / `Edit` / `Write` / `Glob` / `Grep` —— Windows shell 只給 git 用。
- 規劃階段（還沒確定要做什麼）→ 暫停確認，不要先 commit。
- 任務完成回報應包含：(1) 改了什麼、(2) 是否觸發 1a / 3a 寫了 pineedtodo、(3) Pi 是否同步成功、(4) 是否需要使用者後續行動（Pi 端操作 + 回報安裝狀況）。如有 Pi 動作，明確標示「請完成後回報哪些成功裝上」。

---

## 📋 維護原則

- **三層架構：** CLAUDE.md（大標題 + pointer）→ `.claude/rules/<topic>.md`（完整協議內容）→ memory `<topic>`（背景 / 歷史 / Why 細節）。
- **CLAUDE.md 變動原則：** 只放標題 + 一句話描述 + pointer；具體規則內容拆到 rules 或 memory。
- **path-scoped 規則：** 只在編特定檔案類型才需要的（如廠商 SDK API、Linux 路徑規範）→ `.claude/rules/<topic>.md` 加 `paths: [...]` frontmatter，動到對應檔才載入（省 context）。
- **無 paths 規則：** 跟 CLAUDE.md 同等啟動載入 — 純組織用，不省 context。
- 維護用 metadata（最後審查日期、人類備註）可用 `<!-- HTML 註解 -->` — 不會進 Claude context；但 git log 通常已足。
