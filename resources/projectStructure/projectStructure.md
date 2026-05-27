# 專案目錄結構

> 本檔案記錄整個專案的資料夾與檔案結構，方便日後快速查閱。
> 最後更新：2026-05-27（S3 L3 action trigger fix：補上 L2→L3 transition 兩處 do_action(ACTION_L3) 觸發點）

---

## 完整結構（不含 `.git/` 內部檔案）

```
Project_01/
├── .claude/                              # Claude Code 設定資料夾
│   ├── CLAUDE.md                         # 📌 每輪載入的專案上下文 — tracked
│   ├── settings.json                     # 🔒 Claude Code project settings（含 hooks 配置）— tracked（2026-05-25 加）
│   ├── settings.local.json               # 本機 Claude 設定（gitignored）
│   ├── worktrees/                        # 暫存 worktree 目錄（gitignored；2026-05-22 加入）
│   ├── hooks/                            # 🪝 自動化 hook scripts（2026-05-25 加）— tracked，*.log / state/ gitignored
│   │   ├── NOTES.md                      # ⭐ 完整 hooks 研究筆記（30+ events 規格 / gotchas / future ideas）
│   │   ├── state/                        # flag file 暫存目錄（gitignored；三方協作 state）
│   │   ├── block-git-add-bulk.ps1        # PreToolUse Bash：擋 `git add -A` / `git add .`（執法 ⛔#4）
│   │   ├── block-vendor-edit.ps1         # PreToolUse Edit/Write：擋廠商 SDK 檔（執法 ⛔#1）
│   │   ├── auto-sync-pi.ps1              # PostToolUse Bash：`git push origin main` 後自動跑 sync_pi.ps1
│   │   ├── state-mark-sales-dirty.ps1    # PostToolUse Edit/Write：編 sales/* 時寫 flag
│   │   ├── state-clear-on-pytest.ps1     # PostToolUse Bash：pytest 跑過清 flag
│   │   ├── stop-check-sales-pytest.ps1   # Stop：結束 turn 前若 flag 存在 → block 一次提醒
│   │   ├── session-start-context.ps1     # SessionStart：注入 branch/status/test count 摘要
│   │   └── subagent-inject-rules.ps1     # SubagentStart：自動注入標準規範到 subagent context（依 agent_type 分流）
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
│   │   └── bdd-tdd-workflow.md           # 📝 BDD+TDD 開發流程（2026-05-25 path-scoped）— paths: myProgram/sales / tests/sales / tests/spec / 業務程式邏輯規劃
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
│   │   ├── L3_add_loop_scenarios.py      # L3 加單迴圈 18 個 scenarios（ENTRY/A/B-1/B-2/B-3/B-4/C-1/C-2/PRIO；2026-05-24 加入）
│   │   ├── L4_checkout_scenarios.py      # L4 結帳層 22 個 scenarios（ENTRY/A/B/C 客服特殊×9/D 6 次循環×5/E 無法判斷×5；2026-05-24 加入）
│   │   └── L5_thanks_scenarios.py        # L5 致謝層 4 個 scenarios（ENTRY 3 / A 1；最簡單一層；2026-05-24 加入）
│   └── sales/                            # TDD 階段產出（按 prod 模組；L0 第一輪 2026-05-24 建）
│       ├── __init__.py                   # 子資料夾說明
│       ├── test_constants.py             # 5 scenarios：L0-CONST + L0-PROD + L0-HAWK
│       ├── test_nlu.py                   # intent / quantity / normalize_input test（P7 移除 parse_products 部分）
│       ├── test_product_parser.py        # parse_products test（P7.S18 新增；從 test_nlu.py 拆出）
│       ├── test_cart.py                  # 6 scenarios：L0-CART
│       ├── test_states.py                # L0-L5 鏈路 integration test（含 FakeScheduler inline stub）
│       └── test_main_decode_error.py     # main.py UnicodeDecodeError / EOFError noisy debug 測試（2026-05-27 Wave 4 hotfix 3 加）
│   # 完整流程：.claude/rules/bdd-tdd-workflow.md
│   # 設計決策（選項 C 純 unit test）：resources/architecture/backend-module-structure.md
│
├── myProgram/                            # 主程式資料夾（S1 v2 重做中：業務邏輯改 5 層狀態機）
│   ├── __init__.py                       # Package 顯式標記（P6.S8 加；消除隱式 namespace package 行為）
│   ├── __main__.py                       # Package 入口點（支援 python -m myProgram；P6.S8 加）
│   ├── main.py                           # ✅ S1 chat-driven 入口層 wire-up（_S1State + _build_callbacks 11 個 callback → logic.run；原 myProgram.py，P6.S8 改名；S2 起 speak 改 call tts.speak）
│   ├── tts.py                            # ✅ S4 非阻塞 TTS worker（TtsWorker daemon thread + FIFO queue + shutdown；speak() 立即返回不阻塞主線程）
│   ├── vendor/                           # 🚫 廠商 SDK 隔離（2026-05-26 加）
│   │   ├── __init__.py                   # DO NOT MODIFY docstring
│   │   ├── ActionGroupControl.py         # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   │   └── Board.py                      # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   └── sales/                            # ✍️ 後端業務模組（2026-05-24 加入；L0-L5 完成 2026-05-24；B 類 refactor 2026-05-25）
│       ├── __init__.py                   # 模組標記 + docstring
│       ├── logic.py                      # ✅ 主迴圈 + 5 層 cycle dispatch + cart invariant fail-fast（A2-c / A4-c 落地）
│       ├── constants/                    # ✅ L0-L5 常數 subpackage（P8 拆分；原 274 行單檔；S3 加 actions）
│       │   ├── __init__.py               # re-export 全部子模組；對外 import path 向前相容
│       │   ├── timing.py                 # 時間 / 計數常數（WAIT_NO_RESPONSE / DNC_TIMEOUT / … / L4_SERVICE_TIMEOUT）
│       │   ├── products.py               # PRODUCTS dict + QTY_PROMPT_TEMPLATE / QTY_CLARIFY_TEMPLATE
│       │   ├── keywords.py               # HAWK_SLOGANS + KEYWORDS_CONFIRM_YES/NO + STRICT_SHORT 集
│       │   ├── shared.py                 # 跨層共用文案（SERVICE_PHONE / DIALOG_VAGUE_BUY_REASK）
│       │   ├── actions.py                # ✅ S3 動作組常數（ACTION_L1_HAWK/L2/L3/L4_PAY/L5_FAREWELL 對應 ActionGroups/*.d6a）
│       │   ├── l1_text.py                # L1 文字常數（L1_MENU_BANNER / HAWK_ENTRY / STANDBY_ENTRY / SERVICE_PHONE）
│       │   ├── l2_text.py                # L2 文字常數（ENTRY_PROMPT / REJECT / TIMEOUT / B1_CLARIFY / B3 / C_ADDED / UNCLEAR_REJECT）
│       │   ├── l3_text.py                # L3 文字常數（ENTRY / REJECT / B1_CLARIFY / REASK / C1_CHECKOUT / UNCLEAR_FINAL / CHECKOUT_CONFIRM_TEMPLATE / …）
│       │   ├── l4_text.py                # L4 文字常數（ENTRY_PROMPT_TEMPLATE / A_PAY / B_CANCEL / C_OPTIONS / D_FINAL / E_CLARIFY / 4 階段催促）
│       │   └── l5_text.py                # L5 文字常數（L5_THANKS）
│       ├── nlu.py                        # ✅ L0 純函式（classify_intent + parse_quantity + has_quantity；商品解析 P7 已拆出）
│       ├── product_parser.py             # ✅ 商品實體解析（parse_products；P7.S18 從 nlu.py 拆出）
│       ├── cart.py                       # ✅ L0 純函式（new_cart / add_item / calc_total / clear_cart 等）
│       └── states/                       # ✅ L0-L5 鏈路（2026-05-25 B4 拆 states.py；同日 L2/L3 合一為 dialog）
│           ├── __init__.py               # re-export run_? 函式（l0_subroutine_a / l1 / l2_l3_dialog / l4 / l5）
│           ├── _l2_l3_qty_followup.py    # L2/L3 鏈路 C 數量追問共享 helper（resolve_and_add_products；原 _product_helpers.py，P6.S9 改名）
│           ├── l0_subroutine_a.py        # L0 子例程 A（run_subroutine_a + _schedule_hawk；原 subroutine_a.py，P6.S9 改名）
│           ├── l1.py                     # L1 商家層（run_l1 + 4 私有）
│           ├── l2_l3_dialog.py           # L2/L3 合一對話層（run_dialog；cart 狀態驅動：cart 空=L2/非空=L3；原 dialog.py，P6.S9 改名）
│           ├── l4.py                     # L4 結帳層（run_l4 + 6 私有）
│           └── l5.py                     # L5 致謝（run_l5）
│   # 2026-05-23 incremental rebuild：tts.py / robot_actions.py / screen_display.py 歸檔
│   # 到 resources/examples/legacy_threading_v1/。後續 S2-S7 逐步加層。
│   # 2026-05-24 S1 v1（115 行單檔）清空重做為「入口 + 業務邏輯」分離結構。
│   # 2026-05-24 sales_logic.py 拆成 sales/ 模組（6 檔），詳見 resources/architecture/backend-module-structure.md。
│   # 2026-05-24 L0-L5 BDD+TDD 全層完成：107 unit tests PASS。
│   # 2026-05-25 sales 自審 + B 類 refactor 完成（A1+B2+B3+B4+B6；B1+B7 推遲到 logic.py 寫好後決定；B5 不修）。
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
    ├── reviews/                          # tracked — multi-agent 程式碼審查整合報告（2026-05-26 加入）
    │   ├── 2026-05-26_myProgram_multi-agent-review.md  # 4 視角（結構/狀態機/NLU/橫切面）對 myProgram/ 整合審查 + 8 階段 Roadmap
    │   └── 2026-05-26_myProgram_comprehensive_review.md  # 第二輪：3 個 opus xhigh subagent（架構 A / 健壯性 B / 業務 C）+ /review skill 視角 D，約 77 條 finding 統整
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
| `__init__.py` | P6.S8 ✅ | Package 顯式標記（docstring 含入口 / sales / vendor 說明）；消除隱式 PEP 420 namespace package 行為飄移 |
| `__main__.py` | P6.S8 ✅ | Package 入口點：`from myProgram.main import main` → `main()`；支援 `python -m myProgram` 簡潔跑法 |
| `main.py` | S1 v2 ✅ | S1 chat-driven 入口：`_S1State`（OpenCV 模擬狀態）+ `_build_callbacks` 建 12 個 callback → `logic.run(**callbacks)`；`'c'` 鍵模擬 OpenCV 觸發 / 空 Enter 模擬 customer timeout / `schedule` no-op 印警告（S1 單線程不真排程）；try/except SystemExit + KeyboardInterrupt；嚴格不 import 廠商 SDK（S3+ 才接）（原 `myProgram.py`，P6.S8 改名） |
| `sales/__init__.py` | S1 v2 | 模組標記 + docstring（指向規格書與架構文件）|
| `sales/logic.py` | S1 v2 ✅ | 主迴圈 + 5 層 cycle dispatch（L1→L2→L3→L4→L5→子例程 A→L1）；持有 cart 為唯一 cycle state（think_count/loop_count/unclear_count 由各 run_l? 內部管理）；每進新層 cart invariant fail-fast assert（`_assert_cart_empty` / `_assert_cart_nonempty`）— 違反立刻 raise AssertionError；callback dict keyword-only 傳入；嚴格不 import 廠商 SDK（選項 C） |
| `sales/constants/` | P8 ✅ / S3 擴 | L0-L5 常數 subpackage（2026-05-26 P8 從單一 274 行 `constants.py` 拆分；2026-05-27 S3 加 `actions.py`）；對外 `from myProgram.sales.constants import XXX` 向前相容；10 子模組按職責分組：`timing`（時間/計數）/ `products`（商品 dict + QTY template）/ `keywords`（CONFIRM_YES/NO + HAWK_SLOGANS）/ `shared`（跨層共用文案）/ `actions`（5 個 ACTION_* 動作組名）/ `l1_text` 到 `l5_text`（各層字串）；`__init__.py` 統一 re-export |
| `sales/nlu.py` | S1 v2 L0 ✅ | `classify_intent(text, mode)` 6 步優先序（L4 客服模式吃繼續/退出）+ `parse_quantity(text)` 阿拉伯優先 / 中文映射含異體字 / 預設 1 |
| `sales/cart.py` | S1 v2 L0 ✅ | 純函式 + dict[str, int]：`new_cart` / `add_item`（同商品累加）/ `get_quantity` / `calc_total`（依 PRODUCTS 實際價）/ `clear_cart` / `is_empty` |
| `sales/states/__init__.py` | S1 v2 B4 ✅ | re-export `run_subroutine_a / run_l1 / run_dialog / run_l4 / run_l5`（import path 對外不變）；P6.S9 同步更新內部 import 路徑 |
| `sales/states/l0_subroutine_a.py` | S1 v2 B4 ✅ | L0 共通子例程 A：`run_subroutine_a` + `_schedule_hawk`（原 `subroutine_a.py`，P6.S9 改名加層編號） |
| `sales/states/l1.py` | S1 v2 B4 ✅ | L1 商家層：`run_l1` + 4 私有（叫賣 / 待機 / 客服 / q 退出） |
| `sales/states/l2_l3_dialog.py` | S1 v2 B4 ✅ | L2/L3 合一對話層：`run_dialog` + 8 helper；cart 空=L2 模式/非空=L3 模式（cart 狀態驅動；原 `dialog.py`，P6.S9 改名） |
| `sales/states/_l2_l3_qty_followup.py` | S1 v2 B4 ✅ | L2/L3 鏈路 C 數量追問共享 helper：`resolve_and_add_products` + 無數量追問 sub-loop（原 `_product_helpers.py`，P6.S9 改名） |
| `sales/states/l4.py` | S1 v2 B4 ✅ | L4 結帳層：`run_l4`（3-tuple 回傳）+ `_l4_service_mode`（60s timeout）+ `_l4_d_speak_loop_voice`（4 階段語氣）+ `_l4_exit_b/_l4_exit_d_forced/_l4_dispatch_response/_l4_print_entry_detail` |
| `sales/states/l5.py` | S1 v2 B4 ✅ | L5 致謝：`run_l5`（純序列：mute_opencv → speak → clear_cart → sleep → return；無 dispatcher 無分支） |
| `tts.py` | S4 ✅ | 非阻塞 TTS worker — `class TtsWorker` daemon thread + `queue.Queue` FIFO + `threading.Lock` 保護 `_proc` reference；`speak(text)` 立即 `_q.put(text)` 返回（caller thread 也立即 print「[語音] xxx」保 log 時序）；worker `_loop` 從 queue 依序取 text → `asyncio.run(edge_tts.Communicate.save)` 合成 → `subprocess.Popen(["mpg123","-q",path], stdin=DEVNULL)` 播放 → `ALSA_DRAIN_SEC=0.3` drain → 下一輪；`shutdown()` 程式退出時 lock-protected `terminate()` 當前 mpg123 + 清 queue（main.py finally 呼叫）；**預設 FIFO 不中斷**（中斷是 S7）；`import edge_tts` fail-fast；runtime 失敗 noisy print + continue（synth/play 各自 except，含 shutdown SIGTERM CalledProcessError negative returncode）；caller `main.py` speak callback 內 lazy import 避 Windows pytest 觸發 ModuleNotFoundError |
| `robot_actions.py` | S3 | 同步動作（S5 起擴為非阻塞 ActionWorker）|

### 廠商 SDK（myProgram/vendor/，禁止修改）

| 檔案 | 職責 |
|---|---|
| `vendor/__init__.py` | DO NOT MODIFY docstring — 廠商 SDK 隔離資料夾說明（2026-05-26 加） |
| `vendor/ActionGroupControl.py` | 播放 `/home/pi/TonyPi/ActionGroups/*.d6a` 四肢動作組 |
| `vendor/Board.py` | 總線舵機（頭部）、PWM 舵機、蜂鳴器、GPIO 等底層控制 |

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
| `tests/spec/L4_checkout_scenarios.py` | 2026-05-24（L4 第一輪 BDD）| 22 個 Gherkin scenarios（ENTRY 1 / A 1 / B 1 / C 9 / D 5 / E 5），對應 `resources/plans/業務程式邏輯規劃/L4.md`；唯讀 |
| `tests/spec/L5_thanks_scenarios.py` | 2026-05-24（L5 第一輪 BDD）| 4 個 Gherkin scenarios（ENTRY 3 / A 1），對應 `resources/plans/業務程式邏輯規劃/L5.md`；唯讀 |
| `tests/sales/__init__.py` | 2026-05-24（L0 第一輪 TDD）| sales/ 子資料夾組織說明 |
| `tests/sales/test_constants.py` | 2026-05-24（L0 第一輪 TDD）| 5 個測試：時間常數值 / 商品價錢 / 6 組叫賣 / mod 6 輪替 |
| `tests/sales/test_nlu.py` | 2026-05-24（L0 第一輪 TDD）| 22 個測試：意圖分類 6 大類 + 優先序 + L4 客服模式 + 中文 / 阿拉伯數量解析 |
| `tests/sales/test_cart.py` | 2026-05-24（L0 第一輪 TDD）| 6 個測試：新建 / 加入 / 累加 / 單品總額 / 多品總額 / 清空 |
| `tests/sales/test_states.py` | 2026-05-24（**L0-L5 全齊** TDD）| L0：4 SUB-A + FakeScheduler。L1：12 + FakeKeyboardInput + FakeOpencv。L2：14 + FakeCustomerInput。L3：18 + 三態 dispatcher pattern。L4：22（含客服特殊模式 9 子情境 + 4 階段語氣）。L5（2026-05-24 加）：4 個（ENTRY 3 / A 1，inline lambda stub）；**總共 74 個** |
| `tests/sales/test_logic.py` | 2026-05-26（Wave 0 安全網）| **6 個測試**：覆蓋 `logic.py` 主控狀態機 — cart invariant fail-fast / L1 None 終止 / dialog 退出 / L4 非掃碼退出 / L5 退出 / `enter_hawk_immediately` consume-after-use 三輪旗號來源驗證。callback 全 stub（`_make_callbacks` factory），用 `monkeypatch.setattr` patch states 模組 function。對應 review HP-10 / D1 / D6 |
| `tests/sales/test_nlu_boundary.py` | 2026-05-26（Wave 0 安全網）| **23 個 xfail cases**：mark Wave 3 待修的 NLU 邊界誤判 — HP-1「沒有」substring（3）/ HP-1+C5「不了」substring（4）/ HP-2 negation guard（3）/ HP-4「等等」L4 ACK 漏（1）/ B5+D10 複合中文數字（5）/ B16「0 瓶」silent fallback（2）/ C12「沒事/沒問題」L3 結帳（2）/ C18「好了/對了/好啊」L2 肯定（3）。Wave 3 修完後拔 xfail 改綠燈 |
| `tests/sales/test_main_decode_error.py` | 2026-05-27（Wave 4 hotfix 3）| **4 個測試**：`myProgram/main.py` 兩個 callback（`read_terminal_key` / `read_customer_input`）對 `UnicodeDecodeError` / `EOFError` 的 noisy debug 處理 — 用 `monkeypatch.setattr("builtins.input", ...)` 模擬 raise，`capsys` 捕 stdout 斷言含 `"raw hex"` + 失敗 byte 的 hex 字串（單 byte「c3」與多 byte「c328」各覆蓋）+ 對應 return value（`""` / `None`） |
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
| `reviews/` | **multi-agent 程式碼審查整合報告**（2026-05-26 加入）— 主 agent 派多個 opus subagent 不同視角審查 myProgram/ 或其他模組，產出統整 markdown 含跨視角共識點 / 必修建議修可不改清單 / 階段 roadmap。append-only，每輪新增一檔（檔名 `<YYYY-MM-DD>_<scope>_<short_name>.md`）|
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
| 2026-05-24 | **L4 BDD+TDD 第一輪完成（嚴格 TDD 無 DEGRADED）**：BDD 階段 1 主 agent 寫 `tests/spec/L4_checkout_scenarios.py`（22 scenarios，L 系列最複雜：客服特殊模式 9 子情境 + 6 次循環 4 階段語氣 + 雙計數器 + dispatcher 過濾 3 類 + E→C 自動串接）。階段 2 plan mode 通過。階段 3 派 Sonnet subagent → 22 scenarios PASS（總 103：L0 37 + L1 12 + L2 14 + L3 18 + L4 22），commit `8624f5e`。`states.py` 加 `run_l4`（**3-tuple 回傳**）+ `_l4_service_mode`（60s timeout 6 種 trigger）+ `_l4_d_speak_loop_voice`（4 階段語氣）+ `_l4_exit_b` / `_l4_exit_d_forced` / `_l4_dispatch_response`（過濾 3 類 + 三態回傳）+ `_l4_print_entry_detail`。`constants.py` 追加 12 個 L4 常數。`test_states.py` 48→70。**Pitfall 結果**：(1) Pitfall 2 commit 範圍成功；(2) **Pitfall 1 嚴格走完未踩** — subagent 採「22 test 一次寫 → 全 fail → prod 一次寫 → 全 PASS」批次模式（同 L0 純函式批次 fail 變體），所有 22 scenarios 的測試都先見過 fail 才寫 prod，符合 Iron Law 字面與精神。對比 L1/L2/L3 是 ENTRY GREEN 一次寫 dispatcher → 後續 scenarios 立即 PASS（未見 fail）— L4 模式不同，prod 不早於任何 test。**主 agent 通過不標 DEGRADED**。下一輪 L5（最後一層）。|
| 2026-05-24 | **🎉 L5 BDD+TDD 第一輪完成 — 5 層業務邏輯全齊全（L0-L5）**：BDD 階段 1 主 agent 寫 `tests/spec/L5_thanks_scenarios.py`（4 scenarios，最簡單一層：無顧客互動 / 無 dispatcher，純序列 mute→speak→clear_cart→sleep→return）。階段 2 plan mode 通過（推薦新加 `sleep` callback）。階段 3 派 Sonnet subagent → 4 scenarios PASS（總 **107**：L0 37 + L1 12 + L2 14 + L3 18 + L4 22 + L5 4），commit `385e693`。`states.py` 加 `run_l5`（純序列函式約 30 行，採 `sleep` callback）。`constants.py` 追加 `L5_THANKS`。`test_states.py` 70→74（inline lambda stub）。**Iron Law 判定**：ENTRY-001 GREEN 寫完整 `run_l5` 後 scenarios 2-4 立即 PASS，但 L5 是 pure sequence 不是 dispatcher（強行拆 4 個函式逐 RED 屬 over-engineering），每個 scenario 有獨立 assert 驗證對應行為 → **不標 DEGRADED**（pure sequence prod 灰色地帶接受）。**🏁 5 層業務邏輯齊全里程碑** — 接下來可寫 `myProgram.py` 入口層 wire-up callback / S2 接 edge-tts / S3 加機器人動作 / HTML 前端開工（觸發 architecture decisions）。|
| 2026-05-25 | **sales 自審 + B 類 refactor 完成**：主 agent 寫 `resources/plans/sales_自審報告_2026-05-24.md`（commit `a8c2275`）列 A/B 兩類疑點與使用者討論。A 類決策：A1 立即修；A2 採 A2-c（logic.py 寫 state-machine dispatch，callback wire-up 在 myProgram.py）；A3 採 A3-d（先按現況跑 wire-up 驗證痛點）；A4 採 A4-a + A4-c（信任規格 + 入口層加 invariant check）。B 類 refactor 3 個 commit：(1) `3ed2faf` A1 docstring + B3 命名統一（5 個 _ENTRY_PROMPT）+ B6 _schedule_hawk_l1 函式位置；(2) `3d0f141` B2 L5 sleep→read_customer_input；(3) `c35345f` B4 拆 `states.py` 1085 行→`states/` 子資料夾 6 檔（subroutine_a / l1 / l2 / l3 / l4 / l5）+ `__init__.py` re-export（import path 不變）。**B 類推遲 / 不修**：B1+B7（return shape 統一）跟 A2 logic.py 設計強耦合 → 推遲到 logic.py 寫好後一起決定；B5（dispatch_response 重複）分支獨立 evolve 安全 → 不修。pytest 107/107 全程 PASS 不破。下一輪寫 logic.py + myProgram.py 入口層 wire-up。|
| 2026-05-25 | **🔌 S1 v2 logic.py 串接 + myProgram.py 入口層 wire-up 完成**（commit `a1fe336`，派 Sonnet subagent 在 `.claude/worktrees/logic-wireup-s1/`）：(1) `myProgram/sales/logic.py` 152 行 A2-c state machine — `run(**callbacks)` 持 cart 為唯一 cycle state，5 層 cycle dispatch（L1→L2→L3→L4→L5→子例程 A→L1），`_invoke_subroutine_a` helper，A4-c `_assert_cart_empty` + `_assert_cart_nonempty` 每進新層 fail-fast 守衛；(2) `myProgram/myProgram.py` 139 行 A3-d 直 wire callback dict — `_S1State` class 持 OpenCV 模擬狀態（`opencv_enabled` / `opencv_dwell`）、`_build_callbacks` 建 12 個 callback（含 `'c'` 鍵模擬 OpenCV 偵測一次性消耗 + 空 Enter 模擬 customer timeout + `schedule` no-op + `[語音]` / `[動作]` / `[opencv]` 文字標記）、`main()` try/except SystemExit + KeyboardInterrupt。兩檔皆嚴格不 import 廠商 SDK（選項 C 一致；廠商 SDK grep 命中只在 vendor 檔自身）。**既有 107 tests PASS 不破**（驗證 logic.py 沒誤汙染 import path）。S1 v2 全套可端對端跑 `python -m myProgram.myProgram` 做對話模擬。**為何不走 BDD+TDD**：本輪是 dispatcher 整合膠水 + audit 取代 TDD（user 明確決策）；下一步使用者手動互動驗收 → 派 3 個 audit subagent 全面審查 sales/。|
| 2026-05-25 | **🏗️ B 方案重構：L2/L3 合一為 dialog（cart 狀態驅動）**：架構級重構，原則「state machine 由世界狀態（cart）驅動，非動作歷史驅動」。動機：未來加刪除商品功能時，動作驅動架構會在 L3 cart 變空仍問「還需要什麼東西嗎？」違和。改動：(1) 新增 `states/dialog.py`（`run_dialog` + 8 helper），cart 空 = L2 模式 / cart 非空 = L3 模式，模式每輪 main loop 重新判定；(2) 刪除 `states/l2.py` + `states/l3.py`；(3) `logic.py` 4 層 cycle（L1→dialog→L4→L5），少一個 transition；(4) `states/__init__.py` re-export 改為 `run_dialog`；(5) `L0_共通.md` 加「層狀態判定原則」段，L2/L3.md 加架構說明標頭 + 變更紀錄。Tests: 153→159 PASS（10 個既有 L2→L3 assertion 改為 L4，因 dialog 自然繼續到 C-2 auto-checkout；+6 新 dialog cart-state-driven 測試）。未來加刪除商品時，dialog 主迴圈自動回 L2 prompt 模式無需額外 transition。|
| 2026-05-25 | **🪝 Claude Code hooks 上線（自動化執法 + sync_pi 自動觸發）**：新增 `.claude/settings.json`（project-level，commit 上去）+ `.claude/hooks/` 3 個 PowerShell scripts。Hook A（PreToolUse Bash）擋 `git add -A` / `git add .`，Hook B（PreToolUse Edit/Write）擋廠商 SDK 檔編輯，Hook C（PostToolUse Bash + async）`git push origin main` 後自動跑 sync_pi.ps1（取代 standard-workflow 步驟 5 的手動跑）。所有 3 個 hook 用官方 JSON 決策格式（`hookSpecificOutput.permissionDecision`），實測 3 個 PASS / 3 個 BLOCK case 全對。.ps1 用 UTF-8 BOM 編碼（PowerShell 5.1 無 BOM 會用 ANSI 誤讀中文字串）。`.claude/hooks/*.log` 加進 `.gitignore`。CLAUDE.md ⛔#1 / ⛔#4 加 🔒 註明 hook 強制執法（規則保留作文檔但執法不靠主 agent 自律）。|
| 2026-05-25 | **🪝 Stop + SessionStart hooks 上線（regression 守門 + session 自動 context 注入）**：新增 4 個 PS scripts + 完整 `NOTES.md` 研究筆記。**Stop hook（flag file 三方協作）**：state-mark-sales-dirty（PostToolUse Edit/Write）→ 編 sales/* 寫 flag；state-clear-on-pytest（PostToolUse Bash）→ pytest 跑過清 flag；stop-check-sales-pytest（Stop）→ 若 flag pending 則 block 一次 + 改 reminded（防無限循環）。**SessionStart hook**：每 session 開始（startup/resume/clear/compact 都跑）注入 git branch / status / sales tests count 摘要；agent_id 存在則 silent exit（不污染 subagent context）。**NOTES.md（毫無保留）**：30+ events 完整清單 / 5 個 decision patterns 速查 / 9 個踩坑 / cross-check 結果（subagent 推測 vs 官方）/ 11 個未實作但有用的功能 / 維護指南。**Cross-check 規範**：所有 hook 規格都經「subagent + 主 agent WebFetch + 第三輪驗證衝突點」三方確認後才動手。Tests 9/9 case 全通過。CLAUDE.md ⛔ 段加 3 行 sub-note + pointer 到 NOTES.md。|
| 2026-05-25 | **🪝 SubagentStart hook + rules 精簡（hook 接管後文檔對齊）**：(1) 新增 `subagent-inject-rules.ps1` — SubagentStart hook，依 agent_type 分流自動注入標準規範（編碼類完整版 / 研究類精簡版），取代 subagent-dispatch-protocol 步驟 2-3 的手動塞規則。(2) **精簡 rules + memory** — standard-workflow / worktree-workflow / bdd-tdd-workflow / incremental-rebuild 全部改「push（hook 自動 sync）」描述，從 5 步收尾改 4 步；subagent-dispatch-protocol 步驟 2-3 重寫為「hook 自動注入 + 任務特化規則手動塞」；MEMORY.md 索引、standard_workflow.md / workflow_constraints.md / project_deployment.md / incremental_rebuild_pattern.md / worktree_workflow.md / subagent_dispatch.md 全部同步「hook 已自動化」狀態。CLAUDE.md ⛔ 段加 SubagentStart 註腳；部署資訊段標明「hook 自動 + 手動 fallback」。159 tests 仍 PASS。Bash hook 自動觸發測試通過。|
| 2026-05-25 | **📝 `bdd-tdd-workflow.md` 改 path-scoped**：加 paths frontmatter（`myProgram/sales/**/*.py` / `tests/sales/**/*.py` / `tests/spec/**/*.py` / `resources/plans/業務程式邏輯規劃/**/*.md`）。動到 sales 相關檔才自動載入（規則含 DORMANT 標記 + 重啟條件，Claude 自行判斷本輪是否真要重啟）。當前 path-scoped rules 從 3 個增加至 4 個（vendor-sdk-api / path-conventions / threading-conventions / bdd-tdd-workflow）。CLAUDE.md 查閱表行 + 維護原則段對齊。|
| 2026-05-26 | **🔧 P1：dead code 清理 + 廠商 SDK 隔離**：(1) `do_action` callback 從 dialog/l4/l5/logic/wireup 簽名 + dict 移除（S1 stage 從未呼叫）；`_dialog_c2_auto_checkout` 純 forward wrapper 移除，2 caller 改直呼 `_dialog_c2_second_stage`；tests/ 同步移除對應 stub。(2) `git mv` 廠商檔 → `myProgram/vendor/{ActionGroupControl,Board}.py`；新增 `myProgram/vendor/__init__.py`（DO NOT MODIFY docstring）；`.claude/hooks/block-vendor-edit.ps1` regex 更新涵蓋 `myProgram/(?:.+/)?<file>.py`（future-proof）；CLAUDE.md ⛔#1 路徑更新；173 tests PASS（兩個 commit 均通過）。|
| 2026-05-26 | **🔍 multi-agent 程式碼審查整合報告**：使用者要求對 myProgram/ 派 `/review`（build-in）+ 結構/檔名（opus xhigh）+ 主 agent 自選 2 個（狀態機正確性 / NLU 健壯性，皆 opus xhigh）+ 主 agent 補 /review 適配版（橫切面 wire-up/風格/效能/安全），共 4 視角獨立並行審查。注：`/review` 內建 skill 是 PR 審查工作流（單一 prompt 非 3 subagent），與當前無 open PR 不契合，主 agent 改採 5 維度做適配版審查。產出：新建 `resources/reviews/` 資料夾 + 首份報告 `2026-05-26_myProgram_multi-agent-review.md`（含跨視角共識點 / 必修 7 條 + 建議修 18 條 + 可不改 15 條總表 + 8 階段 P0-P8 執行 Roadmap）。最關鍵發現：C-2 strict yes/no 內 NO 詞表「沒了/不要/沒有」與 L3 normal 結帳意圖語意衝突（顧客錢包逆向錯誤）；廠商檔位置應隔離到 `myProgram/vendor/`；`do_action`/`schedule` 是 dead callback 應清理。|
| 2026-05-26 | **🏷️ P6.S8：`myProgram.py` 改名 `main.py` + package 顯式化**：`git mv myProgram/myProgram.py myProgram/main.py`（消除 package 與 module 同名造成的 namespace 模糊）；新增 `myProgram/__init__.py`（顯式 package，避免隱式 PEP 420 namespace package 行為飄移）；新增 `myProgram/__main__.py`（支援 `python -m myProgram` 簡潔跑法）。`tests/sales/test_states.py` L1-ENTRY-001 Given 注釋同步更新為新跑法。Pi 端跑法改變：舊 `python3.11 -m myProgram.myProgram` → 新 `python3.11 -m myProgram`（推薦）或 `python3.11 -m myProgram.main`。回歸視角 A §3.1 / §3.2。180 tests PASS。|
| 2026-05-26 | **🏷️ P6.S9：states/ 三檔改名統一層編號制**：`subroutine_a.py → l0_subroutine_a.py`（L0 共通子例程）、`dialog.py → l2_l3_dialog.py`（L2/L3 合一對話層）、`_product_helpers.py → _l2_l3_qty_followup.py`（L2/L3 鏈路 C 數量追問 helper）。`states/__init__.py` import 路徑 + docstring 同步更新；`l2_l3_dialog.py` 內部 import `_product_helpers` → `_l2_l3_qty_followup` 同步更新。命名與規格書 L?_共通.md / L1-L5.md 層編號對齊，讀目錄即知對應層。職責表同步更新 states/ 各子模組。回歸視角 A §3.3。180 tests PASS。|
| 2026-05-26 | **📦 P8：constants.py 拆 constants/ subpackage**：`myProgram/sales/constants.py`（274 行）拆為 `myProgram/sales/constants/` subpackage（`__init__.py` + 8 子模組）。`timing.py`（時間/計數常數）/ `products.py`（PRODUCTS + QTY template）/ `keywords.py`（CONFIRM_YES/NO + HAWK_SLOGANS）/ `l1_text.py` 到 `l5_text.py`（各層字串）。`__init__.py` 以 `from .submodule import *` 統一 re-export，對外 `from myProgram.sales.constants import XXX` 完全向前相容、零 caller 修改。回歸視角 A §3.6。184 tests PASS。|
| 2026-05-26 | **🔀 P7.S18：nlu.py 商品實體解析拆出 product_parser.py**：從 `nlu.py` 拉出商品實體相關碼到新檔 `myProgram/sales/product_parser.py`（`parse_products` + `_parse_quantity_in_window` + `_PRODUCT_KEYWORD_TO_NAME`）；`nlu.py` 保留純意圖識別（`classify_intent` / `parse_quantity` / `has_quantity` / `normalize_input` / `_KEYWORDS_*` / `_CHINESE_DIGIT_MAP`）；`product_parser.py` 從 `nlu` import `_CHINESE_DIGIT_MAP` / `_KEYWORDS_ICED_TEA` / `_KEYWORDS_SCRATCH`（keyword sets 留 nlu 作第一公民）。callers 同步：`l2_l3_dialog.py` 改 `from myProgram.sales.product_parser import parse_products`。tests 拆分：`tests/sales/test_product_parser.py`（新，16 個測試）從 `test_nlu.py`（移除 `nlu.parse_products` 呼叫）拆出。回歸視角 A §3.7。184 tests PASS。|
| 2026-05-26 | **🔍 第二輪 multi-agent 程式碼審查**：使用者要求對 `myProgram/` 派 `/review` 內建工具 + 3 個 opus xhigh subagent（主題由主 agent 定）共審。主 agent 自選 3 個主題（A 架構與模組設計 / B 正確性、健壯性、多線程 / C 業務邏輯與對話流程）；`/review` skill 是 PR review 工作流，主 agent 套用其 5 個審查角度（test coverage / conventions / performance / security / correctness）做 codebase review 適配（來源 D）。產出 `resources/reviews/2026-05-26_myProgram_comprehensive_review.md`：共 4 個獨立來源、約 77 條 finding、10 條跨來源高優先（HP-1 ~ HP-10）+ 5 層統合處理順序 + 風險評估表 + 12 條好實踐 + 16 條對話腳本盲點 + 文案品質速覽。最關鍵新發現：(1) `tests/sales/test_logic.py` 不存在（BDD 規範自身列出但未建立，logic.py 編排層完全無 unit test）；(2) NLU substring「沒有 / 不了」誤命中「沒有問題 / 等不了」等口語 → 顧客錢包風險；(3) L3 結帳前 confirm 文案沒列總金額。|
| 2026-05-26 | **🛡️ Wave 0：測試安全網（commit `d60798e`）**：依 review HP-10 / D1 / D6 補兩個 test 檔到 `tests/sales/`。(1) `test_logic.py`（6 PASS）覆蓋 `logic.py` 主控狀態機 — cart invariant fail-fast / L1 None 終止 / dialog 退出 / L4 非掃碼退出 / L5 退出 / `enter_hawk_immediately` consume-after-use；callback 全 stub（inline lambda + `_make_callbacks` factory），用 `monkeypatch.setattr` patch states 模組 function。(2) `test_nlu_boundary.py`（23 XFAIL）mark Wave 3 待修的 NLU 邊界誤判 — HP-1「沒有/不了」substring / HP-2 negation guard / HP-4「等等」L4 ACK 漏 / B5+D10 複合中文數字 / B16「0 瓶」silent fallback / C12 L3「沒事/沒問題」/ C18 L2「好了/對了/好啊」。pytest 最終 203 passed, 23 xfailed。**踩到 Gotcha M**：subagent 在 worktree 內 commit 直接落 main（非 worktree branch），主 agent 走 workaround 跳過 ff-merge 直接 push。純加 test 不動 prod code。|
| 2026-05-27 | **🩹 Wave 4 hotfix 3：`main.py` UnicodeDecodeError noisy debug**（commit `50d8b67`，派 opus xhigh subagent）：使用者在 Pi 跑 `python3.11 -m myProgram` 輸入「皆可」時觸發 UnicodeDecodeError，原 except 印一行籠統「輸入解析失敗（UnicodeDecodeError），視為 timeout」就吃掉，無法 debug。Pi 端 locale 已確認全 UTF-8（`LANG=zh_TW.UTF-8` / 全 LC_* / Python `sys.stdin.encoding=utf-8`），非 locale 設錯，疑似 IME / SSH transit / 異常 byte 序列。改動：`myProgram/main.py` 兩處 except 從 `(UnicodeDecodeError, EOFError)` 拆成兩個 except — UnicodeDecodeError 印 `codec` / `reason` / `start-end` / **raw bytes hex** + 友善提示「請截圖回報以上訊息給開發者排查」；EOFError 獨立簡短訊息（EOFError 無 start/end/reason/object/encoding 屬性）。新增 `tests/sales/test_main_decode_error.py`（4 個 PASS）— 模擬兩種 exception × 兩個 callback，capsys 斷言 hex 字串輸出 + return value。pytest 242 → 246 PASS。下一步：使用者 SSH Pi 重現「皆可」截取 hex byte 給開發者排查根因。|
| 2026-05-27 | **🔊 S2：同步 TTS 模組落地（incremental-rebuild 第 2 步）**：新增 `myProgram/tts.py`（同步 TTS — `asyncio.run(edge_tts.Communicate(text, voice="zh-TW-HsiaoChenNeural").save("/tmp/last_tts.mp3"))` 合成 + `subprocess.run(["mpg123","-q",path], check=True)` 阻塞播放至播完；剝離舊版 `legacy_threading_v1/tts.py` 的 TtsWorker / queue / Lock / 中斷邏輯 — 那些是 S4+ 才加）。失敗策略對齊 [[roadmap]] 決議：(1) `import edge_tts` 失敗 → 直接 ImportError 冒（fail-fast，**不** silent fallback `_ENABLED=False`）；(2) runtime 失敗（合成 / 播放炸）→ noisy print 詳細訊息（含 exception type / args / 階段 synth-vs-play / text）+ return（不 raise，caller dialog 繼續下一字）；分階段 try/except 含 `FileNotFoundError`（mpg123 未裝）/ `CalledProcessError`（退出碼非 0）/ 兜底 `Exception`。`myProgram/main.py` 的 `speak` callback 從 `print(f"[語音] {text}")` stub 改 `tts.speak(text)`；`from myProgram import tts` 放 callback 內 lazy import（**非** top-level）— 避免 Windows pytest 經 `test_main_decode_error.py → from myProgram.main import _build_callbacks` 連帶觸發 `import edge_tts` 而 Windows 沒裝 `edge_tts`（規範禁裝）。Pi 端啟動後 L1 hawk entry 第一次 speak 仍立即觸發 import，缺套件仍 fail-fast，不違反 noisy 原則。**248 tests PASS**（不動 sales/ 任何檔，callback 介面 signature 不變）。Pi 端需求：`pip install edge-tts` + `sudo apt install mpg123` + `raspi-config` 選音訊出口（HDMI / 3.5mm / USB）+ `alsamixer` 調音量 + 確認喇叭連接；詳見 `resources/pineedtodo/2026-05-27_S2_tts_setup.md`。incremental-rebuild S1→S2 進展，下一步 S3 同步動作（廠商 `Act.runAction()` 阻塞播完）。|
| 2026-05-27 | **🔊 S4：非阻塞 TTS worker thread + queue 落地（跳過 S3 直接做，commit `179e55b`）**：使用者 Pi 實測 S2 同步阻塞 TTS 帶來兩個問題 — (1) L1 hawk speak 期間商家按 q 想退出需等 speak 播完 ~3-5s 才響應（主線程被 mpg123.wait() 卡死、input() 沒在跑、q 只能存 stdin buffer）；(2) 程式結束時最後段 mpg123 仍在播完才停（沒 cleanup）。**S4 設計（派 opus xhigh subagent + 6 招防護）**：`myProgram/tts.py` 重寫為 `class TtsWorker` — `queue.Queue` FIFO + `threading.Lock` 保護 `_proc` 引用 + daemon thread 跑 `_loop`（get text → synth → Popen mpg123 + wait → drain → 下一輪）；`speak(text)` 對外 signature 不變（仍 module-level 函式）但內部變成「caller thread 立即 print『[語音] xxx』+ `_worker.say(text)` 入 queue 立即 return」；新增 `shutdown()` lock-protected `terminate()` 當前 mpg123 + 清空 queue；`main.py` `main()` 加 `finally: tts.shutdown()`（lazy import + except ImportError pass for Windows pytest）。**設計關鍵**：(a) **預設 FIFO 不中斷**（依 incremental-rebuild S4 規定，中斷是 S7）；(b) Lock **只**包 `_proc` 賦值/讀/terminate 三短瞬間，**不**包 `wait`，否則 shutdown 拿不到 lock 就 defeat；(c) `print` 在 caller thread（保 SSH log 時序）；(d) `stdin=DEVNULL` 保留（防 mpg123 偷讀）；(e) ALSA drain 0.3s 保留；(f) SIGTERM 觸發走 CalledProcessError negative-returncode path，noisy print 仍走，屬 expected exit。**245 tests PASS**（不動 sales/ + tests/，callback signature 完全相容）。**解決使用者三個訴求**：q 立刻響應（主線程不再被 speak 卡）/ exit 時最後音檔立刻停（shutdown terminate）/ 為 S6 真 opencv 偵測鋪路（主線程現在可 poll）。incremental-rebuild S2 → S4 跳過 S3，S3 同步動作後續再做（rule「S3 後可暫停 S4-S7」反向應用：S3 / S4 互不依賴，可亂序）。|
| 2026-05-27 | **🩹 S2/S4 session UX 補強迴圈**（14 commits 連續修補；對應使用者 Pi 端 demo 連續踩到的 9 條 issue）：(1) `5f30dc6` ALSA buffer drain 0.3s（「付款成功」尾巴被截 — mpg123 退出但 ALSA buffer 殘留被下個 mpg123 沖掉）；(2) `4672f1b` L5 移除冗餘 `mute_opencv(THANK_DELAY)`（會被緊隨的 subroutine_a `mute_opencv(OPENCV_MUTE)` 覆寫，純規格冗餘 — 248→247 tests）；(3) `b50b954` 4 條 TTS 文案口語化（移除括號內「終端輸入 1=X」雜訊，純語音模式不該唸這個）；(4) `a9c26ff` `sys.stdin.reconfigure(encoding='utf-8', errors='replace')` 防 Pi 端 stdin TextIOWrapper buffer 殘留 partial UTF-8 byte 害 input() raise（「刮」leading byte 0xe5 被當「期待 continuation byte」報誤）— 移除 2 個 UnicodeDecodeError test（247→245）；(5) `c0cb5b7` cart cap 4 條 speak f-string 改自然口語；(6) `1876cc6` 'c' 鍵 mute 期間嚴格行為（移到 else 內，print 文案對齊「擋下」字面）+ `sleep` callback 從 no-op 改 `time.sleep` 真等待（L5 thanks 後給顧客轉身的 3s 禮貌間隔）；(7) `f7dab09` mpg123 `stdin=subprocess.DEVNULL`（防 mpg123 偷讀父程序 stdin 攔截 user dialog input — Pi 實機踩到「L4 entry 期間打字 → mpg123 收到 q → 印「Stopped.」+ quit 中斷整段 dialog flow」）；(8) `48b9d03` L1 q-confirm 改 nested while 不重印 banner；(9) `f61a497` L4 客服 + final-confirm 繼續後 re-speak entry prompt（對齊 L2/L3 dialog 客服 re-speak fix a2eee27 pattern）。**Hook 配套**：`600a4cc` + `034846d` `auto-sync-pi.ps1` git pull 後加 SSH 清 Pi `__pycache__`（git pull 拉到 latest source 但 Python 仍 import cached .pyc 害 NLU 修補不生效；獨立 try/catch 避免 sync_pi.ps1 的 git stderr progress msg 被 PowerShell 當 ErrorRecord 拋出害清理被跳過）。Memory 同步：新增 `tts-prompt-as-ux-pacing` + `ux-over-technical-correctness` + `python-pycache-stale-on-pull` 三條。incremental-rebuild S2 + S4 階段現況：TTS pipeline 完整、L1-L5 dialog UX 細節已修補、hook 系統含 pycache cleanup；下一步使用者繼續修 S2 / 或開新範圍。 |
| 2026-05-27 | **🩹 S3 L3 action trigger fix（Pi demo 實測 bug，主 agent 直寫）**：使用者 Pi demo 觀察 5 個觸發點，發現 `[動作] L3` 沒印 — L2 加單成功後 dialog 不重新進入 `run_dialog`，直接在 `_dialog_dispatch_inner_l2` / `_dialog_main_loop` 內 `speak(L2_C_ADDED) + speak(L3_ENTRY_PROMPT)`，繞過 entry 觸發點。修補：兩處 cart empty→non-empty transition 前插 `do_action(ACTION_L3)`；`do_action` 參數 propagate 到 `_dialog_main_loop` / `_dialog_dispatch_inner_l2` / `_dialog_think_silence_l2` / `_dialog_c2_second_stage` 簽名。新增 3 個測試（main_loop transition / silence transition / cart 非空後加單 NOT trigger 驗證）。**Tests 252 → 255**。L3 內後續加單仍不重跑動作（符合「每層只 entry 一次」設計，servo 過熱風險避）。 |
| 2026-05-27 | **🤖 S3：同步動作 callback 接入（incremental-rebuild 第 3 步，commit `888ac76`，派 opus xhigh subagent + 6 招防護）**：新增 `myProgram/sales/constants/actions.py`（5 個 `ACTION_*` 動作組常數對應 `/home/pi/TonyPi/ActionGroups/*.d6a`：`L1_HAWK=wave_hand` / `L2=L2` / `L3=L3` / `L4_PAY=bow` / `L5_FAREWELL=wave_hand`，L2/L3 為使用者自訂 .d6a）；`main.py` 加 `do_action` callback（lazy `from myProgram.vendor import ActionGroupControl as Act` + `Act.runAction(name)` 同步阻塞至播完，對齊 speak callback 的 Windows pytest 兼容性 pattern）；5 個觸發點 wire-up：(1) L1 hawk entry（`speak(HAWK_SLOGANS[0])` 前；後續輪播 60s 不跑動作避 servo 過熱）/ (2) L2/L3 dialog entry（依 cart 空 / 非空分流）/ (3) L4 鏈路 A 兩處（主 dispatcher + 客服模式內掃碼 's' 路徑）/ (4) L5 entry（`speak(L5_THANKS)` 後 `clear_cart` 前）。`logic.py` 簽名加 `do_action` 並傳遞給 4 個 state callsite；`l1.py` / `l2_l3_dialog.py` / `l4.py` / `l5.py` 簽名加 `do_action`。**架構選項 C 維持**：sales/ 嚴格不 `from myProgram.vendor` import；動作名字串從 `myProgram.sales.constants.actions` 取。**S3 範圍嚴格切薄**：不呼叫 `Act.stopAction()`（sticky flag 留給 S5/S7）/ 不加 `cancel: threading.Event`（中斷是 S7）/ 不碰 Board 頭部舵機 / 不做場景組合動作（留 S5 worker）。**Tests 245 → 252**（fixture sweep 131 callsite 加 `do_action=lambda *a, **k: None`；+7 新測 covering 5 觸發點 + L1 hawk subsequent rounds NOT-called invariant）。subagent 自驗 `git branch --contains 888ac76` clean（worktree branch 非 main），Gotcha M 不踩。Pi 端待 demo 驗證 `L2.d6a` / `L3.d6a` 存在 + 全 flow 5 觸發點觸發 + vendor sticky flag 不污染（pineedtodo `2026-05-27_S3_action_verify.md`）。下一步：S5 非阻塞動作 worker 視 Pi demo 體感再評估開工時機。|
| 2026-05-27 | **🪝 Hook bug 雙層 fix（push S3 後使用者 Pi demo 動作沒出來 → 發現 Pi HEAD 仍是 028ac3f 沒 sync 到 16a90bd）**：**Layer 2（auto-sync-pi.ps1 內部）**：原本 `$ErrorActionPreference='Stop'` + `2>&1` 把 native command（ssh / git）的 stderr 包成 ErrorRecord 進 pipeline 觸發 terminating error → 跳到 catch 中斷 try block；除舊有的 `git pull` 進度訊息 `From https://github.com/...` 之外，2026-05-27 新踩 OpenSSH 量子安全警告 `** WARNING: connection is not using a post-quantum key exchange algorithm.`（Pi OpenSSH 不支援 post-quantum kex 時 client 端 unconditional 印）— 兩種 stderr 都會誤標 ERROR + 中斷 pycache 清理。修法：兩個 try block 內 inline `$ErrorActionPreference='Continue'` 跑 native command，改用 `$LASTEXITCODE` 判斷成功失敗（native 才有的可靠指標），`finally` 恢復原 EAP。**Layer 1（Claude Code background mode 行為）**：實證 **background job session 內 PostToolUse hook 完全不觸發**（這輪 session 的 push 整輪沒進 log，最後 entry 仍是上輪 live session 結束 push）—非 hook script 壞掉，是 Claude Code background mode 不發 event（未在官方文檔明確記載）。Hook 端無法修，**規則層補強**：`standard-workflow.md` 步驟 5 / `worktree-workflow.md` 階段 4 加「Background session 雙保險」段，主 agent push 後 explicit 跑 `& sync_pi.ps1`（live session 也跑無副作用，idempotent no-op 浪費 ~3s SSH latency）。判斷標準：system context 含「# Background Session」段 + `$CLAUDE_JOB_DIR` env var → background。Memory 同步：`hooks/NOTES.md` 6 段 B（已修）+ 加 N 段（background session skip）。dogfood：本輪 push 後主 agent 手動跑 sync_pi.ps1 + 清 pycache → Pi 同步到 16a90bd。 |
