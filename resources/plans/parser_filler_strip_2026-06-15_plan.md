# parse_products filler-strip + C2_DECISION_TIMEOUT 守值 — plan（HOW / TDD）

> **For agentic workers:** 由 **sales-coder** 執行；步驟 Red→Green→Refactor。
> Spec：[../specs/parser_filler_strip_2026-06-15_spec.md](../specs/parser_filler_strip_2026-06-15_spec.md)。
> **現 589 測試是回歸網，每步後跑 `python -m pytest tests/sales/` 保綠。**

**Goal**：`parse_products` 在 garbled 品名 phonetic 比對前剝除意圖前綴 filler（解「我要刮樂」→刮刮樂）；並補 `C2_DECISION_TIMEOUT==6` 守值斷言。

**Architecture**：在 `product_parser.py` step 3（garbled 品名 span）對每個 gap 先 `_strip_filler` 再 `phonetic_match`；filler 為意圖前綴常數表、單一前綴剝除。D1 為純測試補強。

> 範圍小但含邏輯分支 → 2 個獨立 commit。Part 1（C2）與 Part 2（D1）無耦合。

---

## Part 1（C2）— gap filler-strip

**Files:**
- Modify: `myProgram/sales/product_parser.py`（加 `_GAP_FILLER_PREFIXES` + `_strip_filler`；step 3 phonetic 前剝）
- Test: `tests/sales/test_product_parser.py`

- [ ] **Step 1.1（RED）— 加 C2 正向測試**
  在 `tests/sales/test_product_parser.py` 既有 garbled 測試區（`_garbled_product_side_effect` 定義之後）加：
  ```python
  def test_parse_products_filler_diluted_garbled_name() -> None:
      """「我要刮樂」：意圖前綴 filler「我要」剝除後殘段「刮樂」→ garbled 刮刮樂。"""
      se = _garbled_product_side_effect({"刮樂": "刮刮樂"})
      with patch.object(product_parser, "phonetic_match", side_effect=se):
          assert product_parser.parse_products("我要刮樂") == [("刮刮樂", None)]
          assert product_parser.parse_products("我要刮樂三張") == [("刮刮樂", 3)]
  ```
  Run: `python -m pytest tests/sales/test_product_parser.py::test_parse_products_filler_diluted_garbled_name -v`
  Expected: **FAIL**——未剝 filler 時 phonetic_match 收到整段「我要刮樂」，mock（只認「刮樂」）回 None → `parse_products` 回 `[]`，斷言不符。

- [ ] **Step 1.2（GREEN）— 加 `_strip_filler` 並在 step 3 套用**
  在 `product_parser.py` 的 `_product_group` 函式**之後**、`_find_product_spans` **之前**插入：
  ```python
  # gap 意圖前綴 filler（2026-06-15 C2）：顧客口語常帶「我要 X」，X 為 garbled 品名時
  # 整段 phonetic 對齊被前綴稀釋而失敗。比對前剝單一前綴（長詞先試，避免「要」先吃掉「我要」），
  # 殘段交既有引擎（疊字去重等）糾錯。只在 gap 上、只剝一次、剝空→不誤造商品。
  _GAP_FILLER_PREFIXES = ("我想要", "我要", "我想", "幫我", "給我", "想要", "要")


  def _strip_filler(seg: str) -> str:
      """剝除 gap 開頭單一意圖前綴 filler；無命中回原樣。"""
      for f in _GAP_FILLER_PREFIXES:
          if seg.startswith(f):
              return seg[len(f):]
      return seg
  ```
  並把 step 3 的 phonetic 呼叫（現約 184 行）由：
  ```python
          corrected = phonetic_match(
              seg.strip(), _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group
          )
  ```
  改為：
  ```python
          corrected = phonetic_match(
              _strip_filler(seg.strip()), _PRODUCT_PHONETIC_CANDIDATES, group_key=_product_group
          )
  ```
  Run: `python -m pytest tests/sales/test_product_parser.py::test_parse_products_filler_diluted_garbled_name -v`
  Expected: **PASS**（剝後「刮樂」→ mock 回刮刮樂）。

