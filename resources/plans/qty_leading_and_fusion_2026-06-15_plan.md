# ②數量提前 + ③合音還原 — plan（HOW / step-by-step TDD）

> Spec：[../specs/qty_leading_and_fusion_2026-06-15_spec.md](../specs/qty_leading_and_fusion_2026-06-15_spec.md)。
> 每 step Red→Green→Refactor；指令 `python -m pytest tests/sales/`。

---

## Part ② 數量提前（`product_parser.py`）

- **Step 1（RED）**：`test_product_parser.py` 加 `assert parse_products("三瓶紅茶") == [("冰紅茶", 3)]`。跑 → FAIL（現 `[("冰紅茶", None)]`）。
- **Step 2（Refactor，行為不變）**：抽 `_resolve_window_qty(window, unit)`（搬現 ① inline：`parse_quantity` + `qty is None and window.strip()` 時 `phonetic_match` fallback）；右視窗 loop 改 `qty = _resolve_window_qty(window, PRODUCTS[product]["單位"])`。跑全量 → **仍全綠**（① 行為不變、純重構）。
- **Step 3（GREEN ②）**：dedup pass 前加前導段：
  ```python
  if raw and raw[0][1] is None:
      leading = text[:found[0][0]]
      if leading.strip():
          lead_qty = _resolve_window_qty(leading, PRODUCTS[raw[0][0]]["單位"])
          if lead_qty is not None:
              raw[0] = (raw[0][0], lead_qty)
  ```
  跑 Step 1 → PASS。
- **Step 4（補案 + 回歸）**：一千瓶紅茶→`[("冰紅茶",1000)]`；**回歸不變**：紅茶三瓶→`[("冰紅茶",3)]`、紅茶刮刮樂→`[("冰紅茶",None),("刮刮樂",None)]`、刮刮樂兩張→`[("刮刮樂",2)]`、紅茶2刮刮樂→既有 dedup 規則。跑全量 → 綠。
- **Step 5（commit 1）**：`git add myProgram/sales/product_parser.py tests/sales/test_product_parser.py` → `feat(nlu): parse_products 支援數量提前（三瓶紅茶）+ 抽 _resolve_window_qty`。`git -C "<worktree>" branch --contains <SHA>` 驗。

---

## Part ③ 合音還原（`nlu.py` + `states/l2_l3_dialog.py`）

- **Step 6（RED 單元）**：`test_nlu.py` 加 `assert expand_fusion("將就好") == "這樣就好"`。跑 → FAIL（無函式）。
- **Step 7（GREEN 單元）**：`nlu.py` 加 `_FUSION_TABLE = {"醬": "這樣", "將": "這樣"}` + `def expand_fusion(text): ...`（逐字替換；無命中原樣）。補案：醬就好→這樣就好、將就好→這樣就好、這樣就好→這樣就好（不變）、紅茶→紅茶（不變）、空字串→空。跑 → 綠。
- **Step 8（RED 整合）**：`test_states.py` 加：L3 主迴圈顧客講「將就好」（products 已加、context 問還要不要）→ 斷言走**結帳 C-1 confirm**（如 speak 含結帳 confirm 文案）、**非** unclear clarify。跑 → FAIL（現 unclear）。
- **Step 9（GREEN 整合）**：`l2_l3_dialog.py` `_dispatch` import `expand_fusion`；在 `if products: return self._handle_products(...)`（現 454）**之後**、② phonetic 區塊（現 456）**之前** 插：
  ```python
  expanded = expand_fusion(response)
  if expanded != response:
      return self._dispatch(expanded, in_main_loop=in_main_loop)
  ```
  跑 Step 8 → PASS。
- **Step 10（回歸 + 邊界）**：`test_states.py` 加：「醬就好」L3→結帳 confirm；L2「醬就好」→ 結帳語境 policy（B-1 unclear，因 L2 結帳意圖當 unclear，行為合理即可）；gibberish（無醬/將、無商品）→ unclear 不變（expand 無變、不重 dispatch）；正常意圖（紅茶/不要/客服）不受影響（早 return、不到 expand）。跑全量 → 綠。
- **Step 11（commit 2 + Iron Law）**：`git add myProgram/sales/nlu.py myProgram/sales/states/l2_l3_dialog.py tests/sales/test_nlu.py tests/sales/test_states.py` → `feat(nlu): expand_fusion 合音還原（醬/將就好→這樣就好）`。跑 `python -m pytest tests/sales/` 看 `N passed`（0 failed）；branch 驗。

---

## 收尾（主 agent）
三段審（spec-reviewer → code-quality-reviewer）→ ff-merge → push → 清理 → pineedtodo 記 Pi 複測：三瓶紅茶→×3、將就好/醬就好→結帳 confirm。
