# NLU 全繁體化 + 「醬就好」合音 — SDD spec

> Plan（HOW，逐 list 刪除步驟）：`resources/plans/nlu_traditional_only_2026-06-13_plan.md`。

## 1. 背景與動機

STT 輸出繁體中文 → 所有簡體 keyword 是**永遠不會被語音命中的 dead weight**（早期使用者用簡體 IME 鍵盤測試時成對加的）。使用者決定全走語音、不再簡體鍵盤測試，故清除全部簡體 keyword。

**Audit 結論（已驗證）**：刪簡體對**繁體覆蓋零影響**——繁體 keyword 全保留，繁體輸入靠繁體 keyword 命中、與簡體無關；且無「純簡體孤兒語意」（每個簡體項都是某繁體項的簡體對應）。使用者「確保簡體版也有繁體版存在」的要求由此滿足，並由「繁體行為測試全綠」可驗證。

順帶：加「醬就好」（「這樣」的台灣合音 zhè-yàng→jiàng，延續剛合併的「這樣就好」CHECKOUT 修補）——**只加繁體**，與全繁體方向一致。

## 2. 設計核心與行為規約

### 2.1 刪除準則
**刪除每個「含至少一個簡體 unique 字」的 keyword 項**（如 对/确/结/账/买/这/继/续/离/红/乐/马/弃/没/错/够/题/样/别 等）。
- **保留**：純繁體項 + **繁簡同字**項（「不需要」「付款」「可以了」「我要取消」等繁簡相同，非簡體，不刪）。
- **不順手做**：繁簡同字的重複項去重（那是另一回事，Karpathy surgical——本 wave 只刪簡體）。

### 2.2 「醬就好」
`nlu.py` `_KEYWORDS_CHECKOUT` 繁體列加 `"醬就好"`（substring，cover「醬就好」「醬就好了」）。**不加簡體**。

### 2.3 測試連動（pytest 反向暴露，最可靠）
刪簡體 keyword 後跑全量 pytest，FAIL 分兩類處理：
- **簡體行為測試**（驗簡體輸入分類，如 `test_nlu_iced_tea_simplified_variants_also_classified`）→ 該功能已移除，**刪該 case**。
- **`test_constants` 類 list 內容斷言**（若斷言含簡體項）→ 更新斷言為繁體版。
- **繁體行為測試 FAIL** = 誤刪了繁體項（警訊）→ **停下回報**，不擅自改測試遷就。

## 3. 改檔範圍（高層；逐 list 精確清單見 plan）

| 檔 | 改動 |
|---|---|
| `myProgram/sales/nlu.py` | 刪簡體項（`_KEYWORDS_*` 多處）+ `_KEYWORDS_CHECKOUT` 加「醬就好」 |
| `myProgram/sales/constants/keywords.py` | 刪簡體項（18 個 list 的簡體變體 + 混合行逐字挑） |
| `tests/sales/test_nlu.py`、`test_states.py`、`test_product_parser.py`、`test_nlu_boundary.py` | 刪/改簡體測試 case（pytest 反向暴露） |

**混合行特別注意**（繁簡同一行，逐字挑簡體刪、留繁體）：
- `nlu.py` `_KEYWORDS_REJECT_STRICT_SHORT`：刪「没」「没有」，留「沒」「沒有」「沒了」「不了」
- `keywords.py` `KEYWORDS_CONFIRM_YES_STRICT_SHORT`：刪「对」，留「對」
- `keywords.py` `KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT`：刪「别」「继续」，留「別」「繼續」

## 4. Out of scope（明示不動）

拼音糾錯層（下個 wave，已設計）｜合音還原通用層（YAGNI）｜繁簡同字重複項去重（非簡體，不碰）｜CHINESE_DIGIT_MAP（全繁體+異體字，無簡體）｜任何非 keyword 邏輯。

## 5. 規範與參考

- 派 **sales-coder**（中等跨檔 refactor + 測試連動）+ **Wave 6 招防護**（dispatch.md：先列再做 / 每改完跑 pytest / commit 前自檢 / verbose / 規格衝突停 / 任何 fail 停）。
- 刪除是 destructive：**繁體測試全綠**是覆蓋零損失的硬證明；繁體測試 FAIL 必停報。

## 6. 測試指令與預期

- `python -m pytest tests/ -q` → 繁體行為測試全綠；簡體 case 移除後總數下降（移除數由 sales-coder 回報）；新增「醬就好」test 通過；0 failed。
- Pi 端：純 NLU 邏輯改動、無依賴/設定 → git pull 生效，無 pineedtodo。重測可講「醬就好」確認結帳。

## 7. Commit 規範

worktree `worktree-nlu-trad`（首 commit = spec+plan）。建議拆 2 commit：① `feat(nlu): 醬就好合音加入 CHECKOUT`（含 test）② `refactor(nlu): 移除全部簡體 keyword 與對應測試`。繁中 body + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`；`git add` 明列檔名。

## 8. 流程鳥瞰

```
spec+plan commit → sales-coder（醬就好 TDD → 刪簡體逐 list → pytest 反向處理測試）
→ Iron Law（繁體全綠 + branch verify）→ spec-reviewer → code-quality → 收尾 merge/push
```
