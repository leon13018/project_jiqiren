# 拼音近音糾錯 Phase A — plan（HOW / step-by-step TDD）

> Spec（WHAT）：[../specs/pinyin_correction_phaseA_2026-06-14_spec.md](../specs/pinyin_correction_phaseA_2026-06-14_spec.md)。
> 每 step ≈ 一原子動作，依 Red→Green→Refactor。指令一律 `python -m pytest tests/sales/test_phonetic.py`（單元）或 `python -m pytest tests/sales/`（全量）。

---

## Part 1 — `phonetic.py` 核心（注入式測試，不碰真 pypinyin）

測試共用 fake（放 `test_phonetic.py` 頂層）：
```python
_FAKE = {
    "商": ("sh","ang"), "品": ("p","in"),
    "一": ("","i"), "兩": ("l","iang"), "三": ("s","an"), "四": ("s","i"),
    "五": ("","u"), "六": ("l","iu"), "七": ("q","i"), "八": ("b","a"),
    "九": ("j","iu"), "十": ("sh","i"), "瓶": ("p","ing"), "張": ("zh","ang"),
}
def fake(ch): return _FAKE[ch]
QTY = ["一瓶","兩瓶","三瓶","四瓶","五瓶","六瓶","七瓶","八瓶","九瓶","十瓶"]
```

- **Step 1（Red）**：`test_phonetic.py` 寫核心 failing test：
  `assert phonetic_match("商品", QTY, to_pinyin=fake) == "三瓶"`。
  跑 → FAIL（`ModuleNotFoundError: phonetic`）。
- **Step 2（骨架）**：建 `myProgram/sales/phonetic.py`：
  - 模組 docstring（繁中，說明職責 + Phase A 範圍 + 紅線「頂層禁 import pypinyin」）。
  - 常數：`SIMILARITY_THRESHOLD = 0.75`、`AMBIGUITY_MARGIN = 0.25`（各附「Pi 實測調校」註解）。
  - 等價表：`_INITIAL_EQUIV = {"sh":"s","ch":"c","zh":"z","l":"n","h":"f"}`、`_FINAL_EQUIV = {"ing":"in","eng":"en","ang":"an"}`。
  - `def phonetic_match(text, candidates, *, to_pinyin=None) -> str | None: return None`（暫）。
  跑 → 核心 test FAIL（回 None 非「三瓶」）。
- **Step 3（Green 核心）**：實作 `phonetic.py` 比對：
  - `_canon_initial(i)`：`_INITIAL_EQUIV.get(i, i)`；`_canon_final(f)`：`_FINAL_EQUIV.get(f, f)`。
  - `_syllable_equiv(a, b)`：聲韻母 canon 後皆相等。
  - `phonetic_match`：守衛（空 text/candidates → None）；`to_pinyin or _default_to_pinyin`；取 text 與各 candidate 逐字音；逐 candidate 算 `similarity = 命中數 / max(len)`；取 top-1/top-2（單候選 top-2=0.0）；歧義閥 → 回 candidate 或 None。
  - `_default_to_pinyin` 先留「Step 5 補」之 stub（本步測試都注入 fake，不會呼叫）。
  跑 → 核心 test PASS。
- **Step 4（Red→Green 補單元測試）**：`test_phonetic.py` 補以下案例，逐一跑綠：
  1. `張` 單位變體：`phonetic_match("商張", ["一張",…,"三張",…], fake2)` → `"三張"`（fake2 加 `商→(sh,ang)` 已有、`張→(zh,ang)`）。
  2. 歧義 → None：建兩個與 text 同分（皆 1.0）的候選 → 回 `None`（margin 不足）。
  3. 無夠近 → None：text 與所有候選皆 < 0.75 → 回 `None`。
  4. 聲母平翹舌等價：`s`↔`sh`、`z`↔`zh`、`c`↔`ch`、`n`↔`l`、`f`↔`h` 各構一對命中。
  5. 韻母前後鼻音等價：`in`↔`ing`、`en`↔`eng`、`an`↔`ang` 各構一對命中。
  6. 完全相同字 → 命中（相似度 1.0）。
  7. 空 `text` → None；空 `candidates` → None。
  8. 長度不等：text 2 字 vs candidate 3 字、僅 2 字命中 → `2/3 < 0.75` → None。
  9. 介音**不**等價（守 Phase A 邊界）：`(g,ua)` vs `(g,a)` → 不命中（介音留 Phase B）。
