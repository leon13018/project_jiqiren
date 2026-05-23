# 專案目錄結構

> 本檔案記錄整個專案的資料夾與檔案結構，方便日後快速查閱。
> 最後更新：2026-05-23

---

## 完整結構（不含 `.git/` 內部檔案）

```
Project_01/
├── .claude/                              # Claude Code 設定資料夾
│   ├── CLAUDE.md                         # 📌 每輪載入的專案上下文 — tracked
│   ├── settings.local.json               # 本機 Claude 設定（gitignored）
│   ├── worktrees/                        # 暫存 worktree 目錄（gitignored；2026-05-22 加入）
│   └── rules/                            # 規則檔（2026-05-23 加入）— tracked
│       ├── vendor-sdk-api.md             # 廠商 SDK API；path-scoped, paths: myProgram/**/*.py
│       ├── path-conventions.md           # Linux 路徑規範；path-scoped, paths: code / scripts / Pi docs
│       ├── subagent-dispatch-protocol.md # Subagent 派發協議完整版（無 paths，啟動載入）
│       ├── worktree-workflow.md          # Worktree 5 階段流程完整版（無 paths）
│       ├── standard-workflow.md          # 標準收尾循環 5 步完整版（無 paths）
│       ├── pi-side-trigger.md            # 🚦 Pi 端操作觸發條件完整版（無 paths）
│       └── projectstructure-trigger.md   # 📂 結構維護觸發條件完整版（無 paths）
│
├── .gitignore                            # Git 忽略清單（2026-05-22 重構為精準排除）
│
├── sync_pi.ps1                           # Windows 端 SSH 部署腳本（gitignored）
│
├── myProgram/                            # 主程式資料夾（所有 .py 在此）
│   ├── myProgram.py                      # ✍️ 自寫 — 主程式：狀態機、規則匹配、點餐、結帳
│   ├── screen_display.py                 # ✍️ 自寫 — Tkinter POS 螢幕（訂單、QR Code）
│   ├── robot_actions.py                  # ✍️ 自寫 — 機器人動作封裝（頭部 / 四肢）
│   ├── tts.py                            # ✍️ 自寫 — edge-tts 雲端 TTS 封裝（zh-TW-HsiaoChenNeural）
│   ├── ActionGroupControl.py             # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   └── Board.py                          # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│
└── resources/                            # 開發 / 部署參考資源（2026-05-22 重構：大部分 tracked）
    ├── presentation/                     # gitignored — 大檔不入 git
    │   └── 人形機器人期末專題5.7進度報告.pdf
    │
    ├── userPrompt/                       # gitignored — 個人 prompt 草稿
    │   ├── main_01
    │   ├── main_02
    │   └── 系统设定_01
    │
    ├── requirements/                     # tracked
    │   └── raspberry_pi_setup.md         # Pi 已安裝清單（被動更新，使用者回報後 main agent 寫入）
    │
    ├── pineedtodo/                       # tracked — per-task Pi 端操作說明書（append-only）
    │   └── 2026-05-22_TTS_setup.md       # edge-tts + mpg123 + 音訊裝置設定 + 測試
    │
    ├── projectStructure/                 # tracked
    │   └── projectStructure.md           # 本檔案
    │
    └── plans/                            # tracked — plan 草稿
        └── plan_tts_1                    # 初版 edge-tts 接入 plan 草稿
```

---

## `.gitignore` 排除清單（2026-05-22 重構）

```
.claude/settings.local.json
.claude/worktrees/
sync_pi.ps1
resources/presentation/
resources/userPrompt/
```

- ✅ `.claude/CLAUDE.md` tracked，push 上 GitHub + sync 到 Pi。
- ✅ `resources/requirements/`、`resources/pineedtodo/`、`resources/projectStructure/`、`resources/plans/` 全 tracked，會 sync 到 Pi。
- 🚫 `resources/presentation/`（大 PDF）+ `resources/userPrompt/`（個人草稿）+ `sync_pi.ps1`（Windows-only）+ `.claude/settings.local.json`（本機設定）+ `.claude/worktrees/`（暫存）保持 ignored。

---

## 各檔案職責簡述

### 自寫程式碼（myProgram/）

| 檔案 | 職責 |
|---|---|
| `myProgram.py` | 主程式入口；全域狀態（`has_customer`, `waiting_for_order`）、商品目錄、規則匹配、叫賣循環、顧客服務流程 |
| `screen_display.py` | `POSScreen` 類別；Tkinter 視窗、queue 執行緒安全、`show_welcome()` / `update_order()` |
| `robot_actions.py` | 動作封裝；`nod_head` / `shake_head` / `look_forward` / `action_idle` / `action_greet` / `action_pay` |
| `tts.py` | edge-tts 雲端 TTS 封裝；同步阻塞 `speak()`、`threading.Lock` 序列化、自動退回純 print（套件 / 網路失敗時） |

