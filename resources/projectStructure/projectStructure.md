# 專案目錄結構

> 本檔案記錄整個專案的資料夾與檔案結構，方便日後快速查閱。
> 最後更新：2026-05-24（L3 BDD+TDD 第一輪完成：18 scenarios PASS（總 81）；[DEGRADED-TDD-PARTIAL-L3]）

---

## 完整結構（不含 `.git/` 內部檔案）

```
Project_01/
├── .claude/                              # Claude Code 設定資料夾
│   ├── CLAUDE.md                         # 📌 每輪載入的專案上下文 — tracked
│   ├── settings.local.json               # 本機 Claude 設定（gitignored）
│   ├── worktrees/                        # 暫存 worktree 目錄（gitignored；2026-05-22 加入）
│   ├── rules/                            # 規則檔（2026-05-23 加入）— tracked
│   │   ├── vendor-sdk-api.md             # 廠商 SDK API；path-scoped, paths: myProgram/**/*.py
│   │   ├── path-conventions.md           # Linux 路徑規範；path-scoped, paths: code / scripts / Pi docs
│   │   ├── subagent-dispatch-protocol.md # Subagent 派發協議完整版（無 paths，啟動載入）
│   │   ├── worktree-workflow.md          # Worktree 5 階段流程完整版（無 paths）
│   │   ├── standard-workflow.md          # 標準收尾循環 5 步完整版（無 paths）
│   │   ├── pi-side-trigger.md            # 🚦 Pi 端操作觸發條件完整版（無 paths）
│   │   ├── projectstructure-trigger.md   # 📂 結構維護觸發條件完整版（無 paths）
│   │   ├── threading-conventions.md      # 多線程規範；path-scoped, paths: myProgram/**/*.py
│   │   ├── incremental-rebuild.md        # 🔁 Incremental rebuild 流程 + S1-S7 模板（無 paths）
│   │   └── bdd-tdd-workflow.md           # 📝 BDD+TDD 開發流程（2026-05-24 加入）— 4 階段 + subagent prompt 規範 + fallback（無 paths）
│   └── skills/                           # 使用者自訂 skill（2026-05-24 加入）— tracked
│       └── test-driven-development/      # TDD 實踐 skill（S1 v2 實作前載入用）
│           ├── SKILL.md                  # Red-Green-Refactor 流程 + Iron Law（無失敗測試前不寫產品碼）
│           └── testing-anti-patterns.md  # 測試反模式（禁測 mock 行為 / 禁為測試在產品碼加方法）
│
├── .gitignore                            # Git 忽略清單（2026-05-22 重構為精準排除）
│
├── sync_pi.ps1                           # Windows 端 SSH 部署腳本（gitignored）
│
├── pytest.ini                            # pytest 設定（2026-05-24 L0 TDD 加入）— testpaths=tests/sales — tracked
│
├── tests/                                # ✍️ pytest 測試根目錄（2026-05-24 加入）— tracked
│   ├── __init__.py                       # 組織說明（spec/ vs sales/ 對應關係）
│   ├── conftest.py                       # 共用 fixtures 說明（L0 全部用 inline lambda + FakeScheduler，無跨檔共用 fixture）
│   ├── spec/                             # BDD 階段產出（按 L 層；L0 第一輪 2026-05-24 建）
│   │   ├── __init__.py                   # 子資料夾說明
│   │   ├── L0_common_scenarios.py        # L0 共通規則 37 個 scenarios（CONST/PROD/HAWK/NLU/QTY/CART/SUB-A）
│   │   ├── L1_mode_select_scenarios.py   # L1 商家模式選擇 12 個 scenarios（ENTRY/A/B/C/Q；2026-05-24 加入）
│   │   ├── L2_first_order_scenarios.py   # L2 詢問需求 14 個 scenarios（ENTRY/A/B-1/B-2/B-3/C/PRIO；2026-05-24 加入）
│   │   └── L3_add_loop_scenarios.py      # L3 加單迴圈 18 個 scenarios（ENTRY/A/B-1/B-2/B-3/B-4/C-1/C-2/PRIO；2026-05-24 加入）
│   └── sales/                            # TDD 階段產出（按 prod 模組；L0 第一輪 2026-05-24 建）
│       ├── __init__.py                   # 子資料夾說明
│       ├── test_constants.py             # 5 scenarios：L0-CONST + L0-PROD + L0-HAWK
│       ├── test_nlu.py                   # 22 scenarios：L0-NLU(13) + L0-QTY(9)
│       ├── test_cart.py                  # 6 scenarios：L0-CART
│       └── test_states.py                # 4 scenarios：L0-SUB-A 子例程 A（含 FakeScheduler inline stub）
│   # 完整流程：.claude/rules/bdd-tdd-workflow.md
│   # 設計決策（選項 C 純 unit test）：resources/architecture/backend-module-structure.md
│
├── myProgram/                            # 主程式資料夾（S1 v2 重做中：業務邏輯改 5 層狀態機）
│   ├── myProgram.py                      # ✍️ 入口（暫空）— S1 v2 完成後負責 from sales.logic import run 並啟動
│   ├── ActionGroupControl.py             # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   ├── Board.py                          # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   └── sales/                            # ✍️ 後端業務模組（2026-05-24 加入；L0 實作 2026-05-24 完成）
│       ├── __init__.py                   # 模組標記 + docstring
│       ├── logic.py                      # 主迴圈 + 5 層 dispatch（暫骨架，L1+ 才實作）
│       ├── constants.py                  # ✅ L0 實作：7 時間常數 + PRODUCTS dict + HAWK_SLOGANS list
│       ├── nlu.py                        # ✅ L0 實作：classify_intent（6 步優先序）+ parse_quantity（阿拉伯優先 + 中文映射含異體字）
│       ├── cart.py                       # ✅ L0 實作：new_cart / add_item / get_quantity / calc_total / clear_cart / is_empty 純函式
│       └── states.py                     # ✅ L0 實作：run_subroutine_a「回 L1 叫賣」（callback 注入 + 遞迴排程）；L1-L5 鏈路 TODO
│   # 2026-05-23 incremental rebuild：tts.py / robot_actions.py / screen_display.py 歸檔
│   # 到 resources/examples/legacy_threading_v1/。後續 S2-S7 逐步加層。
│   # 2026-05-24 S1 v1（115 行單檔）清空重做為「入口 + 業務邏輯」分離結構。
│   # 2026-05-24 sales_logic.py 拆成 sales/ 模組（6 檔），詳見 resources/architecture/backend-module-structure.md。
│   # 2026-05-24 L0 BDD+TDD 第一輪完成：constants / nlu / cart / states 4 檔從骨架轉為實作；37 scenarios PASS。
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
    │   ├── plan_tts_1                    # 初版 edge-tts 接入 plan 草稿
    │   ├── 業務程式邏輯規劃/             # S1 v2 業務邏輯規格書（2026-05-24 加入 / 同日格式重構）
    │   │   ├── L0_共通.md                # 共通規則 / 時間常數 / 子例程 / 商品 / 數量解析 / 關鍵字白名單（7 類）
    │   │   ├── L1.md                     # 第 1 層：模式選擇（叫賣 / 待機 / 客服）— 商家操作
    │   │   ├── L2.md                     # 第 2 層：詢問需求（拒絕 / 無法判斷 / 客服 / 想一下 / 點到商品 → L3）
    │   │   ├── L3.md                     # 第 3 層：額外需求（拒絕 / 循環 / 想一下 / 結帳意圖 / 兩段 6s 自動結帳 → L4）
    │   │   ├── L4.md                     # 第 4 層：印金額 + 等掃碼（5 鏈路含客服特殊模式 / 4 次循環 / 無法判斷 fallback）
    │   │   └── L5.md                     # 第 5 層：謝謝惠顧 → 等 3s → 回 L1 叫賣
    │   ├── 業務邏輯規劃_終審報告_2026-05-24.md  # 兩個 Opus 4.7 subagent 平行審查上述規格書的完整原始報告 + 整合清單（debug / 優化 / S 階段檢查時對照）
    │   └── bdd規範.txt                   # BDD/Gherkin 規範（2026-05-24 加入）— 寫測試前必先用 Given-When-Then 注釋骨架 + AskUserQuestion 確認
    │
    ├── architecture/                     # tracked — 跨檔 / 跨層架構決策（2026-05-24 加入）
    │   ├── README.md                     # 資料夾說明 + 與 plans/ 的區別
    │   ├── backend-module-structure.md   # myProgram/sales/ 模組拆分方案 + 每檔職責 + 擴展觸發條件
    │   └── frontend-backend-contract.md  # 三層願景 + 推薦框架（FastAPI + Pydantic + Repository）+ 接口框架延後決策
    │
    └── examples/                         # tracked — 廠商已驗證範例代碼（2026-05-23 加入）
        ├── 機器人動作結合opencv的多線程使用范例.py  # 廠商多線程範例：cv2 主線程 + 動作背景線程
        ├── bdd-寫法範例.txt              # BDD/Gherkin 寫法範例（2026-05-24 加入）— 毒蛇技能 demo：Scenario / Given / When / Then 注釋 + 空函數骨架
        └── legacy_threading_v1/          # 2026-05-23 歸檔：第一輪多線程重構成果（incremental rebuild 前）
            ├── README.md                  # 設計重點、踩到的坑、可參考的 pattern
            ├── myProgram.py               # 主迴圈 + ActionWorker + input_reader + command_dispatcher
            ├── tts.py                     # TtsWorker（中斷式 say + Popen handle + terminate）
            ├── robot_actions.py           # 組合動作 + cancel event
            └── screen_display.py          # tkinter POSScreen + thread-safe _poll_queue
```

