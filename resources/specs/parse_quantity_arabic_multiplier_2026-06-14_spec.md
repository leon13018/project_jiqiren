# Bugfix：parse_quantity 阿拉伯數字 + 中文乘數 — SDD spec

> Pi 實測（2026-06-14）發現：先前 `4c025ad` 千/萬 fix **不完整**——只修純中文路徑（一千張=1000 ✓），**arabic + 中文乘數仍壞**。根因已實證。小改動（含邏輯分支）→ 派 sales-coder、跳 spec-reviewer（主 agent 自驗）、code-quality-reviewer 照跑。
> Plan：本檔末嵌 TDD step（小改動不另開 plan）。

## 1. 背景與根因（已實證）

`parse_quantity` **阿拉伯優先**分支 `_ARABIC_DIGITS_RE.findall` 抓到阿拉伯數字即 return，**從不檢查其後的中文乘數**：
- 實證：`parse_quantity("9萬瓶")`=**9**、`("1萬")`=**1**、`("3千")`=**3**、`("9萬")`=**9**（乘數被忽略）。
- 對照（純中文，`4c025ad` 已修）：`三千`=3000、`一萬`=10000 ✓；純阿拉伯 `100瓶`=100 ✓。
- 後果（Pi transcript）：「9萬瓶」靜默加 9、「1萬」靜默加 1，**繞過超量守衛**（應 9萬=90000 → 超量 reask）。同 class bug 因先前只測純中文而在 arabic 路徑存活。

## 2. 設計核心

`parse_quantity` 在阿拉伯優先 return **之前**，先測「阿拉伯數字緊接中文乘數」：
- 新增乘數值表 `_MULTIPLIER_VALUE = {"十":10,"拾":10,"百":100,"佰":100,"千":1000,"仟":1000,"萬":10000,"万":10000}`。
- 預編譯 `_ARABIC_MULTIPLIER_RE = re.compile(r"(\d+)\s*([十拾百佰千仟萬万])")`。
- parse_quantity 開頭（阿拉伯 findall 之前）：
  ```python
  m = _ARABIC_MULTIPLIER_RE.search(text)
  if m:
      return int(m.group(1)) * _MULTIPLIER_VALUE[m.group(2)]
  ```
- 行為：`9萬`→90000、`3千`→3000、`1萬`→10000；無乘數的純阿拉伯（`100瓶`/`9`/`15瓶`）→ 不命中此分支、走既有阿拉伯邏輯不變；純中文（`三千`）→ 不含阿拉伯、走既有 compound 不變。

**行為規約**：含乘數的大數 → 實際大值 → `classify_qty` 超量(>50) → `invalid_qty_reask`「最多只能選購 N 瓶」（取代靜默小數）。

## 3. 改檔範圍

| 檔 | 類型 | 估計 |
|---|---|---|
| `myProgram/sales/nlu.py` | 改 | ~+8（`_MULTIPLIER_VALUE` + `_ARABIC_MULTIPLIER_RE` + parse_quantity 開頭分支） |
| `tests/sales/test_nlu_boundary.py` | 改 | arabic+乘數 + 回歸案例 |

## 4. Out of scope

- **混合複合精確值**（`9萬5千`→取 leading×first-multiplier=90000，非精確 95000；domain >50 必超量、reask 不受影響）。
- 數量提前（三瓶紅茶）、合音還原（醬就好）——本輪不做（另議）。
- 既有純中文 / 純阿拉伯解析不動。

## 5. 規範與參考

- 派 **sales-coder（opus）**；TDD **先寫重現 9萬→9 的 failing test 再修**（debugging Phase 4）。
- 小改動路徑：跳 spec-reviewer（主 agent 自驗 spec 對照）、code-quality-reviewer 照跑。
- reuse：`_ARABIC_DIGITS_RE`（既有）、對齊 `4c025ad` 千/萬 compound 風格。

## 6. 測試指令 + 預期

`python -m pytest tests/sales/`；現 **557 passed** + 新增全綠、0 failed。

重點案例（test_nlu_boundary）：
- `parse_quantity`：9萬瓶=90000、9萬=90000、1萬=10000、3千=3000、10萬=100000。
- **回歸**：100瓶=100、9=9、15瓶=15、0=0、三千=3000、一萬=10000、一千張=1000、五十=50、三百五十二=352。
- **整合**（test_states，已有 qty 超量路徑可參考）：qty sub-loop 答「9萬瓶」→ classify_qty 超量 → invalid_qty_reask（非靜默加 9）。

## 7. Commit 規範

- worktree：`worktree-arabic-mult`。
- 1 commit：`fix(nlu): parse_quantity 支援阿拉伯數字+中文乘數（解 9萬→9）`。
- `git add` 明列檔名；message 英文 type 前綴 + 繁中描述 + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. TDD step（嵌入；小改動）

1. **RED**：test_nlu_boundary 加 `assert parse_quantity("9萬瓶") == 90000`。跑 → FAIL（現 9）。
2. **Green**：nlu.py 加 `_MULTIPLIER_VALUE` + `_ARABIC_MULTIPLIER_RE` + parse_quantity 開頭分支。跑 → PASS。
3. **補案 + 回歸**：9萬/1萬/3千/10萬 + 回歸（100瓶/9/15瓶/0/三千/一萬/一千張/五十/三百五十二）。跑全量 → 綠。
4. **整合**：test_states qty sub-loop 「9萬瓶」→ 超量 reask。
5. **commit** + `git -C "<worktree>" branch --contains <SHA>` 驗。
