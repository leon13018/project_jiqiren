# 後端模組結構（myProgram/sales/）

**敲定日期：** 2026-05-24
**對應實作階段：** S1 v2（5 層狀態機純單線程實作）

---

## 結構決議

```
myProgram/
├── myProgram.py                # 入口（thin，wire up + 啟動）
├── ActionGroupControl.py       # 廠商 SDK（禁改）
├── Board.py                    # 廠商 SDK（禁改）
└── sales/                      # 後端業務模組
    ├── __init__.py
    ├── logic.py                # 主迴圈 + 5 層 dispatch
    ├── constants/              # L0-L5 常數 subpackage（P8 拆分；8 子模組 + __init__.py re-export）
    ├── nlu.py                  # 意圖識別（純函式）
    ├── cart.py                 # 購物車資料模型
    └── states.py               # L1-L5 鏈路實作
```

---

## 每檔職責 + 為何這樣分

| 檔案 | 職責 | 為何抽出 |
|---|---|---|
| `logic.py` | 主迴圈、層間 dispatch、context 管理 | 對應原 `sales_logic.py` 核心；只管「現在哪一層 / 該轉到哪一層」 |
| `constants/` | L0-L5 常數 subpackage（2026-05-26 P8 拆分；原 274 行單檔）；`__init__.py` re-export 全部，對外 `from myProgram.sales.constants import XXX` 向前相容；8 子模組：`timing`（WAIT_NO_RESPONSE / DNC/DYC_TIMEOUT / …）/ `products`（PRODUCTS + QTY_PROMPT_TEMPLATE）/ `keywords`（CONFIRM_YES/NO + HAWK_SLOGANS）/ `l1_text` 到 `l5_text` | 多檔引用，抽出避免硬編碼擴散；單檔逼近 300 行後拆 subpackage 提升 maintainability；對應 L0_共通.md / L1-L5.md |
| `nlu.py` | `classify_intent(text) → IntentResult`；`parse_quantity` / `has_quantity` / `normalize_input` | 跨層共用的純函式，無副作用 → 最適合 BDD/TDD 切入點；商品實體解析 P7 已拆至 `product_parser.py` |
| `product_parser.py` | `parse_products(text) → list[(name, qty\|None)]` | 多商品實體解析（2026-05-26 P7 從 nlu.py 拆出）；從 nlu import keyword sets（`_KEYWORDS_ICED_TEA` / `_KEYWORDS_SCRATCH` / `_CHINESE_DIGIT_MAP`）以避免重複定義 |
| `cart.py` | `Cart` 類別 + add / remove / total 操作 | 純資料模型，未來上 DB / 上前端都會用，先抽出 |
| `states.py` | L1-L5 各鏈路（A / B-1 / B-2 / B-3 / C 等）| 5 層先合一檔，等長到 >300 行再拆 `states/` 子資料夾 |

---

## 為未來鋪好的路（但現在不蓋）

- `constants/` / `cart.py` / `nlu.py` 全部**純資料 + 純函式**
  → 不碰 `input()` / 不碰 `print()` / 不碰廠商 SDK
- `states.py` 的「對外動作」（語音、動作、UI 顯示）抽成 **callback 注入**
  → `run_state(ctx, *, speak, do_action, show)`
- 未來上 FastAPI 時，只要新增 `sales/api.py` 寫 REST endpoint → 呼叫 `logic.run_turn(input) → DTO`，**業務碼一行不動**
- 未來上資料庫時，只要新增 `sales/repository.py` 把 `cart.py` / 商品定義改成 repo pattern，**service layer 一行不動**

---

## 擴展觸發條件

| 觸發 | 升級成 |
|---|---|
| `states.py` >300 行 | 拆 `states/l1.py` / `l2.py` / `l3.py` / `l4.py` / `l5.py` |
| 要上 HTML 前端 | 加 `sales/api.py` + `sales/schemas.py`（Pydantic DTO） |
| 商品 >10 個 / 要存歷史訂單 | 加 `sales/repository.py` + SQLite |
| 要對前端推事件（動作完成、語音播完）| `sales/api.py` 加 WebSocket endpoint |

---

## 設計原則對應

| 原則 | 來源 | 應用 |
|---|---|---|
| 每步只加一層複雜度 | `.claude/rules/incremental-rebuild.md` | S1 v2 不上 web framework / DB，先把 5 層業務跑通 |
| 不過度設計 | karpathy-guidelines | 不預先建 `states/` 子資料夾、不預先寫 `api.py` 空殼 |
| 純函式 + callback 注入 | 大公司分層解耦慣例 | `nlu.py` / `cart.py` 純函式；`states.py` 對外動作以 callback 注入 |
| 廠商 SDK 不可改 | `CLAUDE.md` ⛔ 絕對禁止 #1 | `sales/` 內任何檔不修 `ActionGroupControl.py` / `Board.py`，只透過 callback 間接呼叫 |

---

## Testing 配置（BDD + TDD）

完整流程見 `.claude/rules/bdd-tdd-workflow.md`。本段只記模組結構面決策。

### 測試目錄結構

