# Project_01 架構願景 / Architecture Vision

> 2026-06-01 從 memory `project-architecture-vision` 遷出至 resources/architecture/（skill 遷移）。`[[memory-slug]]` 引用對應內容多已併入 `.claude/skills/project-01-workflow/` references 或本目錄其他檔。


**敲定日期：** 2026-05-24（S1 v2 業務邏輯實作前）

## 三層架構願景

- **前端**：HTML + CSS + TypeScript（複雜時可加 React）— 待規劃，包含商品顯示 / QR Code 掃碼 / 金額顯示 / 廣告影片背景循環
- **後端**：Python（規則匹配業務邏輯）— S1 v2 進行中
- **資料庫**：暫不需要（商品只兩個）；商品多再上 SQLite / Postgres

**Why:** 使用者想對齊真正軟體公司的分層架構規範，方便未來擴展與維護。

## 後端模組化方案（原敲定 — 2026-05-25 已多輪重構，現況見下方）

原始 5 檔方案：
```
myProgram/sales/
├── __init__.py
├── logic.py        # 主迴圈 + 5 層 dispatch（唯一允許持有外部世界的進入點）
├── constants.py    # L0 常數
├── nlu.py          # 意圖識別純函式
├── cart.py         # 購物車資料模型
└── states.py       # L1-L5 鏈路（對外動作 callback 注入）
```

**當前實際結構**（2026-05-26 P0-P8 review-driven refactor + 同日 UX 補強迴圈完成；197 tests PASS）：
```
myProgram/
├── __init__.py                # P6.S8 加：顯式 package
├── __main__.py                # P6.S8 加：支援 `python -m myProgram` 跑法
├── main.py                    # P6.S8: 原 myProgram.py 改名（消除 package/module 同名）
├── vendor/                    # P1: 廠商 SDK 隔離（hook 強制禁改內容）
│   ├── __init__.py
│   ├── ActionGroupControl.py
│   └── Board.py
└── sales/
    ├── __init__.py
    ├── logic.py               # 4 層 cycle dispatch（L1 → dialog → L4 → L5）
    ├── cart.py
    ├── nlu.py                 # P7 拆分後：classify_intent / parse_quantity / has_quantity / normalize_input
    ├── product_parser.py      # P7.S18 加：商品實體解析（parse_products + alias mapping）
    ├── constants/             # P8.S17 加：拆 subpackage（原 274 行單檔）
    │   ├── __init__.py        # re-export 全部；對外 `from ...constants import XXX` 向前相容
    │   ├── timing.py          # WAIT_NO_RESPONSE / DNC/DYC_TIMEOUT / OPENCV_MUTE / 計數 / timeout 等
    │   ├── products.py        # PRODUCTS dict + QTY_PROMPT_TEMPLATE / QTY_CLARIFY_TEMPLATE
    │   ├── keywords.py        # HAWK_SLOGANS + KEYWORDS_CONFIRM_YES/NO + STRICT_SHORT 短詞集
    │   ├── l1_text.py 到 l5_text.py  # 各層字串常數
    └── states/                # P6.S9 改層編號命名制
        ├── __init__.py        # re-export run_subroutine_a / run_l1 / run_dialog / run_l4 / run_l5
        ├── l0_subroutine_a.py # 原 subroutine_a.py
        ├── l1.py
        ├── l2_l3_dialog.py    # 原 dialog.py；P2 抽 _dialog_main_loop 共用 helper（消 113 行 copy-paste）
        ├── _l2_l3_qty_followup.py  # 原 _product_helpers.py
        ├── l4.py
        └── l5.py
```

純資料 / 純函式檔（`constants/` / `nlu.py` / `product_parser.py` / `cart.py`）不碰 `input()` / `print()` / 廠商 SDK。

**P0-P8 主要 commits**（review-driven，使用者實機驗證 + 多次 dispatch）：`691ef2e` P0 keyword strict-match / `0ab1cea` + `a7d434e` P1 dead code + vendor 隔離 / `f7ea37b` + `3616203` P2 L4 silent fix + dialog 抽 helper / `dcdff9a` + `f7fc7d4` + `6e7ff52` P3 checkout confirm UX / `52ecf84` P4 keyword 補強 / `07720ab` P5 normalize_input / `62d2ab5` + `12415e7` P6 命名一致化 / `7aff860` P7 NLU 拆 product_parser / `860879a` P8 constants 拆 subpackage。完整審查報告與 8 階段 Roadmap：`resources/reviews/2026-05-26_myProgram_multi-agent-review.md`。