- [ ] **Step 1.3（回歸補案，無需 mock）**
  同檔加（這些走真 phonetic_match，Windows 無 pypinyin 回 None，靠精確商品 span / 空殘段）：
  ```python
  def test_parse_products_filler_before_exact_product_unaffected() -> None:
      """filler 在精確商品前：「我要冰紅茶」→ 冰紅茶精確命中，gap「我要」剝空 → 不誤造商品。"""
      assert product_parser.parse_products("我要冰紅茶") == [("冰紅茶", None)]

  def test_parse_products_pure_filler_yields_nothing() -> None:
      """純 filler / 無商品殘段 → 不誤造商品。"""
      assert product_parser.parse_products("我要") == []
      assert product_parser.parse_products("今天天氣很好") == []
  ```
  Run: `python -m pytest tests/sales/` → 既有 589 + 新 3 個函式全綠。
  > ⚠️ 若任何既有案翻動（尤其 `test_parse_products_scratch_letou_and_caijuan_alias` 的「我要樂透 2 張」）：先判是否真 regression。預期**不翻**——樂透是精確 keyword、gap「我要」剝空後與原本 phonetic None 同結果。翻了先回報、勿無腦改 assert。

- [ ] **Step 1.4（commit 1）**
  ```
  git add myProgram/sales/product_parser.py tests/sales/test_product_parser.py
  git commit -m "feat(nlu): parse_products gap 剝意圖前綴 filler（解 我要刮樂→刮刮樂）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```
  commit 後 `git branch --contains <SHA>` 驗落 `worktree-filler-strip`（落 main 停回報，Gotcha M）。

---

## Part 2（D1）— C2_DECISION_TIMEOUT 守值斷言

**Files:**
- Test: `tests/sales/test_constants.py`

- [ ] **Step 2.1（補守值，值已正確 → 直接 PASS）**
  `test_constants.py` 的 `test_time_constants_match_spec`（現約 27-32 行）內，於既有 timing 斷言末尾加一行：
  ```python
      assert const.C2_DECISION_TIMEOUT == 6
  ```
  （`C2_DECISION_TIMEOUT` 已從 `const`（`myProgram.sales.constants`）可取，無需改 import。）
  Run: `python -m pytest tests/sales/test_constants.py::test_time_constants_match_spec -v`
  Expected: **PASS**（值本就 6；本斷言補回歸網捕捉未來誤改，與 sibling timing 守值一致——無 RED 屬正常，非行為變更）。

- [ ] **Step 2.2（commit 2）**
  ```
  git add tests/sales/test_constants.py
  git commit -m "test(constants): 補 C2_DECISION_TIMEOUT 守值斷言（補齊 timing 常數 pattern）" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```
  branch 驗同上。

---

## Part 3（全量回歸）

- [ ] **Step 3.1**
  Run: `python -m pytest tests/sales/ -v --tb=short`（回報尾 ~30 行）
  Expected: `N passed`（0 failed；589 + 新增測試函式）。任何 fail/error → 不交付、停回報。

---

## 收尾（主 agent）
- 小改動：**跳 spec-reviewer**（主 agent 自驗 spec §3 對照 + 自跑 pytest）→ **code-quality-reviewer 照跑** → Iron Law 親跑 pytest 看 `N passed` → ff-merge → push（Stop hook sync Pi）→ 清理 worktree。
- **watchlist.md consolidate**（本批收尾統一做）：遷 perf §10 4 條入 `resources/watchlist.md`——D1 **closed**（本 commit 補守值）/ D2 shared.py **open**（13 常數 62 行，未達 >20 或 >120 觸發）/ D3 即時 2 孤兒已清、通用工具 **open-deferred** / D4 daemon warning **open-deferred**。
- **無 pineedtodo**：純解析邏輯、無新依賴、無 Pi 操作（「我要刮樂」殘段解析 Pi 已實證，複測併下次 demo 即可）。
