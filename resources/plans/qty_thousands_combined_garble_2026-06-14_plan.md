# Bugfix 千/萬 + combined garble — plan（HOW / step-by-step TDD）

> Spec：[../specs/qty_thousands_combined_garble_2026-06-14_spec.md](../specs/qty_thousands_combined_garble_2026-06-14_spec.md)。
> debugging Phase 4：**先寫重現 bug 的 failing test，再修**。指令 `python -m pytest tests/sales/`。

---

## Part 1 — Bug1：`nlu.py` 數量解析支援 千/萬

- **Step 1（RED 重現）**：`test_nlu.py`（或 test_nlu_boundary）加 `assert parse_quantity("一千張") == 1000`。跑 → FAIL（現回 1）。
- **Step 2（Green）**：`nlu.py`：
  - 新增 multiplier 認列：`千仟萬万`（與既有 `十拾百佰` 並列）；定義給 `has_quantity` 與 compound 共用的數字/multiplier 集。
  - `has_quantity` 改：阿拉伯數字 **或** `CHINESE_DIGIT_MAP` 字 **或** multiplier 字 → True。
  - 預編譯 `_THOUSANDS_RE`/`_TENTHOUSANDS_RE`（mirror `_HUNDREDS_RE`）。
  - `_parse_compound_chinese` 加優先序 萬→千→百→十：`萬`→`(g1 or 1)*10000 + 解析rest`、`千`→`*1000 + 解析rest`（rest 走既有百/十/個位）。
  跑 Step 1 → PASS。
- **Step 3（補案 + 回歸）**：`parse_quantity` 一千張/一千=1000、兩千=2000、一萬=10000、一千五百=1500、五千=5000；`has_quantity("千張")`/`("一千張")`=True。**回歸**：五十=50、一百=100、三=3、十=10、十二=12、二十一=21、三百五十二=352 不變。跑 → 綠。
- **Step 4（bug1 整合）**：`test_states.py` 問數量 sub-loop 答「一千張」→ `classify_qty` 超量 → `invalid_qty_reask` 路徑（非靜默加 1 張）。跑 → 綠。
- **Step 5（commit 1）**：`git add myProgram/sales/nlu.py tests/sales/test_nlu.py tests/sales/test_states.py` → `fix(nlu): parse_quantity 支援 千/萬（解一千張靜默變1）`。`git -C "<worktree>" branch --contains <SHA>` 驗。跑全量 → 綠。

---

## Part 2 — Bug2：商品名歪+數量同句糾錯

- **Step 6（RED 單元）**：`test_nlu.py` 加 `assert split_at_quantity("刮樂一千張") == ("刮樂","一千張")`。跑 → FAIL（無函式）。
- **Step 7（Green 單元）**：`nlu.py` 加 `split_at_quantity(text) -> tuple[str,str]`：掃描找首個數量指示字（阿拉伯數字 / `CHINESE_DIGIT_MAP` 字 / multiplier `十拾百佰千仟萬万`）的 index `i`；`i is None`→`(text,"")`；`i==0`→`("",text)`；否則 `(text[:i], text[i:])`。補案：刮刮樂→("刮刮樂","")、一千張→("","一千張")、三張→("","三張")、刮樂三張→("刮樂","三張")。跑 → 綠。
- **Step 8（RED 整合）**：`test_states.py` 問商品 unclear 出口，`patch` `l2_l3_dialog.phonetic_match` 用 side_effect（整句「刮樂一千張」→ None、`"刮樂"`→`"刮刮樂"`），顧客講「刮樂一千張」→ 斷言 cart 走刮刮樂 + qty 1000 超量 reask（**非 unclear**）。跑 → FAIL。
  > 註：`parse_products("刮刮樂一千張")` 找到刮刮樂、視窗「一千張」經 bug1 修後 `parse_quantity`=1000（≠None）→ ① 不觸發、product_parser.phonetic_match 不被呼叫；故只需 patch `l2_l3_dialog.phonetic_match`。
- **Step 9（Green 整合）**：`l2_l3_dialog.py` `_dispatch` ② 區塊改為統一收斂：
  ```python
  corrected_response = None
  whole = phonetic_match(response, _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group)
  if whole is not None:
      corrected_response = whole
  else:
      head, tail = split_at_quantity(response)
      if head and tail:
          ch = phonetic_match(head, _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group)
          if ch is not None:
              corrected_response = ch + tail
  if corrected_response is not None:
      products = parse_products(corrected_response)
      if products:
          return self._handle_products(products, in_main_loop=in_main_loop)
  # 落回既有 B-1 unclear
  ```
  import `split_at_quantity`。跑 Step 8 → PASS。
- **Step 10（回歸 + 邊界）**：`test_states.py` 加：拆句失敗（「刮樂以前」無數量段、或商品段糾不出）→ unclear 不變；整句 match 仍正常（「刮樂」→刮刮樂，沿用既有）；拒絕/結帳 garble → 不被劫持（早 return）。跑全量 → 綠。
- **Step 11（commit 2 + Iron Law）**：`git add myProgram/sales/nlu.py myProgram/sales/states/l2_l3_dialog.py tests/sales/test_nlu.py tests/sales/test_states.py` → `fix(nlu): 問商品糾錯支援商品名歪+數量同句（拆句）`。跑 `python -m pytest tests/sales/` 看 `N passed`（0 failed）；branch 驗。

---

## 收尾（主 agent）
3 段審 → ff-merge → push → 清理 → pineedtodo 記 Pi 複測：一千張→「最多50」、刮樂一千張→刮刮樂（超量 reask）。
