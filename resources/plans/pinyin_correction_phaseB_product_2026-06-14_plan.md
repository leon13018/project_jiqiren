# 拼音近音糾錯 Phase B（問商品環節）— plan（HOW / step-by-step TDD）

> Spec：[../specs/pinyin_correction_phaseB_product_2026-06-14_spec.md](../specs/pinyin_correction_phaseB_product_2026-06-14_spec.md)。
> 每 step 一原子動作，Red→Green→Refactor。指令 `python -m pytest tests/sales/`（全量）或單檔。
> 三大塊：**① 內嵌數量糾錯**（含 constants 移動）→ **② 引擎擴展** → **② 問商品掛載**。

---

## Part ① — parse_products 內嵌數量糾錯（`product_parser.py`）

整合測試用 `unittest.mock.patch` mock `product_parser.phonetic_match`（Windows 無 pypinyin；聲韻母演算法 Phase A 已驗）。

- **Step 1（constants 移動，純重構）**：
  - `constants/products.py`：新增 `QTY_NUMBER_WORDS = ("一","兩","三","四","五","六","七","八","九","十")` + 加入 `__all__`。
  - `states/_l2_l3_qty_followup.py`：改 `from ...constants import QTY_NUMBER_WORDS`（移除 local `_QTY_NUMBER_WORDS`），usage `[w + unit for w in QTY_NUMBER_WORDS]`。
  - `tests/sales/test_states.py`：round-trip 守則測試的 import 改 `from myProgram.sales.constants.products import QTY_NUMBER_WORDS`（原 import `_QTY_NUMBER_WORDS` from _l2_l3_qty_followup）。
  - 跑 `python -m pytest tests/sales/` → **全綠**（純移動，521 不變）。
- **Step 2（① Red）**：`test_product_parser.py` 新增：`patch` `product_parser.phonetic_match` 回 `"三瓶"`，`assert parse_products("紅茶商品") == [("冰紅茶", 3)]`。跑 → FAIL（現回 `[("冰紅茶", None)]`）。
- **Step 3（① Green）**：`product_parser.py`：
  - import `from myProgram.sales.phonetic import phonetic_match`、`from myProgram.sales.constants import PRODUCTS, QTY_NUMBER_WORDS`。
  - 視窗解析後加：`qty is None` 且 `window.strip()` 非空 → `corrected = phonetic_match(window.strip(), [w + PRODUCTS[product]["單位"] for w in QTY_NUMBER_WORDS])`；`corrected` 非 None → `qty = parse_quantity(corrected)`。
  跑 Step 2 → PASS。
- **Step 4（① 回歸 + 邊界）**：`test_product_parser.py` 加：mock 回 None → `parse_products("紅茶商品") == [("冰紅茶", None)]`（不變）；已含數量「紅茶 2」→ 不呼叫 phonetic（patch 設 side_effect 斷言不被呼叫，或驗結果 2）；空視窗「紅茶」→ 不誤糾。跑 → 綠。
- **Step 5（commit 1）**：`git add myProgram/sales/constants/products.py myProgram/sales/states/_l2_l3_qty_followup.py myProgram/sales/product_parser.py tests/sales/test_product_parser.py tests/sales/test_states.py` → `feat(nlu): parse_products 內嵌數量拼音糾錯（QTY_NUMBER_WORDS 下移共用）`。`git branch --contains <SHA>` 驗。跑全量 → 綠。

---

## Part ② 引擎 — `phonetic.py` 擴展

測試 fake（補 `test_phonetic.py`）：
```python
_FAKE_B = {"冰":("b","ing"),"紅":("h","ong"),"茶":("ch","a"),
           "刮":("g","ua"),"樂":("l","e"),"尬":("g","a"),"宏":("h","ong")}
def fakeB(ch): return _FAKE_B[ch]
def grpB(s): return {"冰紅茶":"T","紅茶":"T","刮刮樂":"L"}[s]
PROD = ["冰紅茶","紅茶","刮刮樂"]
```

