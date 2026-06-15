# 統一商品/數量 parser 重寫 + 完全同音 tie-break — SDD spec

> 2026-06-15 brainstorming 定案。Pi 實測揭露：現 `parse_products` 4 個拼湊機制（sticky-right / ② leading / Phase B split / ① window）無法 compose「任意順序 + 多商品 + garbled 品名/數量」；且「食品」類真歧義被安全閥拒絕。本 spec：(0) phonetic 完全同音 tie-break 解真歧義；(1) `parse_products` 重寫為統一 token-parser。
> Plan：[../plans/unified_product_parser_2026-06-15_plan.md](../plans/unified_product_parser_2026-06-15_plan.md)。

## 1. 背景與根因（全部實證，注入式可重現）

| 類別 | 例 | 現況 |
|---|---|---|
| 多商品 + 數量在前（**即使品名正確**） | 五張刮刮樂三瓶紅茶 | ❌ `[(刮刮樂,3),(冰紅茶,None)]` 錯亂（sticky-right 把 刮刮樂 右視窗 三瓶 綁錯） |
| garbled 品名 + 數量在前 | 五張刮樂三瓶紅茶 | ❌ `[(冰紅茶,3)]` 刮刮樂×5 整個掉 |
| garbled 品名 + 數量在前（單） | 五張刮樂 | ❌ `[]` |
| **真歧義數量** | 紅茶**食品**（=十瓶）| ❌ phonetic 回 None：食品 對 四瓶/十瓶 **皆 1.0**（食≡四 平翹舌、食=十 同音）→ margin 0 → 退回問一次 |

根因：(a) 綁定只 sticky-right + 單點 leading patch，多商品任意序無法 compose；(b) garbled 品名只在特定 split 形狀偵測；(c) 安全閥對「一個完全同音 + 一個平翹舌模糊」的平手無法分辨。

## 2. 設計核心

### 2.0 phonetic 完全同音 tie-break（解真歧義；`phonetic.py`）

`phonetic_match` 歧義閥改用 `(模糊相似度, 完全同音數)` 排序。完全同音數 = 逐位「聲韻母**未經模糊正規化**即相等」的音節數。
```
ranked = sorted(候選, key=(sim, exact), reverse=True)
top1 = ranked[0]; 若 sim[top1] < THRESHOLD → None
若僅 1 候選 → top1
top2 = ranked[1]
若 sim[top1] − sim[top2] ≥ MARGIN → top1            # 清楚勝（不變）
若 sim[top1] == sim[top2] 且 exact[top1] > exact[top2] → top1  # 完全同音 tie-break（解 食品→十瓶）
否則 → None                                          # sim 且 exact 皆平手 = 真‧無法區分
```
效果：`食品`→十瓶（食=十 同音 exact=1 勝 四瓶 exact=0）；`商品`→三瓶（本就清楚命中，不變）；真雙重平手仍 None。
**取捨**：偏「同音字混淆」（ASR 最常見錯）勝過「平翹舌發音錯」；極少數「顧客真說四瓶但念翹舌」會誤判十瓶——但替代是「再問一次」，user 取捨後選此。

### 2.1 `parse_products` 重寫為統一 token-parser（`product_parser.py`）

`parse_products(text) -> list[(product_name, qty|None)]`：

1. **精確商品 span**：沿用現 `_PRODUCT_KEYWORDS_PRE` 比對 + 重疊去重 → `(start,end,product)` 列。
2. **數量 span**：用數量字元集（阿拉伯 `\d` + `CHINESE_DIGIT_MAP` 字 + 乘數 `十拾百佰千仟萬万` + 單位 `瓶張`）掃最大連續段；每段 `parse_quantity` 得值（值為 None 的段棄）。（商品字 冰紅茶刮樂 不在此集 → 與商品 span 天然不重疊。）
3. **garbled 品名 span**：扣掉上兩者後的剩餘 segment（gap），逐段 `phonetic_match(gap, _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group)` → 命中即 garbled 商品 span（記原商品）。graceful（無 pypinyin→略過）；未命中 gap 留給 step 6。
4. **排序所有 token**（商品[精確/garbled] + 數量）依 start。
5. **鄰近綁定**：依位置掃每個數量 token → 綁「最近的**前一個未綁商品**」；無則綁「最近的**後一個未綁商品**」。標記已綁。
6. **garbled 數量（保 ①）**：仍未綁的商品 → 看緊鄰未用 gap（先右後左）→ `phonetic_match(gap, [w+unit for w in QTY_NUMBER_WORDS])`（該商品單位）→ 命中即綁。（含 2.0 tie-break，解 紅茶食品→×10。）
7. **組 raw**：商品依位置序，各帶綁定 qty 或 None。
8. **per-product dedup**：**原樣 port 現有規則 1/2/3**（同商品全 None 合一 / 有 qty 丟 None / 全有 qty 覆寫最後）。