**P8 後 UX 補強迴圈 commits**（2026-05-26 同日；使用者實機踩出問題即時修補）：`696ae6a` L1 主選單嚴格匹配（多字元亂打不再截首字元誤進模式）/ `354c037` L4 客服模式移除 print_terminal dup / `0016e23` L4「等待安撫」intent 方案 A（顧客「好/嗯/等等我」溫和回應）/ `0236879` L4 從 A 反轉為**方案 B wall-clock 60s 全程預算**（防 ack spam 拖延，見 [[l4-ack-wallclock-budget-design]]）/ `f970a81` L2/L3「想買無商品」intent（顧客「有/要/想買」肯定詞但無具體商品名 → 溫和引導 reask，不 ++unclear/think）。

## 測試結構（2026-05-24 加入，搭配 [[bdd-tdd-workflow]]）

```
tests/
├── __init__.py
├── conftest.py        # 共用 fixtures（callback stub 工廠等）
├── spec/              # BDD 階段：按 L 層組織（對應規格書 L0-L5）
│   └── L?_*_scenarios.py
└── sales/             # TDD 階段：按 prod 模組組織
    └── test_*.py
```

**選項 C（純 unit test）：** `myProgram/sales/` 嚴格不 import 廠商 SDK → 業務邏輯可完整在 Windows 跑 pytest。對外動作（speak / do_action / show）走 callback 注入，由 `myProgram.py` 入口層 wire up。完整流程：[[bdd-tdd-workflow]] memory + `.claude/rules/bdd-tdd-workflow.md`。

## 推薦接口框架（待決，HTML 開工時才選）

- 後端：**FastAPI + Pydantic**（自動 OpenAPI、type hints 自動 schema、內建 WebSocket）
- 前後端：REST + JSON（簡單事件）+ WebSocket（複雜事件流如動作完成、語音播完）
- 資料層：**Repository Pattern**（未來換 DB 不影響 service layer）
- 前端：HTML + TS，用 `openapi-typescript` 從後端文件自動產 TS 型別

## 標準化接口的核心（不論用哪個傳輸協定）

大公司一定做的三件事：
1. **DTO** — 跨層 / 跨語言傳的資料形狀先定死
2. **Schema / Contract** — Pydantic（Python）/ Zod（TS）/ JSON Schema 描述 DTO，前後端共用
3. **分層解耦** — Service Layer（業務邏輯）跟 Transport Layer（HTTP / WS）分開

## 接口框架延後決策（2026-05-24）

這輪只敲定後端目錄結構；FastAPI / Pydantic 等真正要做 HTML 前端時才選定。

**理由：**
1. 現在加 FastAPI 是空殼
2. Pi 上 FastAPI piwheels 兼容性還不確定（[[pi-glibc-piwheels-trap]]）
3. 優先級是 S1 v2 純單線程狀態機（L1 + dialog + L4 + L5），不被 web framework 打擾

## 擴展觸發條件

| 觸發 | 升級 |
|---|---|
| `states.py` >300 行 | 拆 `states/l1.py` ~ `l5.py` |
| 要上 HTML 前端 | 加 `sales/api.py` + `sales/schemas.py` |
| 商品 >10 個 / 要存歷史訂單 | 加 `sales/repository.py` + SQLite |
| 要對前端推事件 | `sales/api.py` 加 WebSocket endpoint |

## How to apply

- 寫 `myProgram/sales/` 內任何檔時：保持「純函式 / 純資料」原則（除了 `logic.py` 主迴圈與 `states.py` callback 注入）
- `nlu.py` / `cart.py` / `constants.py` 不碰 input / print / SDK
- 對外動作（語音 / 動作 / UI）一律 callback 注入，不直接 call
- 詳細細節 / 變動紀錄：`resources/architecture/backend-module-structure.md` + `frontend-backend-contract.md`

**相關：** [[pi-glibc-piwheels-trap]] / [[vendor-files]] / [[roadmap]]

---

## 2026-05-25 sales 自審後架構決策（下個 session 寫 logic.py / myProgram.py 必看）

L0-L5 全層 107 tests PASS 完成 + B 類 refactor 完成後，主 agent 自審產出 `resources/plans/sales_自審報告_2026-05-24.md`（A/B 兩類議題）。**A 類決策定案：**

（後續持續累加：2026-05-25 159 tests；2026-05-26 P0-P8 review-driven refactor 後 184 tests；同日 UX 補強迴圈後 197 tests）

### A2-c：logic.py 寫 state-machine dispatch，wire-up 在 myProgram.py
- `logic.py` 負責：持有 cart + 串接 cycle（**2026-05-25 更新：L1→dialog→L4→L5→子例程 A→L1，4 層 cycle**；原 L2→L3 transition 已內化到 dialog）+ 處理各 `run_?` 不一致 return shape
- `myProgram.py` 入口層負責：wire-up 真實 terminal / TTS / OpenCV / 廠商 SDK callback
- 這是「乾淨分層」— sales/ 內全 callback 注入，廠商 SDK import 隔離在 myProgram.py
- **Why 不選 A2-a（logic.py 全包）**：wire-up 部分必須在 myProgram.py 因 sales/ 嚴格不 import 廠商 SDK（選項 C）
- **Why 不選 A2-b（logic.py 仍空殼）**：架構文件原意 logic.py 持有「外部世界進入點」— A2-b 違反此設計

