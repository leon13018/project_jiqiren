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
    ├── constants.py            # L0 常數（時間 / 商品 / 白名單）
    ├── nlu.py                  # 意圖識別（純函式）
    ├── cart.py                 # 購物車資料模型
    └── states.py               # L1-L5 鏈路實作
```

---

## 每檔職責 + 為何這樣分

| 檔案 | 職責 | 為何抽出 |
|---|---|---|
| `logic.py` | 主迴圈、層間 dispatch、context 管理 | 對應原 `sales_logic.py` 核心；只管「現在哪一層 / 該轉到哪一層」 |
| `constants.py` | `WAIT_NO_RESPONSE` / `HAWK_INTERVAL` / `PRODUCTS` / 7 類關鍵字白名單 | 多檔引用，抽出避免硬編碼擴散；對應 L0_共通.md |
| `nlu.py` | `classify_intent(text) → IntentResult` | 跨層共用的純函式，無副作用 → 最適合 BDD/TDD 切入點 |
| `cart.py` | `Cart` 類別 + add / remove / total 操作 | 純資料模型，未來上 DB / 上前端都會用，先抽出 |
| `states.py` | L1-L5 各鏈路（A / B-1 / B-2 / B-3 / C 等）| 5 層先合一檔，等長到 >300 行再拆 `states/` 子資料夾 |

---

## 為未來鋪好的路（但現在不蓋）

- `constants.py` / `cart.py` / `nlu.py` 全部**純資料 + 純函式**
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
| 廠商 SDK 不可改 | `.claude/CLAUDE.md` ⛔ 絕對禁止 #1 | `sales/` 內任何檔不修 `ActionGroupControl.py` / `Board.py`，只透過 callback 間接呼叫 |

---

## 變動紀錄

| 日期 | 變動 |
|---|---|
| 2026-05-24 | 初版敲定；6 個空骨架檔（含 `__init__.py`）建立於 `myProgram/sales/`；舊 `sales_logic.py` 刪除 |