- **Step 5（graceful + production seam）**：
  - 實作 `_default_to_pinyin(char)`：函式內 `import pypinyin`（lazy），`Style.INITIALS`/`Style.FINALS`、`strict=False` 取 `(聲母, 韻母)`。
  - `phonetic_match` 取音段包 `try/except ImportError: return None`。
  - `test_phonetic.py` 加：`to_pinyin=None`（不注入）在無 pypinyin 環境 → `phonetic_match("商品", QTY)` 回 `None`（Windows graceful）。
  跑 `python -m pytest tests/sales/test_phonetic.py` → 全綠。
- **Step 6（commit 1）**：`git add myProgram/sales/phonetic.py tests/sales/test_phonetic.py` → commit `feat(phonetic): 新增拼音近音比對核心`。`git branch --contains <SHA>` 驗落 `worktree-pinyin-phase-a`。

---

## Part 2 — 問數量 sub-loop 掛載（`_l2_l3_qty_followup.py`）

整合測試掛 `tests/sales/test_states.py`（既有 qty sub-loop 流程測試所在），用 `unittest.mock.patch` mock `_l2_l3_qty_followup.phonetic_match`（Windows 無 pypinyin，不能依賴真演算法；演算法已由 Part 1 單元測試覆蓋）。

- **Step 7（Red）**：`test_states.py` 新增整合 test：
  問數量 sub-loop（透過 `resolve_and_add_products` 既有 harness），顧客缺數量商品後答「商品」（非數字、非客服/拒絕/結帳）；`patch` 使 `phonetic_match` 回 `"三瓶"`。
  斷言：該商品以 `qty=3` 加入 cart（`added` True，無 cancel_notice）。
  跑 → FAIL（wiring 未實作，「商品」走 attempts++ → skip）。
- **Step 8（Refactor，行為不變）**：`_l2_l3_qty_followup.py`：
  - import：`from myProgram.sales.phonetic import phonetic_match`。
  - module 級 `_QTY_NUMBER_WORDS = ("一","兩","三","四","五","六","七","八","九","十")`。
  - 抽 `def _apply_resolved_qty(qty, product, unit, cart, io) -> tuple[bool, str|None, str|None]`：搬現 `has_quantity` 分支內 `classify_qty` → `at_cap`（speak + return False,None,None）/ 無效（`invalid_qty_reask` + control 冒泡）/ `ok`（`add_item` + return True,None,None）邏輯。
  - `has_quantity` 分支改為 `return _apply_resolved_qty(parse_quantity(follow_up), product, unit, cart, io)`。
  跑 `python -m pytest tests/sales/` → **仍全綠**（純重構，證 helper 抽取無回歸）。
- **Step 9（Green）**：在「其他 bucket」（`if follow_intent == "結帳"` 區塊**之後**、`attempts += 1` **之前**）插入：
  ```python
  corrected = phonetic_match(follow_up, [w + unit for w in _QTY_NUMBER_WORDS])
  if corrected is not None:
      return _apply_resolved_qty(parse_quantity(corrected), product, unit, cart, io)
  ```
  跑 Step 7 整合 test → PASS。
- **Step 10（補回歸 + 邊界）**：`test_states.py` 加：
  1. `patch` `phonetic_match` 回 `None` → 顧客答「商品」→ 既有 `attempts++` / `QTY_CLARIFY_TEMPLATE` reprompt 行為**不變**（達 3 次 skip + cancel_notice）。
  2. `patch` 回超量詞（如 `"五十瓶"`，經 `parse_quantity` → 50+ 觸發 over_limit）→ 走 `invalid_qty_reask`（驗 control 路徑，可 mock reask 回 `"resolved"`）。
  3. （回歸保險）客服 / 拒絕 / 結帳 回應仍各自正確分流，**不被 phonetic 劫持**（這些在插入點之前 return，理論上不受影響，補 1 條確認）。
  跑 → 全綠。
- **Step 11（commit 2 + Iron Law）**：`git add myProgram/sales/states/_l2_l3_qty_followup.py tests/sales/test_states.py` → commit `feat(nlu): 問數量 sub-loop 掛載拼音糾錯`。
  跑 `python -m pytest tests/sales/` 看 `N passed`（N > 504、0 failed）；`git branch --contains <SHA>` 驗落 `worktree-pinyin-phase-a`。

---

## 收尾（主 agent，approval 後流程）

3 段審（spec-reviewer → code-quality-reviewer）→ ff-merge main → push → worktree 清理 → 寫 `resources/pineedtodo/` 記 Pi 端 `pip install pypinyin` + 實測調閾值。
