# 專案目錄結構

> 本檔案記錄整個專案的資料夾與檔案結構，方便日後快速查閱。
> 最後更新：2026-05-24（S1 v2 預備：清空 myProgram.py + 新增空 sales_logic.py 骨架）

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
│       ├── projectstructure-trigger.md   # 📂 結構維護觸發條件完整版（無 paths）
│       ├── threading-conventions.md      # 多線程規範；path-scoped, paths: myProgram/**/*.py
│       └── incremental-rebuild.md        # 🔁 Incremental rebuild 流程 + S1-S7 模板（無 paths）
│
├── .gitignore                            # Git 忽略清單（2026-05-22 重構為精準排除）
│
├── sync_pi.ps1                           # Windows 端 SSH 部署腳本（gitignored）
│
├── myProgram/                            # 主程式資料夾（S1 v2 重做中：業務邏輯改 5 層狀態機）
│   ├── myProgram.py                      # ✍️ 入口（暫空）— S1 v2 完成後負責 import sales_logic 並啟動
│   ├── sales_logic.py                    # ✍️ 業務邏輯主檔（暫空）— S1 v2 將實作 5 層狀態機
│   ├── ActionGroupControl.py             # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   └── Board.py                          # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   # 2026-05-23 incremental rebuild：tts.py / robot_actions.py / screen_display.py 歸檔
│   # 到 resources/examples/legacy_threading_v1/。後續 S2-S7 逐步加層。
│   # 2026-05-24 S1 v1（115 行單檔）清空重做為「入口 + 業務邏輯」分離結構。
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
    │   ├── 2026-05-22_TTS_setup.md       # edge-tts + mpg123 + 音訊裝置設定 + 測試
    │   ├── 2026-05-23_python311_vendor_deps.md  # 廠商 SDK 所有依賴補裝到 Python 3.11 + 迭代驗證
    │   └── 2026-05-23_python311_rebuild_pillow_libtiff.md  # Python rebuild 加 _tkinter + Pillow source build 連 libtiff5
    │
    ├── projectStructure/                 # tracked
    │   └── projectStructure.md           # 本檔案
    │
    ├── plans/                            # tracked — plan 草稿
    │   └── plan_tts_1                    # 初版 edge-tts 接入 plan 草稿
    │
    └── examples/                         # tracked — 廠商已驗證範例代碼（2026-05-23 加入）
        ├── 機器人動作結合opencv的多線程使用范例.py  # 廠商多線程範例：cv2 主線程 + 動作背景線程
        └── legacy_threading_v1/          # 2026-05-23 歸檔：第一輪多線程重構成果（incremental rebuild 前）
            ├── README.md                  # 設計重點、踩到的坑、可參考的 pattern
            ├── myProgram.py               # 主迴圈 + ActionWorker + input_reader + command_dispatcher
            ├── tts.py                     # TtsWorker（中斷式 say + Popen handle + terminate）
            ├── robot_actions.py           # 組合動作 + cancel event
            └── screen_display.py          # tkinter POSScreen + thread-safe _poll_queue
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
- ✅ `resources/requirements/`、`resources/pineedtodo/`、`resources/projectStructure/`、`resources/plans/`、`resources/examples/` 全 tracked，會 sync 到 Pi。
- 🚫 `resources/presentation/`（大 PDF）+ `resources/userPrompt/`（個人草稿）+ `sync_pi.ps1`（Windows-only）+ `.claude/settings.local.json`（本機設定）+ `.claude/worktrees/`（暫存）保持 ignored。

---

## 各檔案職責簡述

### 自寫程式碼（myProgram/）

**狀態（2026-05-24 S1 v2 重做進行中）**：S1 v1（115 行單檔）2026-05-24 清空。改為「入口 + 業務邏輯」分離結構；業務邏輯按 5 層狀態機重做（L1 模式選擇 / L2 詢問需求 / L3 額外需求 / L4 印金額掃碼 / L5 謝謝惠顧）。

| 檔案 | 引入階段 | 職責 |
|---|---|---|
| `myProgram.py` | S1 v2（暫空）| 入口：未來 `from sales_logic import run; run()`，保持簡潔 |
| `sales_logic.py` | S1 v2（暫空）| 業務邏輯主檔：5 層狀態機（純單線程、無語音 / 動作 / threading；時間 / 視覺 stub）|
| `tts.py` | S2 | 同步阻塞 `speak()`（S4 起擴為非阻塞 TtsWorker）|
| `robot_actions.py` | S3 | 同步動作（S5 起擴為非阻塞 ActionWorker）|

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
| `.claude/rules/threading-conventions.md` | 多線程規範（cv2 / tkinter 主線程、動作 / TTS 背景線程、asyncio / subprocess 地雷區）；path-scoped, paths: `myProgram/**/*.py` |
| `.claude/rules/incremental-rebuild.md` | 🔁 架構難收斂時的 S1-S7 重做模板 + 核心原則（無 paths，啟動載入）|
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
| `examples/` | **廠商已驗證範例代碼 + 歸檔舊版** — 廠商寫好且在機器人上測試成功的示範碼；可參考做 pattern、可仿、可改（與 `myProgram/` 的廠商 SDK 本體不同，那些禁改）|
| `examples/legacy_threading_v1/` | 2026-05-23 第一輪多線程重構成果歸檔（4 個 .py + README）；incremental rebuild 前的舊版設計，留作參考。內含 README 說明踩到的坑（vendor stop_action sticky / has_customer 分流 race）|