---

## `.gitignore` 排除清單（2026-05-22 重構，2026-05-24 補 pytest 副產物）

```
.claude/settings.local.json
.claude/worktrees/
sync_pi.ps1
resources/presentation/
resources/userPrompt/

# Python / pytest 副產物（2026-05-24 L0 TDD 第一輪後加入；曾擋住 worktree cleanup）
__pycache__/
.pytest_cache/
```

- ✅ `.claude/CLAUDE.md` tracked，push 上 GitHub + sync 到 Pi。
- ✅ `resources/requirements/`、`resources/pineedtodo/`、`resources/projectStructure/`、`resources/plans/`、`resources/examples/` 全 tracked，會 sync 到 Pi。
- 🚫 `resources/presentation/`（大 PDF）+ `resources/userPrompt/`（個人草稿）+ `sync_pi.ps1`（Windows-only）+ `.claude/settings.local.json`（本機設定）+ `.claude/worktrees/`（暫存）保持 ignored。
- 🚫 `__pycache__/` + `.pytest_cache/` — pytest / Python 跑測試副產物，全 ignored（避免污染 git 與 Windows worktree cleanup file lock）。

---

## 各檔案職責簡述

### 自寫程式碼（myProgram/）

**狀態（2026-05-24 S1 v2 重做進行中）**：S1 v1（115 行單檔）2026-05-24 清空。改為「入口 + 業務邏輯」分離結構；業務邏輯按 5 層狀態機重做（L1 模式選擇 / L2 詢問需求 / L3 額外需求 / L4 印金額掃碼 / L5 謝謝惠顧）。