**綁定規則涵蓋驗算**：五張刮刮樂三瓶紅茶→[(刮刮樂,5),(冰紅茶,3)]；刮刮樂五張紅茶三瓶→同；三瓶紅茶兩張刮刮樂→[(冰紅茶,3),(刮刮樂,2)]；五張刮樂三瓶紅茶→[(刮刮樂,5),(冰紅茶,3)]；紅茶三瓶→[(冰紅茶,3)]（=sticky-right）；紅茶食品→[(冰紅茶,10)]。

**subsume**：sticky-right（數量綁前一商品）/ ② leading（數量綁後一商品）/ ① window（step 6）/ Phase B split（step 3 garbled 品名 + step 5 綁定）四機制統一。`l2_l3_dialog` 的 ② phonetic 出口可**保留**（整句認不出時的商品名糾錯 fallback）——但多數情況新 parse_products 已能解（garbled 品名在 step 3）。

## 3. 改檔範圍

| # | 檔 | 類型 | 估計 |
|---|---|---|---|
| 1 | `myProgram/sales/phonetic.py` | 改 | ~+12（exact_count + 歧義閥 tie-break） |
| 2 | `myProgram/sales/nlu.py` | 改 | ~+10（`find_quantity_spans(text)` helper：回 `(start,end,value)` 列） |
| 3 | `myProgram/sales/product_parser.py` | **重寫** | parse_products token-parser（~+90/−60）；保 dedup；`_PRODUCT_PHONETIC_CANDIDATES`/`_product_group` 由 l2_l3_dialog 移入此檔（破循環 import） |
| 3b | `myProgram/sales/states/l2_l3_dialog.py` | 改 | ②出口改 import `_PRODUCT_PHONETIC_CANDIDATES`/`_product_group` from product_parser（移出後） |
| 4 | `tests/sales/test_phonetic.py` | 改 | 2.0 tie-break（食品→十瓶、真雙重平手→None） |
| 5 | `tests/sales/test_nlu.py` | 改 | `find_quantity_spans` 單元 |
| 6 | `tests/sales/test_product_parser.py` | 改 | comprehensive 案（多商品任意序 / garbled+數量前 / 食品）；**既有案全綠當回歸網** |

## 4. Out of scope

- filler 稀釋的 garbled（「我要刮樂」整段比不出）、插字 garble（三鮮瓶，需編輯距離）。
- 合音還原（③ 已做、不動）；confirm / 錢包 context。
- 閾值最終值（Pi 調）；`l2_l3_dialog` ② 出口邏輯不重寫（保留為 fallback）。

## 5. 規範與參考

- 派 **sales-coder（opus）**；TDD。**重寫高風險 → 現 575 測試是回歸網，全程保綠**；dedup 規則 1/2/3 原樣 port。
- reuse：`_PRODUCT_KEYWORDS_PRE`、`phonetic_match`、`parse_quantity`、`CHINESE_DIGIT_MAP`/`_CHINESE_MULTIPLIER_CHARS`、`QTY_NUMBER_WORDS`、`PRODUCTS`。
- 三段審不變（spec-reviewer + code-quality-reviewer）。

## 6. 測試指令 + 預期

`python -m pytest tests/sales/`；現 **575 passed** + 新增全綠、0 failed。

重點案例：
- **2.0**（test_phonetic，注入）：食品→十瓶（exact tie-break）；商品→三瓶（不變）；構造真雙重平手（兩候選 sim 且 exact 皆同）→ None。
- **find_quantity_spans**（test_nlu）：「五張刮刮樂三瓶」→ [(0,2,5),(5,7,3)] 之類（span + value）。
- **parse_products comprehensive**（test_product_parser）：
  - 五張刮刮樂三瓶紅茶→[(刮刮樂,5),(冰紅茶,3)]、刮刮樂五張紅茶三瓶→同、三瓶紅茶兩張刮刮樂→[(冰紅茶,3),(刮刮樂,2)]
  - 五張刮樂三瓶紅茶→[(刮刮樂,5),(冰紅茶,3)]（mock phonetic 品名段）、五張刮樂→[(刮刮樂,5)]
  - 紅茶食品→[(冰紅茶,10)]（mock 或注入）
  - **回歸**：紅茶三瓶 / 紅茶刮刮樂 / dedup 規則 1/2/3 / ① 紅茶商品 / 既有全案不變。

## 7. Commit 規範

- worktree：`worktree-unified-parser`。
- 建議 3 commit：(0) `feat(phonetic): 歧義閥完全同音 tie-break（解 食品→十瓶）`；(1) `feat(nlu): find_quantity_spans helper`；(2) `refactor(nlu): parse_products 重寫為統一 token-parser（任意序/多商品/garbled）`。
- `git add` 明列檔名；message 繁中描述 + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
[approval] → worktree → commit spec/plan
  → 派 sales-coder（TDD：Part0 tie-break → Part1 find_quantity_spans → Part2 parser 重寫，全程保 575 綠）
  → 三段審 → Iron Law → ff-merge → push → 清理
  → pineedtodo：Pi 複測 五張刮樂三瓶紅茶 / 紅茶食品 / 多商品任意序
```