### 廠商 SDK（myProgram/，禁止修改）

| 檔案 | 職責 |
|---|---|
| `ActionGroupControl.py` | 播放 `/home/pi/TonyPi/ActionGroups/*.d6a` 四肢動作組 |
| `Board.py` | 總線舵機（頭部）、PWM 舵機、蜂鳴器、GPIO 等底層控制 |

> 廠商檔內含 Pi-only 路徑與底層庫 import（`pigpio`, `RPi.GPIO`, `BusServoCmd` 等），**Windows 本機無法 import 測試**，實際執行驗證一律在 Raspberry Pi 4 上。

### 部署 / 設定

| 檔案 | 職責 |
|---|---|
| `sync_pi.ps1` | SSH 到 `pi@raspberrypi.local`，自動 `git pull` / clone 到 `/home/pi/Desktop/project_jiqiren` |
| `.gitignore` | 排除清單（見上方） |
| `.claude/CLAUDE.md` | 每輪載入的專案上下文（大標題 + pointer 指向 rules / memory） |
| `.claude/rules/` | 規則檔目錄 — path-scoped 規則動到符合檔案才載入；無 paths 的跟 CLAUDE.md 同等啟動載入 |
| `.claude/rules/vendor-sdk-api.md` | 廠商 SDK 關鍵 API；path-scoped, paths: `myProgram/**/*.py` |
| `.claude/rules/path-conventions.md` | Linux 路徑規範；path-scoped, paths: 程式碼 / `.ps1` / `.gitignore` / Pi setup & 操作 markdown |
| `.claude/rules/subagent-dispatch-protocol.md` | Subagent 派發協議完整版（無 paths，啟動載入） |
| `.claude/rules/worktree-workflow.md` | Worktree 5 階段流程完整版（無 paths） |
| `.claude/rules/standard-workflow.md` | 標準收尾循環 5 步完整版（無 paths） |
| `.claude/rules/pi-side-trigger.md` | 🚦 Pi 端操作觸發條件完整版（無 paths） |
| `.claude/rules/projectstructure-trigger.md` | 📂 結構維護觸發條件完整版（無 paths） |
| `.claude/settings.local.json` | Claude Code 本機設定（gitignored）|
| `.claude/worktrees/` | EnterWorktree 建立的暫存工作目錄（gitignored；任務完成後 cleanup） |

### 文件 / 參考（resources/）

| 檔案 / 資料夾 | 職責 |
|---|---|
| `presentation/人形機器人期末專題5.7進度報告.pdf` | 5/7 期末專題進度報告簡報 |
| `userPrompt/` | 使用者個人 prompt 草稿（與 Claude Code 溝通時的輸入備份） |
| `requirements/raspberry_pi_setup.md` | **Pi 已安裝清單** — Pi 上實際完成安裝並經使用者回報確認的項目 snapshot；被動更新 |
| `pineedtodo/` | **per-task Pi 端操作說明書** — append-only，每輪有 Pi 動作時新增一檔（檔名 `<YYYY-MM-DD>_<short_name>.md`）|
| `projectStructure/projectStructure.md` | 本檔案 — 專案目錄結構 |
| `plans/` | plan 草稿（plan mode 討論結果 / 任務藍圖）|

---

## 更新紀錄

| 日期 | 變更 |
|---|---|
| 2026-05-21 | 建立初版；`resource/` 已重新命名為 `resources/` |
| 2026-05-22 | edge-tts 接入（`tts.py` 新建）；`.gitignore` 重構（精準排除 `presentation/` + `userPrompt/`，其他 `resources/` 改 tracked）；`.claude/worktrees/` 加入 ignore；CLAUDE.md 新增 Worktree 工作流程 + Subagent 派發協議 + Pi 端操作觸發條件 |
| 2026-05-23 | 新增 `.claude/rules/` 子資料夾 + 2 個 path-scoped 規則檔（`vendor-sdk-api.md` / `path-conventions.md`）；CLAUDE.md 拆出 🛠️ 廠商 SDK API + 📍 路徑規範 兩節，加 📋 維護原則；CLAUDE.md 從 ~236 行降到 ~210 行 |
| 2026-05-23 | `raspberry_pi_setup.md` 重新定位為「Pi 已安裝清單」（被動更新）；CLAUDE.md「📝 Pi 端要做的事」節廢除，整合進工作流程 1a / 3a；查閱表加 `pineedtodo/` 行；memory 對齊現行規則 |
| 2026-05-23 | 三層架構建立：CLAUDE.md 各章節詳細內容拆到 `.claude/rules/` 新增 5 個檔（subagent-dispatch-protocol / worktree-workflow / standard-workflow / pi-side-trigger / projectstructure-trigger，無 paths frontmatter）；CLAUDE.md 從 ~210 行降到 ~112 行，只留標題 + 一句描述 + pointer |
