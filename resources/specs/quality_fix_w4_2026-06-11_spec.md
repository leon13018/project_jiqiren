# quality_fix_w4 — 代碼質檢修復 Wave 4（低價值 #10-#13）spec

## 1. 背景與動機

2026-06-11 質檢 review 的低價值清理項（使用者核准、#12 限縮為「無行為效果的確定冗餘」）：

- **#10**：`nlu.py` REJECT 雙集判定式 `contains_any(text, _KEYWORDS_REJECT) or equals_strict_short(text, _KEYWORDS_REJECT_STRICT_SHORT)` 逐字重複 ×2（normal mode「結帳」分支 / 通用「拒絕」分支）；且 cross-L cancel 8 個片語在 `_KEYWORDS_REJECT` 與 `_KEYWORDS_REJECT_L3_STRICT` 逐字雙份（平行維護隱患）。
- **#11**：`nlu.py` `_parse_compound_chinese` 十位分支與 `_parse_tens_part` 的「`[X]十Y` regex + `tens*10+units` 計算」逐字重複。
- **#12（限縮版）**：`keywords.py` `KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT`（["繼續","取消","继续"]）與 `KEYWORDS_INVALID_QTY_EXIT_STRICT_SHORT`（["退出","離開","离开"]）每個成員都已在對應 substring 集內——`equals_strict_short` 為真必蘊含 `contains_any` 為真（strip/case 不影響 substring 包含），整組零行為效果。prod 端零使用（已 grep：僅 keywords.py 定義 + KG 建構）。**刻意文檔化的 user 片語（substring 集內被短詞包含的長片語）不動。**
- **#13**：`l4.py` 計時器初始化 3 行 ×2（entry / 客服 reset——兩處必須同步否則 v3 雙計時器 spec 破功）；付款成功序列 3 行 ×2（終端 "s" / 客服 "scan"——同一鏈路 A 語意單元）。

W1-W3 已 merge（main `088927f`）；本 wave 基於其上。

## 2. 設計核心 + 行為規約

**鐵則：行為零改變**——`tests/sales/` **503 passed** 前後不變。#12 牽動 2 個測試檔的 assert 調整（測試直接釘資料層內容，屬資料清理的必然伴隨；本 spec 透明列出，無測試函式增刪）。

### #10：nlu REJECT KeywordGroup 化 + `_KEYWORDS_CROSS_L_CANCEL` 共享

1. import 補 `KeywordGroup`（自 `keyword_group`，與既有 re-export 同行）。
2. 新增共享清單（置於 `_KEYWORDS_REJECT` 定義前）：

```python
_KEYWORDS_CROSS_L_CANCEL = [
    "取消交易", "退出交易", "我想取消交易", "我要取消交易",
    "取消交易吧", "我想要取消交易",
    "取消这次交易", "退出这次交易",  # 簡體
]
```

3. `_KEYWORDS_REJECT` 與 `_KEYWORDS_REJECT_L3_STRICT` 各自刪掉行內的 8 片語、改 `[...] + _KEYWORDS_CROSS_L_CANCEL`（兩清單中該 8 片語都在尾端 → 串接保序，`contains_any` 用 `any()` 本就與順序無關）。
4. `_KEYWORDS_REJECT_STRICT_SHORT` 之後加 `_KG_REJECT = KeywordGroup(tuple(_KEYWORDS_REJECT), tuple(_KEYWORDS_REJECT_STRICT_SHORT))`，兩處判定式改 `_KG_REJECT.matches(text)`。`KeywordGroup.matches` 本體即同一雙呼叫——逐字等價。`contains_any` / `equals_strict_short` 仍被其他分支使用，import 保留。測試無 monkeypatch nlu 清單（已 grep，僅 docstring 提及）。

### #11：`_match_tens` 共用 helper

```python
def _match_tens(text: str) -> int | None:
    """匹配「[X]十Y」十位 pattern；命中回 tens*10+units，未命中回 None。

    共用：_parse_compound_chinese 十位分支 / _parse_tens_part（原兩份相同 regex + 計算）。
    """
    m = re.search(rf"([{_CHINESE_UNIT_CHARS}])?[十拾]([{_CHINESE_UNIT_CHARS}])?", text)
    if m is None:
        return None
    tens = CHINESE_DIGIT_MAP.get(m.group(1), 1)
    units_val = CHINESE_DIGIT_MAP.get(m.group(2), 0)
    return tens * 10 + units_val
```

兩 caller 改寫（regex 與計算逐字等價；`_parse_tens_part` 未命中時 fall through 純個位、`_parse_compound_chinese` 未命中時 return None——控制流不變）。

### #12：刪兩個零效果 strict_short 常數

