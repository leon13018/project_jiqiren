# 拼音近音糾錯 Phase B（問商品環節）— SDD spec

> 統領設計：[pinyin_correction_2026-06-13_design.md](pinyin_correction_2026-06-13_design.md)。本 spec 完成 design §5 Phase B 的**問商品環節糾錯**（不含合音還原）。
> Plan：[../plans/pinyin_correction_phaseB_product_2026-06-14_plan.md](../plans/pinyin_correction_phaseB_product_2026-06-14_plan.md)。
> **範圍（2026-06-14 user）= 問商品環節兩個掛載點都做**：
> - **① 一句內嵌數量糾錯**：顧客一句「紅茶商品」(=紅茶三瓶)，商品認得、但內嵌數量「商品」(=三瓶) 被聽歪 → 在 `parse_products` 解數量視窗時糾正 → 直接 紅茶 ×3，**不再多問一次**。（Pi demo 實證缺口）
> - **② 商品名糾錯**：商品名整個被聽歪（刮樂/尬尬樂→刮刮樂、茶→紅茶）→ 整句認不出 → 在問商品 NLU 放棄出口糾正。需引擎擴展。
> **前提**：Phase A（問數量 sub-loop 糾錯）已 Pi 實機驗證；pypinyin 已裝（`d5df8a1`）。

## 1. 背景與動機

Phase A 只在**單獨追問數量**的 sub-loop 注入糾錯。Pi 實測（2026-06-14）顯示問商品環節仍有兩個漏洞：

| # | 痛點（ASR 誤聽，Pi 實證 / design §1） | 現況 |
|---|---|---|
| ① | 「紅茶**商品**」(紅茶三瓶)：商品認得、內嵌數量「商品」(三瓶) 沒糾 | parse_products 回 (冰紅茶, None) → **多問一次數量** |
| ② | 「刮樂」「尬尬樂」(刮刮樂)、「茶」(紅茶)：商品名整個聽歪 | classify_intent 無法判斷 + parse_products 空 → **unclear reprompt** |

①重用 Phase A 引擎（聲韻母足矣）；②需補引擎能力（疊字去重 / 介音等價 / 子串規則）。

## 2. 設計核心 + 行為規約

### 2.0 共用：`QTY_NUMBER_WORDS` 下移 constants

Phase A 的 `_QTY_NUMBER_WORDS`（`states/_l2_l3_qty_followup.py`）現由 `parse_products`（①）與 qty sub-loop 共用 → **移至 `constants/products.py` 為 `QTY_NUMBER_WORDS`**（公開、加入 `__all__`）。`_l2_l3_qty_followup.py` 改 import；避免兩處平行維護（對齊既有「keyword 共享常數」慣例）。

### 2.1 ① `parse_products` 內嵌數量糾錯（`product_parser.py`）

現 per-product 數量視窗解析：
```python
window = text[end:window_end]
qty = parse_quantity(window, default=None)
```
**改為**：`parse_quantity` 解不出（None）且視窗有實質內容時，對視窗做拼音糾錯：
```python
qty = parse_quantity(window, default=None)
if qty is None:
    unit = PRODUCTS[product]["單位"]
    corrected = phonetic_match(window.strip(), [w + unit for w in QTY_NUMBER_WORDS])
    if corrected is not None:
        qty = parse_quantity(corrected)
```
- 重用既有 `phonetic_match`（聲韻母模糊；商品→三瓶 不需疊字/介音）。
- `phonetic_match` graceful（Windows 無 pypinyin → None）→ ① no-op → `parse_products` 行為同今天（既有測試零衝擊）。
- 候選依該 product 的單位（瓶/張）。多字 / 雜訊視窗 → 長度不符 → None → 落回 (product, None) 走既有追問。

**行為規約**：① 只在「商品認得、視窗數量解不出」時補救；不改變已解出數量的路徑；失敗回 None＝現狀（追問），不劣化。

### 2.2 ② `phonetic.py` 引擎擴展（全 always-on；問數量 / ① 的數量候選 inert）

**a) 疊字去重**：比對前對 text 與每候選做「連續重複字 collapse」（`刮刮樂→刮樂`）；保 `deduped→original` 映射，**命中回 original**。idempotent。
**b) 介音等價**：`_FINAL_EQUIV` 增 `ua→a`、`uo→o`、`ie→e`（解 `尬(ga)≡刮(gua)`）。數量候選韻母無一含 ua/uo/ie → inert。
**c) `group_key` 參數**：`phonetic_match(text, candidates, *, to_pinyin=None, group_key=None)`。歧義閥 top-2 只取「`group_key` 與 top-1 不同 group」最高分（同商品多 surface 不互壓）。`None`＝identity → 問數量 / ① 行為不變。
**d) 不同字數子串 fallback**（group-aware）：similarity 無 winner 時，找 `deduped(text)` 是 `deduped(候選)` 子串者；同一 group → 回該組 similarity 最高候選；跨多 group / 無 → None。解 `茶 ⊂ 紅茶/冰紅茶`（皆冰紅茶組）。

**執行序**：守衛 → 取音（`try/except ImportError→None`）→ 疊字去重 → similarity（聲韻母 + 介音 + 鼻音 + 平翹舌）→ group-aware 歧義閥 → 命中回 original；否則子串 fallback；否則 None。

### 2.3 ② 問商品掛載（`states/l2_l3_dialog.py`）