### A3-d：callback 集合先按現況 wire-up 驗證痛點再 refactor
- 目前 8+ 種 callback variant 分散在 6 個 `run_l?` 函式（不一致）
- 不預先 refactor 包 Context dataclass — 等 myProgram.py wire-up 跑通看實際痛點
- **B1+B7 推遲**（return shape 統一）— 跟 logic.py 怎麼接 tuple 強耦合，等實寫才決定

### A4-a + A4-c：cart 清空靠規格 + 入口層 invariant check
- L4-A 不清 cart、L5 進入時清（規格定）— L4-A → L5 必串接，信任規格保證
- 但 logic.py / myProgram.py wire-up 時加 invariant check：每進新層前確認 cart 狀態符合預期
  - 例：進 L5 前 assert cart 非空（從 L4-A 帶過來才有商品）；進 L1 子例程 A 前 assert cart 已空（L3-A / L4-B / L4-D 強制退 / L4-C 退出已清）
- defensive 但便宜

### B 類 refactor 結果（2026-05-25 完成）
- ✅ A1：states.py docstring 修（含 L0-L5 全層描述 + callback 集合 + return shape 不一致說明）
- ⚠️ B2：L5 `sleep` callback → `read_customer_input`（少一個 callback；L5 規格寫不接受顧客回應，當 sleep 用忽略結果）— **2026-05-25 已 revert**（commit `31f5dbb`）：chat-driven S1 wire-up 把 read_customer_input 實作為 blocking input() → L5 變「等使用者按 Enter」違反規格本意；改回獨立 sleep callback + S1 wire-up 用真 time.sleep。教訓：refactor 把多功能合一個 callback 前須先想 wire-up 端怎麼實作該 callback，不能假設「都是 timeout 就能共用」。
- ✅ B3：常數命名統一 — 5 個 `_ENTRY_PROMPT`（L1_HAWK / L1_STANDBY / L2 / L3 / L4_TEMPLATE）
- ✅ B4：拆 `states.py` 1085 行 → `states/` package（6 子檔 + `__init__.py` re-export，import path 不變）
- ✅ B6：`_schedule_hawk_l1` 從 L2 後 / L3 前的奇怪位置移到 L1 段尾（拆檔後屬於 l1.py）
- ⏸ B1 + B7：return shape 統一（dict / Transition dataclass / 4-tuple 等）推遲到 logic.py 寫好後一起決定
- ❌ B5：`_l2_dispatch_response` 與 `_l3_dispatch_response` 重複保留不抽 helper（分支獨立 evolve 安全，DRY 反 coupling）

### sales/ 結構快照（2026-05-25 B 方案重構後；2026-05-26 P0-P8 再演進）

**2026-05-25 完成時：**
```
myProgram/sales/
├── constants.py            # L0-L5 常數
├── nlu.py                  # classify_intent / parse_quantity / has_quantity / parse_products
├── cart.py
├── logic.py                # 4 層 cycle dispatch（L1 → dialog → L4 → L5）
└── states/
    ├── _product_helpers.py / subroutine_a.py / l1.py / dialog.py / l4.py / l5.py
```

**2026-05-26 P0-P8 後**（見上方「當前實際結構」段，含 vendor/ 隔離 / main.py 改名 / states 改層編號 / product_parser 拆出 / constants subpackage 等）。

**run_? return shape 速查**（B1+B7 仍未統一）：
- `run_subroutine_a` → None
- `run_l1` → str | None（"L2" / None — 字串保留沿用，語義 = "進 dialog"）
- `run_dialog` → `(next_state, next_think_count)`，next_state ∈ {"L4", "L1_via_subroutine_a"}
- `run_l4` / `run_l5` → `(next_state, next_loop_count, next_unclear_count)`

### 2026-05-25 B 方案重構（L2/L3 → dialog）

**動機：** state machine 該由「世界狀態（cart）驅動」，非「動作歷史驅動」。原 L2→L3 transition 是動作驅動，未來加刪除商品功能時 L3 內 cart 變空仍會問「還需要什麼東西嗎？」違和。

**結果：**
- L2.py / L3.py 刪除，合一為 `dialog.py`
- `run_dialog` 主迴圈每輪讀 `cart_module.is_empty(cart)` 決定模式：
  - cart 空 → L2 模式（詢問需求，timeout=A 拒絕）
  - cart 非空 → L3 模式（詢問加單 / 結帳，timeout=C-2 自動結帳，結帳前 confirm）
- 未來加刪除商品時 cart 變空，dialog 主迴圈自動切回 L2 prompt 模式，無需額外 transition

**規格書：** L2.md / L3.md 仍保留作為「dialog 在某 cart 狀態下行為的描述」；L0_共通.md 加「層狀態判定原則」段。
