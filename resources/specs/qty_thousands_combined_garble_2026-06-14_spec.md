# Bugfix：數量 千/萬 解析 + 商品名歪+數量同句糾錯 — SDD spec

> Pi 實測（2026-06-14）發現兩 bug，根因已 systematic-debugging 確認。皆 myProgram code → SDD。
> Plan：[../plans/qty_thousands_combined_garble_2026-06-14_plan.md](../plans/qty_thousands_combined_garble_2026-06-14_plan.md)。

## 1. 背景與根因（已實證）

| Bug | 現象 | 根因（confirmed） |
|---|---|---|
| **1** | 「一千張」→ 加入 **1** 張（靜默變小） | `nlu._parse_compound_chinese` 只處理 `十`(tens)/`百`(hundreds)，**無 `千`/`萬`**；「一千」複合解析失敗 → 單字 fallback 抓「一」→ 1。`千`/`萬` 不在 `CHINESE_DIGIT_MAP`，`has_quantity("千張")` 亦回 False。實證：`parse_quantity("一千張")==1`、`("兩千")==2`、`("一萬張")==1`。 |
| **2** | 「刮樂一千張」→ unclear（無法識別） | `l2_l3_dialog._dispatch` 的②糾錯 `phonetic_match("刮樂一千張", 商品候選)` 比對**整句** vs 商品名（2-3字）→ 相似度 ~0.4(<0.75)、非子串 → None → unclear。**商品名歪 + 數量同句**：①只在商品名認得時補數量、②只比整句商品名，兩者皆不接此組合。 |

realistic max = `MAX_QTY_PER_ITEM=50`，故「一千」正確行為應是**超量 reask「最多只能選購 50」**，而非靜默變 1。

## 2. 設計核心

### 2.1 Bug1 — `nlu.py` 數量解析支援 千/萬

- **數字偵測集擴充**：新增 multiplier 認列 `千仟萬万`（`十百` 已有）。`has_quantity` 改為：含阿拉伯數字 **或** `CHINESE_DIGIT_MAP` 字 **或** multiplier 字（`十百千萬` 及異體）→ True。解「千張」=有數量。
- **`_parse_compound_chinese` 擴 千/萬**（mirror 既有 `百` pattern）：
  - 預編譯 `_TENTHOUSANDS_RE`（`([單位])?[萬万](rest)?`）、`_THOUSANDS_RE`（`([單位])?[千仟](rest)?`）。
  - 優先序：萬 → 千 → 百 → 十。`萬` 命中：`(單位 or 1)*10000 + 解析(rest)`；`千` 同理 *1000；rest 由既有 百/十/個位邏輯解析（遞迴或既有 `_parse_tens_part` 擴版）。
  - 範圍：常見複合（一千=1000、一千五百=1500、兩千=2000、一萬=10000、五千=5000）。**`零` 連接（一萬零五十）out of scope**（不現實、且 >50 必超量，結果不影響 reask）。
- 結果：`一千張` → `parse_quantity`=1000 → `classify_qty` 超量 → `invalid_qty_reask`「最多只能選購 50」。

### 2.2 Bug2 — `l2_l3_dialog.py` 商品名歪+數量同句糾錯

- **`nlu.py` 新增 `split_at_quantity(text) -> tuple[str, str]`**：回 `(head, tail)`，`tail` 從**首個數量指示字**（阿拉伯數字 / `CHINESE_DIGIT_MAP` 字 / multiplier `十百千萬`）起；無數量字 → `(text, "")`；數量字在開頭 → `("", text)`。例：`"刮樂一千張"→("刮樂","一千張")`、`"刮刮樂"→("刮刮樂","")`。
- **②糾錯擴充**（`_dispatch` unclear 出口，現整句 `phonetic_match` 之後）：整句 match 失敗時 → `split_at_quantity` 拆出 `head`(商品段)/`tail`(數量段)；`head` 與 `tail` 皆非空 → `phonetic_match(head, 商品候選, group_key=...)` 糾商品段 → 命中則 `corrected_response = 糾正商品 + tail` → `parse_products(corrected_response)` → `_handle_products`（① 接 tail 數量、bug1 修後 一千張=1000→超量）。
- 統一結構（整句 / 拆句 兩路皆收斂到 `corrected_response → parse_products → _handle_products`），避免重複。