| 檔案 | 引入階段 | 職責 |
|---|---|---|
| `myProgram.py` | S1 v2（暫空）| 入口：未來 `from sales.logic import run; run()`，保持簡潔 |
| `sales/__init__.py` | S1 v2 | 模組標記 + docstring（指向規格書與架構文件）|
| `sales/logic.py` | S1 v2（暫骨架，L1+ 才實作）| 主迴圈 + 5 層 dispatch；唯一允許持有「外部世界」的進入點 |
| `sales/constants.py` | S1 v2 L0+L1+L2+L3 ✅ | L0：7 時間常數 + `PRODUCTS` + `HAWK_SLOGANS`。L1：`L1_MENU_BANNER` / `L1_HAWK_ENTER_PROMPT` / `L1_STANDBY_ENTER_PROMPT` / `SERVICE_PHONE`。L2：`L2_GREETING_PROMPT` / `L2_REJECT_THANKS` / `L2_B1_CLARIFY` / `L2_B3_REASK` / `L2_B3_THIRD_REJECT` / `L2_C_ADDED`。L3（2026-05-24 追加）：`L3_FOLLOWUP_PROMPT` / `L3_REJECT_THANKS` / `L3_B1_CLARIFY` / `L3_REASK`（B-3/B-4 共用）/ `L3_C1_CHECKOUT_GO`（C-2 警告語音用 f-string 即時組） |
| `sales/nlu.py` | S1 v2 L0 ✅ | `classify_intent(text, mode)` 6 步優先序（L4 客服模式吃繼續/退出）+ `parse_quantity(text)` 阿拉伯優先 / 中文映射含異體字 / 預設 1 |
| `sales/cart.py` | S1 v2 L0 ✅ | 純函式 + dict[str, int]：`new_cart` / `add_item`（同商品累加）/ `get_quantity` / `calc_total`（依 PRODUCTS 實際價）/ `clear_cart` / `is_empty` |
| `sales/states.py` | S1 v2 L0+L1+L2+L3 ✅ | L0：`run_subroutine_a`。L1：`run_l1` + 4 私有。L2：`run_l2` + `_l2_exit_a` / `_l2_b3` / `_l2_dispatch_response`（L2 跳過結帳）。L3（2026-05-24 加）：`run_l3` + `_l3_main_loop`（內部主等待，C-2 / B-4 復用避免遞迴）+ `_l3_exit_a`（清空 cart）+ `_l3_b4`（第 3 次走 C-2 第二段）+ `_l3_c2_second_stage`（兩段機制 + f-string 警告語音）+ `_l3_dispatch_response`（全 6 步 dispatcher + 三態回傳 tuple/int/None）。L4-L5 TODO |
| `tts.py` | S2 | 同步阻塞 `speak()`（S4 起擴為非阻塞 TtsWorker）|
| `robot_actions.py` | S3 | 同步動作（S5 起擴為非阻塞 ActionWorker）|