- `keywords.py`：刪 380 / 385 行兩常數定義 + `__all__` 兩項（46 / 48 行）+ KG 建構改單參（`strict_short` 用 dataclass 預設 `()`）：

```python
KG_INVALID_QTY_CONTINUE = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_CONTINUE))
KG_INVALID_QTY_EXIT = KeywordGroup(tuple(KEYWORDS_INVALID_QTY_EXIT))
```

- 等價論證：∀kw ∈ strict_short, kw ∈ substrings；`text.strip().lower() == kw.lower()` ⟹ `kw.lower() in text.lower()` → `matches` 真值表不變。
- 測試伴隨調整（assert 改寫，無函式增刪）：
  - `test_keyword_group.py`：import 移除兩常數；`test_kg_invalid_qty_continue_wired` / `test_kg_invalid_qty_exit_wired` 的 strict_short assert 改 `== ()`。
  - `test_constants.py` `test_invalid_qty_constants_present_and_valued`：import 移除兩常數；`assert "繼續" in KEYWORDS_INVALID_QTY_CONTINUE_STRICT_SHORT` 改 `assert "繼續" in KEYWORDS_INVALID_QTY_CONTINUE`（守護意圖不變：「繼續」必須被辨識）。

### #13：l4 兩個微 helper

```python
def _l4_fresh_deadlines() -> tuple:
    """回傳 (budget_deadline, cycle_deadline)——自此刻起算（entry 與客服 reset 兩處必須同步）。"""
    now = time.monotonic()
    return now + L4_TOTAL_BUDGET, now + L4_QR_REFRESH_INTERVAL


def _l4_pay_success(io) -> tuple:
    """鏈路 A 共同體：付款成功 speak + 鞠躬動作 + 進 L5（終端 "s" 與客服 "scan" 共用）。"""
    io.speak(L4_A_PAY_SUCCESS)
    io.do_action(ACTION_L4_PAY)
    return ("L5", 0, 0)
```

替換 4 處（entry / reset 計時器初始化；dispatch "s" / service "scan" 付款序列）。抽取理由非單純行數：計時器兩處有「必須同步」的 spec 耦合（36=12×3 不變量）、付款序列是鏈路 A 語意單元。

## 3. 改檔範圍（高層）

| 檔 | 項 | 行數估 |
|---|---|---|
| `myProgram/sales/nlu.py` | #10 + #11 | 淨約 -10 |
| `myProgram/sales/constants/keywords.py` | #12 | -8 |
| `tests/sales/test_keyword_group.py` | #12 伴隨 | ±4 |
| `tests/sales/test_constants.py` | #12 伴隨 | ±3 |
| `myProgram/sales/states/l4.py` | #13 | 淨約 -4 |

## 4. Out of scope

- substring 清單內被短詞包含的長片語（刻意文檔化 user 片語，如 `KEYWORDS_C2_CANCEL` 的「幫我取消購買」）。
- `_KEYWORDS_REJECT_L3_STRICT` 內被「取消/退出」涵蓋的明示片語（檔內註解明定為可讀性保留）——#10 只收斂跨清單的 8 片語雙份，兩清單其餘內容不動。
- 其他 KG_* 配對（皆有真實 strict_short 差集）。
- review 判定刻意設計 7 項；任何文案 / timeout / 行為變更。

## 5. 規範與參考

派 **sales-coder**；plan 已給各項新舊碼與測試調整精確位置。背景：review 報告 #10-#13 段、`keyword_group.py` W1 oop_w1 慣例。

## 6. 測試指令 + 預期結果

每 commit 後：`python -m pytest tests/sales/` → **503 passed**（數量不變；#12 為 assert 改寫非增刪）。

## 7. Commit 規範（4 個獨立 commit，依序）

1. `refactor(sales): dedupe nlu REJECT matching via KeywordGroup + shared cross-L cancel list`（add：`myProgram/sales/nlu.py`）
2. `refactor(sales): extract _match_tens for compound Chinese numeral parsing`（add：`myProgram/sales/nlu.py`）
3. `refactor(sales): drop no-op INVALID_QTY strict_short subsets`（add：`myProgram/sales/constants/keywords.py tests/sales/test_keyword_group.py tests/sales/test_constants.py`）
4. `refactor(sales): extract L4 fresh-deadlines and pay-success helpers`（add：`myProgram/sales/states/l4.py`）

body 繁中 + `Co-Authored-By: Claude Opus <noreply@anthropic.com>`；禁 `-A`/`.`。

## 8. 流程鳥瞰

```
worktree quality-fix-w4 → spec+plan commit → sales-coder（4 commits）
→ 主 agent Iron Law（pytest 503 + branch + diff 對照）→ spec-reviewer → code-quality-reviewer
→ ExitWorktree(keep) → ff-merge → push → cleanup
```