- 抽 `_handle_products(self, products, *, in_main_loop) -> tuple | None`：把 `_dispatch` 內 products block（`l2_l3_dialog.py:435-474`：`resolve_and_add_products` + control 分流 + transition / reask）原封搬出，正常路徑與糾錯路徑共用。`_dispatch` 商品分支改呼叫之（純重構）。
- **unclear 出口插糾錯**（`l2_l3_dialog.py:476`「都沒命中 → B-1 兜底」**之前**）：
  ```python
  corrected = phonetic_match(response, _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group)
  if corrected is not None:
      products = parse_products(corrected)
      if products:
          return self._handle_products(products, in_main_loop=in_main_loop)
  # 否則落回既有 B-1 unclear
  ```
- `_PRODUCT_PHONETIC_CANDIDATES = ("冰紅茶", "紅茶", "刮刮樂")`；`_product_group(s) = parse_products(s)[0][0]`。

**行為規約**：② 只在問商品 NLU 放棄出口觸發（拒絕/想一下/結帳/客服/想買無商品/正常解析皆已先 return，不被劫持）；修正後走與正常輸入相同的 `_handle_products`（**含 ①：corrected 商品名重 parse_products 時，內嵌數量也一併糾**）；失敗 None → 落回 unclear，不劣化。

## 3. 改檔範圍

| # | 檔 | 類型 | 估計 |
|---|---|---|---|
| 1 | `myProgram/sales/constants/products.py` | 改 | +2（`QTY_NUMBER_WORDS` 常數 + `__all__`） |
| 2 | `myProgram/sales/states/_l2_l3_qty_followup.py` | 改 | ~±3（改 import 共用常數，刪 local def） |
| 3 | `myProgram/sales/product_parser.py` | 改 | ~+8（① 視窗糾錯 + import phonetic_match/PRODUCTS/QTY_NUMBER_WORDS） |
| 4 | `tests/sales/test_product_parser.py` | 改 | ① 整合測試（mock phonetic_match：紅茶商品→×3 / None→不變） |
| 5 | `myProgram/sales/phonetic.py` | 改 | ~+45（②引擎：疊字 + 介音 + group_key + 子串） |
| 6 | `tests/sales/test_phonetic.py` | 改 | **翻**介音邊界測試 + 新增疊字/介音/group_key/子串案例 |
| 7 | `myProgram/sales/states/l2_l3_dialog.py` | 改 | ~+30/−40（抽 `_handle_products` + 常數 + group helper + unclear 插糾錯） |
| 8 | `tests/sales/test_states.py` | 改 | ② wiring 整合測試（corrected→加單 / None→unclear 不變 / 不劫持）+ 更新 round-trip 守則 import（QTY_NUMBER_WORDS 改 constants） |

## 4. Out of scope

- **合音還原**（醬就好→這樣就好）→ 後續。
- **數量在商品前**（「三瓶紅茶」sticky-right 視窗在商品後 → ① 抓不到）→ 不在本 spec（要動 parse 視窗邏輯，另議）。
- 問數量 sub-loop（Phase A）行為：`group_key=None`、引擎擴展對數量候選 inert → 零改動。
- 既有正常解析 / confirm / 錢包 context 不碰。
- 閾值最終值（Pi 調）；商品候選擴充（即時樂/樂透/彩券）初版不收。

## 5. 規範與參考

- 派 **sales-coder（opus）**；karpathy + TDD frontmatter 自動預載。
- **既有 reuse**：`phonetic_match`（①重用、②擴展不重寫）、`parse_quantity`、`parse_products` 框架、`resolve_and_add_products`、`_dispatch` products block（搬 `_handle_products`）、`PRODUCTS[p]["單位"]`。
- 統領設計 §2.2 / §3 權威；`group_key`（同商品多 surface）為實作衍生補足。

## 6. 測試指令 + 預期結果

指令：`python -m pytest tests/sales/`
預期：現 **521 passed** + 新增/翻轉案例全綠，0 failed。

重點案例：
- **①（test_product_parser，mock phonetic_match）**：`parse_products("紅茶商品")` 在 phonetic_match 回「三瓶」時 → `[("冰紅茶", 3)]`；mock 回 None → `[("冰紅茶", None)]`（不變）；已解出數量者（「紅茶 2」）不觸發糾錯。
- **②引擎（test_phonetic，注入 fake to_pinyin）**：疊字（刮樂→刮刮樂）、疊字+介音（尬尬樂→刮刮樂）、介音三類、group_key 同商品不互壓、子串（茶→tea surface）、**翻** `medial_not_equivalent`。
- **②wiring（test_states，mock phonetic_match）**：問商品 unclear 顧客 garble → 回「刮刮樂」→ 加單；回 None → unclear 不變；拒絕/結帳 garble → 不被劫持。
- **回歸**：Phase A 12 案 + round-trip 守則 + 問數量 wiring + 既有 product_parser 測試全綠（① / 引擎擴展 graceful/inert）。

## 7. Commit 規範

- worktree：`worktree-pinyin-phase-b`。
- 建議拆 3 commit：
  1. `refactor(constants): QTY_NUMBER_WORDS 下移共用` + `feat(nlu): parse_products 內嵌數量拼音糾錯`（①，含 constants 移動 + product_parser + 測試）。
  2. `feat(phonetic): 擴拼音引擎（疊字去重 + 介音等價 + group_key + 子串規則）`（②引擎）。
  3. `feat(nlu): 問商品 unclear 出口掛載拼音糾錯`（②wiring）。
- `git add` 明列檔名（禁 `-A`）；message 英文 type 前綴 + 繁中描述 + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
[approval] → worktree-pinyin-phase-b → commit spec/plan
  → 派 sales-coder（TDD：① 內嵌數量 → ② 引擎擴展 → ② 問商品掛載）
  → 3 段審 → Iron Law → ff-merge → push（Stop hook sync Pi）→ 清理
  → pineedtodo：Pi 實測 紅茶商品→×3（①）+ 刮樂/尬尬樂/茶（②）+ 調閾值
```
