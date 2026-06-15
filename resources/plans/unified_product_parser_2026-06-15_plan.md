# 統一商品/數量 parser 重寫 — plan（HOW / step-by-step TDD）

> **For agentic workers:** 由 sales-coder 執行；步驟 Red→Green→Refactor。
> Spec：[../specs/unified_product_parser_2026-06-15_spec.md](../specs/unified_product_parser_2026-06-15_spec.md)。
> **重寫高風險**：現 575 測試是回歸網，**每步後跑 `python -m pytest tests/sales/` 保綠**。

測試注入 fake（test_phonetic）：
```python
_FK={'食':('sh','i'),'品':('p','in'),'商':('sh','ang'),'三':('s','an'),'四':('s','i'),'十':('sh','i'),
     '一':('','i'),'兩':('l','iang'),'五':('','u'),'六':('l','iu'),'七':('q','i'),'八':('b','a'),'九':('j','iu'),'瓶':('p','ing')}
fk=lambda c:_FK[c]; QP=[w+'瓶' for w in '一兩三四五六七八九十']
```

---

## Part 0 — phonetic 完全同音 tie-break（`phonetic.py`）

- **Step 0.1（RED）**：test_phonetic 加 `assert phonetic_match("食品", QP, to_pinyin=fk) == "十瓶"`。跑 → FAIL（現 None：食品 對 四瓶/十瓶 sim 皆 1.0、margin 0）。
- **Step 0.2（GREEN）**：`phonetic.py`：
  - 算 `exact_count`（逐位 `text_syl[i] == cand_syl[i]` **未 canon** 即相等的數）。
  - 歧義閥改：`ranked = sorted(idx, key=lambda i:(sim[i], exact[i]), reverse=True)`；`top1=ranked[0]`；`sim[top1]<THRESHOLD→None`；單候選→回；`top2=ranked[1]`；`sim[top1]-sim[top2]>=MARGIN→回 top1`；`elif sim[top1]==sim[top2] and exact[top1]>exact[top2]→回 top1`；`else None`。
  跑 → PASS。
- **Step 0.3（補案+回歸）**：`phonetic_match("商品",QP,fk)=="三瓶"`（不變）；構造真雙重平手（如兩候選對 text 都 sim=1.0、exact 同）→ None；既有 test_phonetic 全綠（含 group_key/子串/疊字/介音案——確認 exact tie-break 不破壞）。
- **Step 0.4（commit 0）**：`git add myProgram/sales/phonetic.py tests/sales/test_phonetic.py` → `feat(phonetic): 歧義閥完全同音 tie-break（解 食品→十瓶）`。`git -C "<wt>" branch --contains <SHA>` 驗。全量綠。

---

## Part 1 — `nlu.find_quantity_spans`（`nlu.py`）

- **Step 1.1（RED）**：test_nlu 加 `assert find_quantity_spans("紅茶三瓶") == [(2, 4, 3)]`（紅茶 0-2、三瓶 2-4 值 3）。跑 → FAIL（無函式）。
- **Step 1.2（GREEN）**：`nlu.py` 加：
  ```python
  _QTY_SPAN_RE = re.compile(r"[0-9" + "".join(CHINESE_DIGIT_MAP) + _CHINESE_MULTIPLIER_CHARS + "瓶張]+")
  def find_quantity_spans(text):
      out = []
      for m in _QTY_SPAN_RE.finditer(text):
          v = parse_quantity(m.group(), default=None)
          if v is not None:
              out.append((m.start(), m.end(), v))
      return out
  ```
  跑 → PASS。
- **Step 1.3（補案）**：「五張刮刮樂三瓶」→ [(0,2,5),(7,9,3)]（刮刮樂 2-5 不在數量集）；「9萬瓶」→ [(0,3,90000)]；「紅茶」→ []；「瓶」（無數字）→ []（值 None 棄）。跑綠。
- **Step 1.4（commit 1）**：`git add myProgram/sales/nlu.py tests/sales/test_nlu.py` → `feat(nlu): find_quantity_spans helper`。branch 驗。全量綠。