- **Step 6（翻邊界 → Red）**：`test_phonetic_match_medial_not_equivalent` 改為斷言**介音現等價**（`(g,"ua")` 與 `(g,"a")` → `_syllable_equiv` True）。跑 → FAIL。
- **Step 7（介音 Green）**：`_FINAL_EQUIV` 增 `"ua":"a","uo":"o","ie":"e"`。跑 → PASS；補介音三類測試。
- **Step 8（疊字 Red→Green）**：test `phonetic_match("刮樂",["刮刮樂","紅茶"],to_pinyin=fakeB)=="刮刮樂"`、`phonetic_match("尬尬樂",["刮刮樂","紅茶"],fakeB)=="刮刮樂"`。impl `_dedup_chars`（collapse 連續重複字）+ 取音前對 text/候選 dedup、保 deduped→original、命中回 original。跑 → PASS。
- **Step 9（group_key Red→Green）**：簽名加 `group_key=None`（None=identity）；歧義閥 top-2 取「group 與 top-1 不同」最高分。test `phonetic_match("宏茶",PROD,fakeB,group_key=grpB)=="紅茶"`。跑 → PASS。
- **Step 10（子串 fallback Red→Green）**：test `phonetic_match("茶",PROD,fakeB,group_key=grpB) in {"冰紅茶","紅茶"}`；對照 `phonetic_match("茶",PROD,fakeB)`（無 group_key）`is None`。impl：similarity 無 winner → 找 deduped(text) 是 deduped(候選) 子串者 → group-aware 唯一 → 回該組最高 similarity，跨多 group/無 → None。跑 → PASS。
  > ⚠️ **Phase A None-測試交互風險（必讀）**：子串 fallback 只在「similarity 無 winner」時跑，Phase A 的 None 案（歧義/無夠近/長度不等）正是「無 winner」→ 若那些測試 fake 字恰好構成子串，子串規則會把 None 翻成命中、Phase A 測試 FAIL。逐一檢視翻掉者：(a) text 確是子串、回候選＝**正確新行為** → 調該測試預期；(b) fake 字**巧合**成子串、原意測 None → 改 fake 字使**不構成子串**保留原意。**禁無腦改 assert**。
- **Step 11（②引擎回歸 + commit 2）**：跑全量確認 Phase A 12 案 + round-trip + 問數量/① wiring（`group_key=None`、數量候選 inert）全綠。`git add myProgram/sales/phonetic.py tests/sales/test_phonetic.py` → `feat(phonetic): 擴拼音引擎（疊字去重 + 介音等價 + group_key + 子串規則）`。branch 驗。

---

## Part ② 掛載 — 問商品 unclear 出口（`states/l2_l3_dialog.py`）

整合測試掛 `test_states.py`，mock `l2_l3_dialog.phonetic_match`。

- **Step 12（Red）**：問商品 unclear 出口（顧客講既非意圖、parse_products 又空的 garble），`patch` `phonetic_match` 回 `"刮刮樂"` → 斷言 cart 加刮刮樂、`unclear_count` 未累加。跑 → FAIL。
- **Step 13（Refactor 行為不變）**：抽 `_handle_products(self, products, *, in_main_loop)`，搬 `_dispatch` 的 `if products:` block（435-474）；`_dispatch` 商品分支改呼叫。跑全量 → **仍全綠**。
- **Step 14（Green）**：`l2_l3_dialog.py` import `phonetic_match`；加 `_PRODUCT_PHONETIC_CANDIDATES=("冰紅茶","紅茶","刮刮樂")` + `_product_group(s)=parse_products(s)[0][0]`；unclear 出口前插 `phonetic_match(response,...,group_key=_product_group)` → `parse_products(corrected)` → `_handle_products`。跑 Step 12 → PASS。
- **Step 15（回歸 + 邊界）**：test_states.py 加：mock 回 None → unclear_count++/clarify 不變；拒絕/結帳 garble → 不被劫持（早 return）；corrected 商品名缺數量 → 走 _handle_products 進追問。跑全量 → 綠。
- **Step 16（commit 3 + Iron Law）**：`git add myProgram/sales/states/l2_l3_dialog.py tests/sales/test_states.py` → `feat(nlu): 問商品 unclear 出口掛載拼音糾錯`。跑 `python -m pytest tests/sales/` 看 `N passed`（0 failed）；branch 驗。

---

## 收尾（主 agent）

3 段審 → ff-merge → push → worktree 清理 → pineedtodo 記 Pi 實測 ①紅茶商品→×3 + ②刮樂/尬尬樂/茶 + 調閾值。