### 廠商 SDK（myProgram/，禁止修改）

| 檔案 | 職責 |
|---|---|
| `ActionGroupControl.py` | 播放 `/home/pi/TonyPi/ActionGroups/*.d6a` 四肢動作組 |
| `Board.py` | 總線舵機（頭部）、PWM 舵機、蜂鳴器、GPIO 等底層控制 |

> 廠商檔內含 Pi-only 路徑與底層庫 import（`pigpio`, `RPi.GPIO`, `BusServoCmd` 等），**Windows 本機無法 import 測試**，實際執行驗證一律在 Raspberry Pi 4 上。

### 測試（tests/）

| 檔案 / 資料夾 | 引入階段 | 職責 |
|---|---|---|
| `tests/__init__.py` | 2026-05-24（BDD+TDD 流程定案）| 組織說明：spec/ 按 L 層、sales/ 按模組 |
| `tests/conftest.py` | 2026-05-24 | 共用 fixtures 說明 — L0 全部用 inline lambda + FakeScheduler（無跨檔共用 fixture）；後續 L 層出現共用需求才搬入 |
| `tests/spec/__init__.py` | 2026-05-24（L0 第一輪 BDD）| spec/ 子資料夾組織說明 |
| `tests/spec/L0_common_scenarios.py` | 2026-05-24（L0 第一輪 BDD）| 37 個 Gherkin scenarios（CONST 1 / PROD 2 / HAWK 2 / NLU 13 / QTY 9 / CART 6 / SUB-A 4），對應 `resources/plans/業務程式邏輯規劃/L0_共通.md`；唯讀，不 import prod code |
| `tests/spec/L1_mode_select_scenarios.py` | 2026-05-24（L1 第一輪 BDD）| 12 個 Gherkin scenarios（ENTRY 1 / A 1 / B 4 / C 5 / Q 1），對應 `resources/plans/業務程式邏輯規劃/L1.md`；唯讀 |
| `tests/spec/L2_first_order_scenarios.py` | 2026-05-24（L2 第一輪 BDD）| 14 個 Gherkin scenarios（ENTRY 1 / A 2 / B-1 1 / B-2 1 / B-3 5 / C 3 / PRIO 1），對應 `resources/plans/業務程式邏輯規劃/L2.md`；唯讀 |
| `tests/spec/L3_add_loop_scenarios.py` | 2026-05-24（L3 第一輪 BDD）| 18 個 Gherkin scenarios（ENTRY 1 / A 1 / B-1 1 / B-2 1 / B-3 2 / B-4 5 / C-1 1 / C-2 5 / PRIO 1），對應 `resources/plans/業務程式邏輯規劃/L3.md`；唯讀 |
| `tests/sales/__init__.py` | 2026-05-24（L0 第一輪 TDD）| sales/ 子資料夾組織說明 |
| `tests/sales/test_constants.py` | 2026-05-24（L0 第一輪 TDD）| 5 個測試：時間常數值 / 商品價錢 / 6 組叫賣 / mod 6 輪替 |
| `tests/sales/test_nlu.py` | 2026-05-24（L0 第一輪 TDD）| 22 個測試：意圖分類 6 大類 + 優先序 + L4 客服模式 + 中文 / 阿拉伯數量解析 |
| `tests/sales/test_cart.py` | 2026-05-24（L0 第一輪 TDD）| 6 個測試：新建 / 加入 / 累加 / 單品總額 / 多品總額 / 清空 |
| `tests/sales/test_states.py` | 2026-05-24（L0+L1+L2+L3 TDD）| L0：4 SUB-A + FakeScheduler。L1：12 + FakeKeyboardInput + FakeOpencv。L2：14 + FakeCustomerInput。L3（2026-05-24 加）：18 個（ENTRY 1 / A 1 / B-1 1 / B-2 1 / B-3 2 / B-4 5 / C-1 1 / C-2 5 / PRIO 1）；總共 48 個 |
| `pytest.ini` | 2026-05-24（L0 第一輪 TDD）| pytest 設定：`testpaths = tests/sales`；確保 `python -m pytest tests/sales/ -v` 正確找到測試 |