```
tests/                              # 專案根目錄
├── __init__.py
├── conftest.py                     # 共用 fixtures（callback stub 工廠等）
├── spec/                           # BDD 階段產出（按 L 層組織）
│   ├── L0_common_scenarios.py     # 含 Gherkin 注解 + 空 def test_xxx: pass
│   └── L?_*_scenarios.py
└── sales/                          # TDD 階段產出（按模組組織）
    ├── test_nlu.py
    ├── test_cart.py
    ├── test_logic.py
    └── test_states.py
```

### spec/ vs sales/ 對應關係

| 層級 | 組織方式 | 對應源 | 內容 |
|---|---|---|---|
| `tests/spec/` | 按 **L 層**（規格書檔案結構）| `resources/plans/業務程式邏輯規劃/L?.md` | BDD scenario 注解 + 空函數骨架，不 import prod code |
| `tests/sales/` | 按 **prod 模組**（實作檔結構）| `myProgram/sales/*.py` | 完整可執行測試，import prod code 驗證行為 |

spec/ 寫完不刪，當「規格書的可執行版」永久存活；後續修規格時 spec/ 跟著修。

### 選項 C：純 unit test，無整合測試

- `myProgram/sales/` 內任何檔**禁止 import 廠商 SDK**（`ActionGroupControl` / `Board`）
- 對外動作（speak / do_action / show）一律走 callback 注入，由 `myProgram.py` 入口層 wire up
- 結果：`sales/` 在 Windows 可完整 import、執行、測試，pytest 直接跑

### callback stub 範例（純函式 lambda，不用 mock）

```python
# tests/sales/test_states.py
def test_l3_b3_想一下_timeout_returns_to_l3():
    speak_calls = []
    ctx = make_ctx(speak=lambda t: speak_calls.append(t))

    states.run_l3_b3_想一下(ctx)

    assert speak_calls == ["請慢慢看"]
```

符合 `.claude/skills/test-driven-development/testing-anti-patterns.md`「mock 不是被測物件」原則。

### 測試指令

```bash
# 跑全部測試
python -m pytest tests/sales/ -v

# 跑單一檔
python -m pytest tests/sales/test_nlu.py -v

# 跑單一測試
python -m pytest tests/sales/test_nlu.py::test_classify_intent_recognizes_product -v
```

---

## 變動紀錄

| 日期 | 變動 |
|---|---|
| 2026-05-24 | 初版敲定；6 個空骨架檔（含 `__init__.py`）建立於 `myProgram/sales/`；舊 `sales_logic.py` 刪除 |
| 2026-05-24 | 加入 Testing 配置段：tests/ 目錄結構（spec/ + sales/）/ 對應關係表 / 選項 C 純 unit test 限制 / callback stub 範例 / 測試指令；完整 BDD+TDD 流程移到 `.claude/rules/bdd-tdd-workflow.md` |
| 2026-05-25 | **sales 自審後架構決策（下個 session 寫 logic.py / myProgram.py 時實踐）**：A2-c：`logic.py` 寫 state-machine dispatch 邏輯（持有 cart / think_count / loop_count / unclear_count + 5 層串接 cycle），但 callback wire-up（真實 terminal / TTS / OpenCV / 廠商 SDK）在 `myProgram.py` 入口層做。A3-d：callback 集合（目前 8+ 種 variant）先按現況跑 myProgram.py 驗證可行性，遇到痛點才 refactor 包 Context dataclass（B1/B7 return shape 統一也一起延後）。A4-a + A4-c：L4-A → L5 cart 清空靠規格保證（L4-A 不清、L5 進入時清）+ 入口層加 invariant check（每進新層前確認 cart 狀態符合預期）。**B 類 refactor 結果**：A1 docstring 修 / B2 L5 改用 read_customer_input / B3 常數命名統一（5 個 _ENTRY_PROMPT 對齊）/ B4 拆 `states.py` 1085 行為 `states/` package（6 子檔 + __init__.py re-export）/ B6 函式位置修正。B5 不修（dispatch_response 重複但分支獨立 evolve 安全）。B1+B7 推遲到 logic.py 寫好後再決定 return shape。107 tests PASS 不破。 |
| 2026-05-26 | **P7.S18：nlu.py 商品實體解析拆出 product_parser.py**：`parse_products` / `_parse_quantity_in_window` / `_PRODUCT_KEYWORD_TO_NAME` 從 `nlu.py` 移至新檔 `product_parser.py`；keyword sets（`_KEYWORDS_ICED_TEA` / `_KEYWORDS_SCRATCH` / `_CHINESE_DIGIT_MAP`）留 `nlu.py`（intent 第一公民），`product_parser` 從 nlu import；`l2_l3_dialog.py` callers 改 import 自 `product_parser`；tests 拆分出 `test_product_parser.py`（16 個）。184 tests PASS。 |
| 2026-05-26 | **P8：constants.py 拆 constants/ subpackage**：`sales/constants.py`（274 行）→ `sales/constants/`（`__init__.py` + 8 子模組）。`timing.py` / `products.py` / `keywords.py` / `l1_text.py`-`l5_text.py`。`__init__.py` 以 `from .submodule import *` re-export，對外 import path 向前相容；本文件結構決議表 + 職責表 + 未來預留段同步更新為 `constants/`。184 tests PASS。 |
