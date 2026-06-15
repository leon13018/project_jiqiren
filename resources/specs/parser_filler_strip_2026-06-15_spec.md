# parse_products gap filler-strip（解 filler 稀釋 garbled）+ C2_DECISION_TIMEOUT 守值斷言 — SDD spec

> 2026-06-15 brainstorming triage 定案（精實批次 C2 + D1）。
> Plan：[../plans/parser_filler_strip_2026-06-15_plan.md](../plans/parser_filler_strip_2026-06-15_plan.md)。

## 1. 背景與根因（實證可重現）

### C2 — filler 稀釋的 garbled 品名解不出
顧客口語常帶意圖前綴：「**我要刮樂**」（刮樂 = 刮刮樂 garbled）。現 `parse_products("我要刮樂")`：
- `_find_product_spans` 無精確命中（刮樂非 keyword）；`find_quantity_spans` 無；
- 剩餘 gap = 整段「我要刮樂」→ `phonetic_match("我要刮樂", _PRODUCT_PHONETIC_CANDIDATES)` **失敗**（「我要」稀釋了音節對齊，子串 fallback 也救不到）→ 回 `[]`。
- 結果：顧客講「我要刮樂」系統聽不懂。

**根因**：step 3 直接拿整個 gap 做 phonetic_match，未剝除意圖前綴 filler；而剝掉「我要」後殘段「刮樂」現有引擎（疊字去重 刮刮→刮）本就能命中刮刮樂。

### D1 — C2_DECISION_TIMEOUT 缺守值斷言（perf §10 watch 項）
`test_constants.py` 系統性守所有 timing 常數值（`WAIT_NO_RESPONSE==6` / `L4_TOTAL_BUDGET==36` / `QTY_FOLLOWUP_TIMEOUT==12` / `INVALID_QTY_*` …），**唯獨 `C2_DECISION_TIMEOUT`（=6，C-2 三選一 budget）漏**。改動該值無回歸網捕捉。

## 2. 設計核心

### 2.1 gap filler-strip（`product_parser.py`）
新增 `_GAP_FILLER_PREFIXES`（意圖前綴，長到短排）+ `_strip_filler(seg)`：startswith 命中首個前綴即剝一次，否則原樣。step 3 phonetic_match 前先剝：
```python
_GAP_FILLER_PREFIXES = ("我想要", "我要", "我想", "幫我", "給我", "想要", "要")
def _strip_filler(seg):
    for f in _GAP_FILLER_PREFIXES:   # 長詞先試，避免「要」先吃掉「我要」
        if seg.startswith(f):
            return seg[len(f):]
    return seg
```
step 3 內：`cand = _strip_filler(seg.strip())` → `phonetic_match(cand, ...)`；命中即 garbled 商品（span 仍用**原 gap 邊界**，filler 被吸收進該商品 span）。

**保守性**：只剝**單一前綴**、只在 gap 上（精確商品 span 不經此路徑）；剝到空字串 → phonetic None → 收 unused_gap（不誤造商品）。

**驗算**：
- 「我要刮樂」→ 剝「我要」→「刮樂」→ 刮刮樂 → `[("刮刮樂", None)]`
- 「我要刮樂三張」→ garbled 刮刮樂(0-4) + qty 三張 → `[("刮刮樂", 3)]`
- 「我要冰紅茶」→ 冰紅茶為精確 span，gap 僅「我要」→ 剝後空 → `[("冰紅茶", None)]`（不變）
- 「我要」/「今天天氣很好」→ 無殘段命中 → `[]`（不誤造）

### 2.2 C2_DECISION_TIMEOUT 守值斷言（`test_constants.py`）
`test_time_constants_match_spec` 內補一行 `assert const.C2_DECISION_TIMEOUT == 6`（與 sibling timing 守值 pattern 一致）。純測試補強。

## 3. 改檔範圍

| # | 檔 | 類型 | 內容 |
|---|---|---|---|
| 1 | `myProgram/sales/product_parser.py` | 改 | +`_GAP_FILLER_PREFIXES` + `_strip_filler`；step 3 phonetic 前剝 filler（~+12） |
| 2 | `tests/sales/test_product_parser.py` | 改 | C2 案：我要刮樂 / 我要刮樂三張（mock phonetic 或注入）+ 回歸 我要冰紅茶 / 我要 / gibberish |
| 3 | `tests/sales/test_constants.py` | 改 | +1 行 `assert const.C2_DECISION_TIMEOUT == 6`（D1） |

## 4. Out of scope
- C1 無分隔相鄰雙數量、C3 插字 garble（需編輯距離）、C4 合音表擴充——**2026-06-15 triage 明確 defer**（投機/歧義/高成本），本 spec 不碰。
- 多重 filler（「我就是要刮樂」）、尾綴 filler——只做單一前綴剝除，足解常見「我要X」。
- phonetic 引擎本體不動（疊字去重等既有規則照用）。

## 5. 規範與參考
- 派 **sales-coder（opus）**；TDD。現 **589 測試是回歸網，全程保綠**。
- reuse：`phonetic_match`、`_PRODUCT_PHONETIC_CANDIDATES`、`_product_group`、`find_quantity_spans`、`parse_quantity`、`_remaining_gaps`。
- 小改動：可**跳 spec-reviewer**（主 agent 自驗 spec 對照），code-quality-reviewer 照跑。

## 6. 測試指令 + 預期
`python -m pytest tests/sales/`；現 589 passed + 新增全綠、0 failed。

重點案例：
- **C2**（test_product_parser，mock `product_parser.phonetic_match` 對「刮樂」回刮刮樂，或注入 to_pinyin）：我要刮樂→`[("刮刮樂", None)]`、我要刮樂三張→`[("刮刮樂", 3)]`。
- **回歸**：我要冰紅茶→`[("冰紅茶", None)]`、我要→`[]`、今天天氣很好→`[]`、既有多商品/dedup 案全綠。
- **D1**（test_constants）：`C2_DECISION_TIMEOUT == 6`。

## 7. Commit 規範
- worktree：`worktree-filler-strip`。
- 建議 2 commit：(1) `feat(nlu): parse_products gap 剝意圖前綴 filler（解 我要刮樂→刮刮樂）`；(2) `test(constants): 補 C2_DECISION_TIMEOUT 守值斷言`。
- `git add` 明列；繁中 message + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰
```
[approval] → writing-plans 出 plan → worktree → 派 sales-coder（TDD，保 589 綠）
  → code-quality-reviewer（跳 spec-reviewer，小改動）→ Iron Law → ff-merge → push → 清理
  → 收尾：watchlist.md consolidate（D1 closed / D2 未觸發 / D3 即時清通用工具 defer / D4 defer）
  → pineedtodo？否——純解析邏輯、無新依賴、無 Pi 操作（複測「我要刮樂」可併下次 demo）
```