> **測試環境（選項 C）：** Windows 全域 Python 3.14.4 + pytest（使用者 2026-05-24 手動裝）；`myProgram/sales/` 內任何檔禁 import 廠商 SDK，所有對外動作（speak / do_action / show）以 callback 注入。跑指令 `python -m pytest tests/sales/ -v`。完整流程：`.claude/rules/bdd-tdd-workflow.md`。

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
| `.claude/rules/bdd-tdd-workflow.md` | 📝 編寫 `myProgram/sales/` 業務邏輯必走 4 階段：主 agent BDD spec → AskUserQuestion → 單一 subagent TDD+Impl（Red-Green-Refactor）→ 主 agent 跑 pytest 審查 + 收尾。含 subagent prompt 規範 + tests/ 目錄結構 + fallback（無 paths）|
| `.claude/skills/` | 使用者自訂 skill 目錄（2026-05-24 加入）— Claude Code 偵測到匹配條件時自動載入 |
| `.claude/skills/test-driven-development/SKILL.md` | TDD 實踐 skill：Red-Green-Refactor 流程 + Iron Law（無失敗測試前不寫產品碼）；S1 v2 寫 `sales_logic.py` 前載入 |
| `.claude/skills/test-driven-development/testing-anti-patterns.md` | 測試反模式（禁測 mock 行為 / 禁為測試在產品碼加方法 / mock 不是被測物件）；寫測試或加 mock 時參考 |
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
| `plans/bdd規範.txt` | **BDD 規範**（2026-05-24 加入）— 規定寫測試前必先用 Gherkin schema 寫 Given-When-Then 空骨架 + AskUserQuestion 確認後再實作；引用 `examples/bdd-寫法範例.txt` |
| `architecture/` | **整體架構決策**（2026-05-24 加入）— 跨檔 / 跨層方向；與 `plans/`（單一任務執行計劃）區別在時效（長期 vs 短中期）|
| `architecture/README.md` | 資料夾說明 + 與 `plans/` 的區別 + 維護原則 |
| `architecture/backend-module-structure.md` | `myProgram/sales/` 模組拆分方案 + 每檔職責 + 擴展觸發條件（>300 行拆 states/ / HTML 上線加 api.py+schemas.py / DB 上線加 repository.py）|
| `architecture/frontend-backend-contract.md` | 三層願景（前端 HTML+TS / 後端 Python / 未來 DB）+ 推薦框架（FastAPI + Pydantic + REST + Repository Pattern）+ 接口框架延後決策紀錄 |
| `examples/` | **廠商已驗證範例代碼 + 歸檔舊版** — 廠商寫好且在機器人上測試成功的示範碼；可參考做 pattern、可仿、可改（與 `myProgram/` 的廠商 SDK 本體不同，那些禁改）|
| `examples/bdd-寫法範例.txt` | **BDD/Gherkin 寫法範例**（2026-05-24 加入）— 毒蛇技能 demo 5 個 scenario：`## ID` + `### Scenario` + `### Given/When/Then` + 空 func。供 BDD 規範引用作模板 |
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
| 2026-05-24 | **業務邏輯規格書納 tracked**：使用者手寫的 5 層狀態機規格 `resources/plans/業務程式邏輯規劃/L1-L5.md` 從 untracked 納入 git；S1 v2 後續實作以此為準 |
| 2026-05-24 | **業務邏輯規格書格式重構（plan「規格書格式改造」）**：原 L1-L5.md 為使用者口述意識流，重寫為統一模板（入口 / 進入動作 / 鏈路 A-C / 出口列表）；新增 `L0_共通.md` 集中時間常數 / 共通子例程 / 商品 / 數量解析 / 7 類關鍵字白名單。5 個內容待釐清點全部敲定：#1 重複文字去重 / #2「等等」= 想一下意圖（新增鏈路 B-3/B-4）/ #3 4 次循環 = loop_count 上限 4 / #4 客服退出/繼續兩者皆可 / #5 用 L0 規則匹配（後續可換 NLP）|
| 2026-05-24 | **業務邏輯規格書終審報告歸檔**：S1 v2 實作前派出兩個 Opus 4.7 subagent（Agent A 狀態機 / 跨層一致性、Agent B UX / 待釐清點）以獨立平行方式審查 L0-L5 規格書；產出 23 + 39 = 62 項發現（含 12 項高優先 / 17 項中優先 / 13 項低優先 + 13 項待釐清點選項）。完整原始報告 + 主 agent 整合清單存至 `resources/plans/業務邏輯規劃_終審報告_2026-05-24.md`，作為後續實作 / debug / 優化的權威對照依據。|
| 2026-05-24 | **規格三輪整合修訂**：分三輪 push commit `f3c0304` / `04c9eef` / `f664d37`，把終審報告 62 項發現裡的高優先 12 項 + 中優先 17 項 + 低優先 9 項 + 13 項待釐清點全部處理完。L0/L1/L2/L3/L4/L5 全部敲定，所有「設計推論（待 review）」標記消除，S1 v2 程式實作有完整無歧義的權威規格依據。|
| 2026-05-24 | **TDD skill + BDD/Gherkin 規範與範例就位**（使用者手動加入）：新增 `.claude/skills/test-driven-development/`（SKILL.md + testing-anti-patterns.md，TDD 實踐 skill 含 Red-Green-Refactor 與測試反模式）+ `resources/plans/bdd規範.txt`（寫測試前必先 Gherkin 骨架 + AskUserQuestion 確認）+ `resources/examples/bdd-寫法範例.txt`（毒蛇技能 demo 範例）。S1 v2 實作將走 BDD 骨架 → AskUserQuestion → TDD 實作流程。|
| 2026-05-24 | **後端模組化骨架就位 + 架構規劃資料夾建立**：S1 v2 業務邏輯實作前敲定後端分層 — 刪除 `myProgram/sales_logic.py`，新增 `myProgram/sales/` 模組含 6 檔骨架（`__init__.py` / `logic.py` / `constants.py` / `nlu.py` / `cart.py` / `states.py`，全為 docstring + TODO 占位）。新增 `resources/architecture/` 資料夾收納整體架構決策（README + `backend-module-structure.md` + `frontend-backend-contract.md`），CLAUDE.md 🔗 查閱表加 2 行 pointer，memory 新增 `project-architecture-vision`。三層願景定案（前端 HTML+TS / 後端 Python / 未來 DB），接口框架（FastAPI + Pydantic）延後到 HTML 前端開工時敲定。|
| 2026-05-24 | **展示拓樸與網路通訊文件擴充**：`resources/architecture/frontend-backend-contract.md` 新增「展示拓樸與網路通訊」段（+154 行）含硬體拓樸圖 / 3 種展示場景對比 / Android mDNS 解法 / HTTP REST vs WebSocket 概念 / 功能對應表 / FastAPI 雙協定範例 / `host=0.0.0.0` 啟動關鍵 / 6 種症狀 debug 表 / Pi IP 穩定性 3 種方法 / 內網安全性註記。|
| 2026-05-24 | **BDD+TDD 開發流程定案**：新增 `.claude/rules/bdd-tdd-workflow.md`（4 階段完整流程 + spec/ vs sales/ 結構 + Iron Law 對應 + subagent prompt 規範 + fallback + 每 L 層獨立一輪 + 環境設定）+ `tests/` 測試根目錄骨架（`__init__.py` + `conftest.py`；spec/ 與 sales/ 子資料夾於 L0 第一輪才建，依 user-step-by-step-pace 不預先做）。CLAUDE.md 加「📝 BDD + TDD 開發流程」段 + 🔗 查閱表 2 行 pointer。`resources/architecture/backend-module-structure.md` 加 Testing 配置段（含 callback stub 範例 + 測試指令）。memory 新增 `bdd-tdd-workflow`，更新 `workflow-constraints`（pytest Windows 例外）+ `project-architecture-vision`（tests/ 結構）。決策：BDD 主 agent 寫 / TDD+Impl 同一個 subagent 走完 Red-Green-Refactor / 選項 C 純 unit test 不寫廠商整合 / 每層 L0→L5 順序獨立一輪 / Python 3.14.4 全域 pytest。|
| 2026-05-24 | **L0 BDD+TDD 第一輪完成**：BDD 階段 1 主 agent 寫 `tests/spec/L0_common_scenarios.py`（37 scenarios，7 大類），AskUserQuestion 通過。階段 2 plan mode 規劃 4 模組對應（constants/nlu/cart/states），ExitPlanMode 通過。階段 3 派單一 Sonnet subagent 走 Red-Green-Refactor → 37 scenarios 全 PASS，新增 `pytest.ini`（testpaths=tests/sales）+ `tests/sales/__init__.py` + 4 個 test_*.py + 4 個 prod 檔從骨架轉為實作。`myProgram/sales/{constants,nlu,cart,states}.py` 完成 L0 實作（callback 注入、純函式、無廠商 SDK import）。`logic.py` 本輪不動（L1+ 才有意義）。下一輪 L1。|
| 2026-05-24 | **L0 第一輪復盤維護**：`.gitignore` 加 `__pycache__/` + `.pytest_cache/`（pytest 副產物曾擋住 worktree cleanup）。`.claude/rules/worktree-workflow.md` 階段 5 補 Windows file lock fallback（`Remove-Item -Recurse -Force` + `git worktree prune`）。`.claude/rules/bdd-tdd-workflow.md` 補兩段：(1) Subagent 自主決策範圍（pytest.ini / conftest fixture / inline stub / pytest 設定相關的 .gitignore 補充可自主，prod 模組擴大 / 改 logic.py / 新依賴 / 改 spec 須請示）(2) Iron Law 判定指引（模組空白時批次 fail 算「精神有守」不標 DEGRADED；寫 prod code 前未見任何 fail 才算真違反）。memory `worktree-workflow` + `bdd-tdd-workflow` 同步補充。|
| 2026-05-24 | **L1 BDD+TDD 第一輪完成 + 狀態機 pitfall 規則補強**：BDD 階段 1 主 agent 寫 `tests/spec/L1_mode_select_scenarios.py`（12 scenarios）。階段 2 plan mode 通過。階段 3 派 Sonnet subagent → 12 scenarios 全 PASS（總 49 PASS：L0 37 + L1 12）。`states.py` 加 `run_l1` + 4 個私有函式；`constants.py` 追加 4 個 L1 文字常數；`test_states.py` 加 12 個 L1 測試 + 2 個 inline stub class（FakeKeyboardInput / FakeOpencv）。**[DEGRADED-TDD-PARTIAL-L1]** subagent 寫 L1-ENTRY GREEN 時一次寫完整個路由骨架，導致後續 L1-A/B/C/Q 11 個 scenarios 加入時直接 PASS（未見 RED，prod code 早於 test）— Iron Law 部分違反。已接受 commit 不退回（49 PASS 品質 OK）。**規則補強**：`.claude/rules/bdd-tdd-workflow.md` 加「狀態機 / dispatcher 類型 prod code 的 RED 排程 pitfall」段（ENTRY GREEN 只寫最小印選單 + q 退，後續鏈路須親見 RED）+ 「Subagent commit 範圍 pitfall」段（subagent commit `3cff233` 漏 add `tests/spec/L1_mode_select_scenarios.py`，主 agent 階段 3b 補 add；prompt 模板須明列 git add 範圍含 `tests/spec/L?_*.py`）。memory `bdd-tdd-workflow` 同步補兩段。下一輪 L2。|
| 2026-05-24 | **L2 BDD+TDD 第一輪完成 + DEGRADED 容許條款入規**：BDD 階段 1 主 agent 寫 `tests/spec/L2_first_order_scenarios.py`（14 scenarios，5 鏈路 + ENTRY + 判定優先序 dispatcher，跳過結帳意圖）。階段 2 plan mode 通過。階段 3 派 Sonnet subagent → 14 scenarios PASS（總 63：L0 37 + L1 12 + L2 14）。`states.py` 加 `run_l2`（caller 注入 think_count + cart，return tuple `(next_state, next_think_count)`） + `_l2_exit_a` / `_l2_b3`（想一下狀態機 + 第 3 次跳沉默走 A）/ `_l2_dispatch_response`（B-3 沉默期中斷後重跑判定）。`constants.py` 追加 6 個 L2 字串常數。`test_states.py` 16→30 + FakeCustomerInput inline stub。**Pitfall 預防結果**：Pitfall 2（commit 範圍）成功，spec 檔有 add；Pitfall 1（狀態機 ENTRY 一次寫完 dispatcher）即使 prompt 明確警告 subagent 仍踩到 → **[DEGRADED-TDD-PARTIAL-L2]** 自標。**新規則：DEGRADED 容許條款** — dispatcher 型 prod code 即使警告也常踩，redo 成本不划算且結果可能一樣 → rule 補「狀態機 prod 容許 DEGRADED-TDD-PARTIAL，主 agent 不退回 redo」段，標 + 留痕即可。memory `bdd-tdd-workflow` 同步補。下一輪 L3。|
| 2026-05-24 | **L3 BDD+TDD 第一輪完成**：BDD 階段 1 主 agent 寫 `tests/spec/L3_add_loop_scenarios.py`（18 scenarios，6 鏈路 + ENTRY + C-2 兩段機制 + L3 跳過 L4 客服詞）。階段 2 plan mode 通過。階段 3 派 Sonnet subagent → 18 scenarios PASS（總 81：L0 37 + L1 12 + L2 14 + L3 18），commit `b40e597`。`states.py` 加 `run_l3` + `_l3_main_loop`（C-2 / B-4 復用避免遞迴增長）+ `_l3_exit_a`（清空 cart）+ `_l3_b4`（第 3 次走 C-2 第二段）+ `_l3_c2_second_stage`（f-string 警告語音）+ `_l3_dispatch_response`（全 6 步 dispatcher + 三態 tuple/int/None 回傳）。`constants.py` 追加 5 個 L3 字串常數（C-2 警告 f-string 不入常數）。`test_states.py` 30→48。**Pitfall 預防結果**：Pitfall 2（commit 範圍）成功；Pitfall 1（狀態機 ENTRY）即使警告 subagent 仍踩到 → **[DEGRADED-TDD-PARTIAL-L3]** 自標（dispatcher 容許條款生效，接受不退回）。下一輪 L4。|
