# ②數量提前 + ③合音還原 — SDD spec

> Pi 實測（2026-06-14/15）痛點，根因已 systematic-debugging 實證。兩者皆統領設計規劃、先前 deferred，user 要求補。中改動 → 三段審不變。
> Plan：[../plans/qty_leading_and_fusion_2026-06-15_plan.md](../plans/qty_leading_and_fusion_2026-06-15_plan.md)。

## 1. 背景與根因（已實證）

| # | 現象 | 根因 |
|---|---|---|
| **②數量提前** | 「三瓶紅茶」/「一千瓶紅茶」→ `parse_products`=`[(冰紅茶,None)]` → 多問一次數量 | `parse_products` sticky-**right** 只看商品詞**後方**視窗；數量在商品**前**（極常見自然語序）落空 |
| **③合音還原** | 「醬就好」/「將就好」（=這樣就好=結帳）→ `classify_intent`=無法判斷 → unclear | 台灣合音「這樣→醬(jiàng)」+ ASR 同音變體「將」未還原；統領設計 §2.1 規劃 `expand_fusion` 但未實作（曾 hardcode 後 revert，待此層） |

## 2. 設計核心

### 2.1 ② 數量提前（`product_parser.py`）

- **抽 helper**（DRY，從現 ① inline 抽出）：
  ```python
  def _resolve_window_qty(window, unit):
      """視窗數量解析；解不出且有實質內容 → 拼音近音糾錯（① 右視窗 / ② 前導段共用）。"""
      qty = parse_quantity(window, default=None)
      if qty is None and window.strip():
          corrected = phonetic_match(window.strip(), [w + unit for w in QTY_NUMBER_WORDS])
          if corrected is not None:
              qty = parse_quantity(corrected)
      return qty
  ```
  右視窗 loop（現 122-134）改呼叫 `_resolve_window_qty(window, PRODUCTS[product]["單位"])`（① 行為不變）。
- **新增前導段**（dedup pass 前）：**第一個商品**右視窗無數量時，解析其前導段 `text[:found[0][0]]`（商品名前）：
  ```python
  if raw and raw[0][1] is None:
      leading = text[:found[0][0]]
      if leading.strip():
          lead_qty = _resolve_window_qty(leading, PRODUCTS[raw[0][0]]["單位"])
          if lead_qty is not None:
              raw[0] = (raw[0][0], lead_qty)
  ```
- **範圍限制**：只「前導段 → 第一商品」（非首商品的左段＝前一商品右視窗，sticky-right 已處理，不重綁）；混合語序「三瓶紅茶兩張刮刮樂」（首商品有右數量則前導被忽略）out of scope。

### 2.2 ③ 合音還原（`nlu.py` + `states/l2_l3_dialog.py`）

- **`nlu.expand_fusion(text) -> str`**：固定合音表 `_FUSION_TABLE = {"醬": "這樣", "將": "這樣"}`（台灣合音「這樣→醬 jiàng」+ ASR 同音變體「將」），逐字替換；無命中原樣返回。
- **掛載 `_dispatch` unclear 出口**（`l2_l3_dialog.py:455`，`if products: return` 之後、② phonetic 之前，design §3 ①）：
  ```python
  expanded = expand_fusion(response)
  if expanded != response:
      return self._dispatch(expanded, in_main_loop=in_main_loop)
  ```
  展開後 **重 dispatch 重 classify**（「將就好」→「這樣就好」→ classify=結帳 → 走結帳 confirm）。
- **遞迴安全**：`expand_fusion` idempotent（「這樣…」無 醬/將 → 不再變）；`if expanded != response` guard → 重 dispatch 的 expand 無變 → 不再遞迴，max depth 1。
- **FP 低**：`expand_fusion` 只在 classify 已回**無法判斷**的 unclear 出口跑（正常含「將要」之輸入早被 classify/parse 攔、不到此），故「將→這樣」風險受 gating 壓低。

## 3. 改檔範圍

| # | 檔 | 類型 | 估計 |
|---|---|---|---|
| 1 | `myProgram/sales/product_parser.py` | 改 | ~+12/−6（抽 `_resolve_window_qty` + 前導段） |
| 2 | `myProgram/sales/nlu.py` | 改 | ~+8（`_FUSION_TABLE` + `expand_fusion`） |
| 3 | `myProgram/sales/states/l2_l3_dialog.py` | 改 | ~+5（import + unclear 出口 expand 重 dispatch） |
| 4 | `tests/sales/test_product_parser.py` | 改 | ② 前導段案例 |
| 5 | `tests/sales/test_nlu.py` | 改 | `expand_fusion` 單元 |
| 6 | `tests/sales/test_states.py` | 改 | ③ 整合（「將就好」/「醬就好」→ 結帳 confirm） |

## 4. Out of scope

- **混合語序** between-product 數量（「三瓶紅茶兩張刮刮樂」首商品有右數量 → 前導被忽略）。
- **插字 garble**（「三鮮瓶」→三瓶，插入字元）→ 需編輯距離式 phonetic，另議。
- 合音表大擴（甭→不用、表→不要…）：初版只 醬/將→這樣（design YAGNI）。
- ①右視窗 / 既有 sticky-right 正常路徑 / confirm / 錢包 不碰。

## 5. 規範與參考

- 派 **sales-coder（opus）**；TDD（先寫重現的 failing test 再修）。三段審不變（spec-reviewer + code-quality-reviewer）。
- **reuse**：② 抽 `_resolve_window_qty` 收斂 ①；③ reuse `classify_intent`/`_dispatch` 重入；`QTY_NUMBER_WORDS`/`phonetic_match`/`PRODUCTS`。
- 統領設計 §2.1（expand_fusion）/ §3（掛載）為權威。曾 hardcode「醬就好」後 revert（git `7ccee39`），本層為其正解。

## 6. 測試指令 + 預期

`python -m pytest tests/sales/`；現 **564 passed** + 新增全綠、0 failed。

重點案例：
- **② parse_products**：三瓶紅茶→`[(冰紅茶,3)]`、一千瓶紅茶→`[(冰紅茶,1000)]`、紅茶三瓶→`[(冰紅茶,3)]`（不變）、紅茶刮刮樂→both None（不變）、刮刮樂兩張→`[(刮刮樂,2)]`（不變）。
- **③ expand_fusion 單元**：醬就好→這樣就好、將就好→這樣就好、這樣就好→這樣就好（不變）、紅茶→紅茶（不變）。
- **③ 整合**（test_states）：L3「將就好」/「醬就好」→ 重 dispatch → classify 結帳 → C-1 confirm（非 unclear）；L2「醬就好」→ 結帳語境 policy。
- **回歸**：①右視窗（紅茶商品→×3 mock）、問商品 phonetic wiring、千/萬/arabic 大數、round-trip 守則、564 全綠。

## 7. Commit 規範

- worktree：`worktree-qty-fusion`。
- 2 commit：① `feat(nlu): parse_products 支援數量提前（三瓶紅茶）+ 抽 _resolve_window_qty`；② `feat(nlu): expand_fusion 合音還原（醬/將就好→這樣就好）`。
- `git add` 明列檔名；message 繁中描述 + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
[approval] → worktree-qty-fusion → commit spec/plan
  → 派 sales-coder（TDD：② 前導段 → ③ expand_fusion）
  → 三段審 → Iron Law → ff-merge → push → 清理
  → pineedtodo：Pi 複測 三瓶紅茶→×3、將就好/醬就好→結帳
```