---

## 更新紀錄

| 日期 | 變更 |
|---|---|
| 2026-05-21 | 建立初版；`resource/` 已重新命名為 `resources/` |
| 2026-05-22 | edge-tts 接入（`tts.py` 新建）；`.gitignore` 重構（精準排除 `presentation/` + `userPrompt/`，其他 `resources/` 改 tracked）；`.claude/worktrees/` 加入 ignore；CLAUDE.md 新增 Worktree 工作流程 + Subagent 派發協議 + Pi 端操作觸發條件 |
| 2026-05-23 | 新增 `.claude/rules/` 子資料夾 + 2 個 path-scoped 規則檔（`vendor-sdk-api.md` / `path-conventions.md`）；CLAUDE.md 拆出 🛠️ 廠商 SDK API + 📍 路徑規範 兩節，加 📋 維護原則；CLAUDE.md 從 ~236 行降到 ~210 行 |
| 2026-05-23 | `raspberry_pi_setup.md` 重新定位為「Pi 已安裝清單」（被動更新）；CLAUDE.md「📝 Pi 端要做的事」節廢除，整合進工作流程 1a / 3a；查閱表加 `pineedtodo/` 行；memory 對齊現行規則 |
| 2026-05-23 | 三層架構建立：CLAUDE.md 各章節詳細內容拆到 `.claude/rules/` 新增 5 個檔（subagent-dispatch-protocol / worktree-workflow / standard-workflow / pi-side-trigger / projectstructure-trigger，無 paths frontmatter）；CLAUDE.md 從 ~210 行降到 ~112 行，只留標題 + 一句描述 + pointer |
| 2026-05-23 | 使用者新增 `resources/examples/` 資料夾收納廠商已驗證範例代碼，加入第 1 份廠商範例（cv2 + 動作多線程）；主 agent 由此範例抽出多線程規範 `.claude/rules/threading-conventions.md`（path-scoped to `myProgram/**/*.py`）；CLAUDE.md 🔗 查閱表加 2 行 |
| 2026-05-23 | TTS 沒聲音 debug → 發現 Python interpreter mismatch（3.11 缺 pyserial 等廠商 SDK 依賴，3.7 缺 edge-tts）；新增 pineedtodo `2026-05-23_python311_vendor_deps.md` 統整所有廠商 SDK pip 依賴補裝指令 + 迭代驗證流程 |
| 2026-05-23 | 接續上輪 debug，實際迭代踩了 3 個 Buster + piwheels 坑（RPi.GPIO piwheels GLIBC_2.34 不相容 / Python 3.11.9 source build 沒含 `_tkinter` / piwheels 連 Pillow 9 都連結 libtiff.so.6）；新增 pineedtodo `2026-05-23_python311_rebuild_pillow_libtiff.md` 記錄修補（source build pip / apt tk-dev+tcl-dev 並 rebuild Python / apt libtiff5-dev 並 source build Pillow 9）；`raspberry_pi_setup.md` 補進確認裝上的 8 個 apt + 9 個 pip 套件 |
| 2026-05-23 | 第一輪多線程重構（commit `42291c8` + `a95507f`）後實測「按 y 不一致 / 動作 / 語音被打斷 / 反覆切換亂掉」，根因為 vendor `stop_action` sticky 旗號 + `has_customer` 雙 queue 分流 race。決定 incremental rebuild：歸檔 4 個自寫 .py 到 `resources/examples/legacy_threading_v1/`（含 README 紀錄踩坑）；新增 `.claude/rules/incremental-rebuild.md`（S1-S7 模板 + 核心原則）；CLAUDE.md 加 🔁 Incremental rebuild 段 + pointer；memory 新增 3 條（`incremental-rebuild-pattern` / `vendor-stop-action-sticky` / `single-queue-preference`）|
| 2026-05-23 | **S1 完成**：新建 `myProgram/myProgram.py`（115 行純單線程對話骨架）— PRODUCTS / 關鍵字 / 識別函數 / customer_session / main 主迴圈；無 timeout / 無 threading / 不 import 任何後續 .py。商品與舊版一致（冰紅茶 + 刮刮樂全場九折）。等待使用者測 OK 才開 S2（同步語音）|
| 2026-05-24 | **S1 v2 預備**：S1 v1 經實測發現業務邏輯瑕疵（重複加單 / 無修改數量機制 / 無確認流程），決定重做為 5 層狀態機。本輪僅做架構準備：清空 `myProgram/myProgram.py`、新增空 `myProgram/sales_logic.py`（之後業務邏輯都寫此檔，`myProgram.py` 只當入口 import）|