**行為規約**：
- 只在②（問商品 NLU 放棄出口）整句 match 失敗後才嘗試拆句；拒絕/想一下/結帳/客服/正常解析皆已先 return，不被劫持。
- 拆句失敗（無數量段 / 商品段糾不出）→ `None` → 落回既有 B-1 unclear，不劣化。
- Bug1 對所有數量路徑生效（問數量 sub-loop、parse_products 視窗、① ②）；行為從「靜默小數」變「正確大數→超量 reask」。

## 3. 改檔範圍

| # | 檔 | 類型 | 估計 |
|---|---|---|---|
| 1 | `myProgram/sales/nlu.py` | 改 | ~+30（multiplier 集 + has_quantity + 千/萬 compound + `split_at_quantity`） |
| 2 | `myProgram/sales/states/l2_l3_dialog.py` | 改 | ~+12（② 拆句糾錯分支，收斂進既有 corrected→parse_products） |
| 3 | `tests/sales/test_nlu.py`（或 test_nlu_boundary） | 改 | bug1 parse_quantity 千/萬 + has_quantity + `split_at_quantity` 單元測試 |
| 4 | `tests/sales/test_states.py` | 改 | bug1 整合（一千張→超量reask）+ bug2 整合（刮樂一千張→刮刮樂，mock phonetic_match） |

## 4. Out of scope

- 數量 `零` 連接（一萬零五十）、`億`+；商品名在句中夾 filler（「我要刮樂三張」product 非開頭）→ 後續。
- 合音還原（醬就好）。
- 既有正常解析 / confirm / 錢包 / 問數量在商品前（三瓶紅茶）不碰。
- 閾值最終值（Pi 調）。

## 5. 規範與參考

- 派 **sales-coder（opus）**；TDD（**先寫 failing test 重現 bug** 再修——debugging Phase 4）。
- **既有 reuse / 對齊 pattern**：bug1 mirror `_HUNDREDS_RE`/`_parse_tens_part`；bug2 reuse `phonetic_match`/`parse_products`/`_handle_products`（Phase B 抽出）。
- 根因見本 spec §1（systematic-debugging Phase 1 實證）。

## 6. 測試指令 + 預期

指令：`python -m pytest tests/sales/`；預期現 **536 passed** + 新增全綠、0 failed。

重點案例：
- **bug1 單元**：`parse_quantity` 一千=1000 / 一千張=1000 / 兩千=2000 / 一萬=10000 / 一千五百=1500；`has_quantity("千張")`/`("一千張")`=True；**回歸** 五十=50 / 一百=100 / 三=3 / 十=10 不變。
- **bug1 整合**：問數量 sub-loop 答「一千張」→ `classify_qty` 超量 → `invalid_qty_reask`（非靜默加 1）。
- **bug2 單元**：`split_at_quantity` 刮樂一千張→("刮樂","一千張") / 刮刮樂→("刮刮樂","") / 一千張→("","一千張") / 三張→... 。
- **bug2 整合**（mock phonetic_match）：問商品「刮樂一千張」→ 整句 match None → 拆句 → mock `phonetic_match("刮樂")`回"刮刮樂" → `parse_products("刮刮樂一千張")` → 刮刮樂 + qty 1000 → 超量 reask（不再 unclear）；拆句失敗（無數量/糾不出）→ unclear 不變。
- **回歸**：Phase A/B 全案（注入 fake、round-trip 守則、問數量/問商品 wiring）全綠。

## 7. Commit 規範

- worktree：`worktree-qty-bugfix`。
- 建議 2 commit：① `fix(nlu): parse_quantity 支援 千/萬（解一千張靜默變1）`；② `fix(nlu): 問商品糾錯支援商品名歪+數量同句（拆句）`。
- `git add` 明列檔名；message 英文 type 前綴 + 繁中描述 + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
[approval] → worktree-qty-bugfix → commit spec/plan
  → 派 sales-coder（TDD：先重現 bug 的 failing test → 修）
  → 3 段審 → Iron Law → ff-merge → push → 清理
  → pineedtodo：Pi 複測 一千張（→最多50）+ 刮樂一千張（→刮刮樂）
```