---

## Part 2 — `parse_products` 重寫為統一 token-parser（`product_parser.py`）

- **Step 2.1（RED comprehensive）**：test_product_parser 加 `assert parse_products("刮刮樂五張紅茶三瓶") == [("刮刮樂",5),("冰紅茶",3)]`（此案現已對，當基準）+ `assert parse_products("五張刮刮樂三瓶紅茶") == [("刮刮樂",5),("冰紅茶",3)]`（現錯亂 → FAIL）。跑 → FAIL。
- **Step 2.2（GREEN 重寫）**：`parse_products` 重寫（spec §2.1 八步）：
  1. 精確商品 span（沿用 `_PRODUCT_KEYWORDS_PRE` + occupied 重疊去重，回 `[(s,e,product,'exact')]`）。
  2. `qty_spans = find_quantity_spans(text)`（已扣商品？不需——數量集與商品字不重疊）。
  3. 剩餘 gap（扣商品 span + qty span 的區間）→ 逐 gap `phonetic_match(gap.strip(), _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group)` → 命中加 `(s,e,corrected,'garbled')`；未命中 gap 收進 `unused_gaps`。
  4. `tokens = sorted(商品spans + [(s,e,'QTY',v)], key=start)`。
  5. 綁定：`prods=[(pos,product,qty=None)...]`；對每個 qty（位置序）→ 找「start < qty.start 且 qty 為 None 的最近商品」綁；無則「start > qty.start 最近未綁商品」。
  6. 未綁商品 → 緊鄰 unused_gap（先右後左）`phonetic_match(gap, [w+unit...])` → 綁。
  7. raw = 商品依位置序 (product, qty)。
  8. dedup pass：**原樣複製現有規則 1/2/3 code**（不改邏輯）。
  
  > ⚠️ import：`from myProgram.sales.nlu import parse_quantity, find_quantity_spans`、`phonetic_match`、`_PRODUCT_PHONETIC_CANDIDATES`/`_product_group`（從 l2_l3_dialog？→ 為避免循環 import，把 `_PRODUCT_PHONETIC_CANDIDATES` 與 `_product_group` **移到 product_parser 或 constants**，l2_l3_dialog 改 import；確認無循環）。
  跑 Step 2.1 → PASS。
- **Step 2.3（全量回歸，關鍵）**：跑 `python -m pytest tests/sales/` → 既有 575 全綠。逐一修任何翻動：sticky-right（紅茶三瓶）、dedup 規則 1/2/3（刮刮樂刮刮樂 / 刮刮樂3刮刮樂 / 紅茶2紅茶3）、① 紅茶商品、② 三瓶紅茶、Phase B wiring。**任何翻動先分清是 (a) 新 parser 正確新行為 → 調該測試預期，還是 (b) 真 regression → 修 parser**。禁無腦改 assert。
- **Step 2.4（補 comprehensive 案）**：三瓶紅茶兩張刮刮樂→[(冰紅茶,3),(刮刮樂,2)]；五張刮樂三瓶紅茶（mock `product_parser.phonetic_match` 品名段回刮刮樂）→[(刮刮樂,5),(冰紅茶,3)]；五張刮樂→[(刮刮樂,5)]；紅茶食品（mock/注入）→[(冰紅茶,10)]。跑綠。
- **Step 2.5（commit 2 + Iron Law）**：`git add myProgram/sales/product_parser.py myProgram/sales/states/l2_l3_dialog.py tests/sales/test_product_parser.py` → `refactor(nlu): parse_products 重寫為統一 token-parser（任意序/多商品/garbled）`。跑 `python -m pytest tests/sales/` 看 `N passed`（0 failed）；branch 驗。

---

## 收尾（主 agent）
三段審 → ff-merge → push → 清理 → pineedtodo（Pi 複測 五張刮樂三瓶紅茶 / 紅茶食品 / 多商品任意序）。
