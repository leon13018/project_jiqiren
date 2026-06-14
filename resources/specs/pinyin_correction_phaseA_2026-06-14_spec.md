# 拼音近音糾錯 Phase A — SDD spec（phonetic.py 核心 + 問數量掛載）

> 統領設計：[pinyin_correction_2026-06-13_design.md](pinyin_correction_2026-06-13_design.md)。本 spec 實作其 §5 Phase A。
> Plan（HOW / step-by-step）：[../plans/pinyin_correction_phaseA_2026-06-14_plan.md](../plans/pinyin_correction_phaseA_2026-06-14_plan.md)。
> **範圍對齊（2026-06-14 user）**：精實對齊掛載——只做問數量 wiring 真正 exercise 的「聲韻母模糊比對 + 歧義安全閥 + pypinyin 注入 seam」。**疊字去重 / 介音等價 / 不同字數子串規則延 Phase B**（它們只服務問商品 context，Phase A 在 Pi 上無法驗證）。

## 1. 背景與動機

統領設計定案本地拼音糾錯層（Deepgram keyterm 對中文 streaming 無效後 pivot）。Phase A 先單點驗證**整層成敗關鍵**：聲韻母模糊比對對真實台灣國語 ASR 輸出到底準不準。

**Pi 實測痛點（問數量 context）**：系統問「請問⋯要幾瓶？」顧客答「三瓶」(sān-píng)，雲端 ASR 因**平翹舌（s/sh）＋前後鼻音（an/ang、in/ing）雙重混淆**聽成「商品」(shāng-pǐn)。現況：`商品` 無數字 → `has_quantity` False → `classify_intent` 回「無法判斷」→ `attempts++` reprompt，顧客被迫重講、體驗差。

**可兜底的本質**：問數量時**合法詞域極小**（`{一瓶…十瓶}` 或 `{一張…十張}`，依商品單位）。雲端 ASR 對「短中文詞 + 系統性混淆」不可靠，但我們握有 context — 用本地拼音比對在 NLU 放棄出口兜底。

## 2. 設計核心 + 行為規約

### 2.1 新檔 `myProgram/sales/phonetic.py` — `phonetic_match`

簽名：`phonetic_match(text: str, candidates: list[str], *, to_pinyin=None) -> str | None`

行為（依序）：
1. **守衛**：`text` 為空或 `candidates` 為空 → 回 `None`。
2. `to_pinyin` 為 `None` → 用 `_default_to_pinyin`（production lazy import pypinyin）。
3. 取 `text` 與每個 candidate 的逐字 `(聲母, 韻母)`。**pypinyin 不可用時（如 Windows 未裝）→ 整體回 `None`**（graceful no-op：糾錯層缺依賴時靜默退回 caller 既有 reprompt，**既有測試零衝擊**）。實作：步驟 3 的取音包在 `try/except ImportError` 內，命中即回 `None`。
4. 逐 candidate 算**相似度**：
   - 逐位比對 `i ∈ range(min(len(text), len(cand)))`：`_syllable_equiv` 命中計 1。
   - `similarity = 命中數 / max(len(text), len(cand))`（**長度不等自然降分，無需子串特例**）。
5. 取 similarity 的 top-1、top-2（僅 1 個 candidate 時 top-2 視為 `0.0`）。
6. **歧義安全閥**：`top1 ≥ SIMILARITY_THRESHOLD` **且** `(top1 − top2) ≥ AMBIGUITY_MARGIN` → 回 top-1 的 candidate 原字串；否則 `None`。

**音節模糊等價** `_syllable_equiv((i1,f1),(i2,f2))`：
`_canon_initial(i1)==_canon_initial(i2) and _canon_final(f1)==_canon_final(f2)`
- 聲母正規化 `_INITIAL_EQUIV`（平翹舌＋常見混淆）：`sh→s`、`ch→c`、`zh→z`、`l→n`、`h→f`；其餘原樣。
- 韻母正規化 `_FINAL_EQUIV`（前後鼻音）：`ing→in`、`eng→en`、`ang→an`；其餘原樣。
- 介音脫落（`ua/a`、`uo/o`、`ie/e`）**不含 → Phase B**。

**閾值常數**（named module 常數，初值供 Pi 實測調校，**禁 inline 寫死神奇數字**）：
- `SIMILARITY_THRESHOLD = 0.75`（初值；2 音節候選須兩字皆模糊命中才達標，Phase A 偏保守避免誤糾）。
- `AMBIGUITY_MARGIN = 0.25`（初值；top-1 須明顯勝 top-2 才修正，否則退回 reprompt）。
- 兩常數註明「Pi 實測調校」。

`_default_to_pinyin(char) -> tuple[str, str]`：lazy `import pypinyin`，`Style.INITIALS` 取聲母、`Style.FINALS` 取韻母（`strict=False` 處理零聲母 y/w）；回 `(聲母, 韻母)`。**頂層禁 import pypinyin**（紅線：Windows 未裝，只能 lazy 在函式內）。

### 2.2 掛載 `myProgram/sales/states/_l2_l3_qty_followup.py`（問數量 sub-loop）

- 新增 module 級 `_QTY_NUMBER_WORDS = ("一","兩","三","四","五","六","七","八","九","十")`：一個量值一個 canonical 口語詞（2 用「兩」），**保歧義閥有效**（避免同義候選互相壓低 margin）。
- 抽 helper `_apply_resolved_qty(qty, product, unit, cart, io) -> tuple[bool, str|None, str|None]`：把「已得 int `qty` → `classify_qty` → `at_cap` / 無效（`invalid_qty_reask` + control 冒泡）/ `ok`（`add_item`）」邏輯**單一來源化**。現有 `has_quantity` 分支與新 phonetic 分支共用，消除重複。
- `has_quantity` 分支改呼叫 `_apply_resolved_qty`（純重構，行為不變）。
- **「其他 bucket」插入**（客服 / 拒絕 / 結帳 三判定**之後**、`attempts++` **之前**）：
  ```python
  candidates = [w + unit for w in _QTY_NUMBER_WORDS]
  corrected = phonetic_match(follow_up, candidates)
  if corrected is not None:
      return _apply_resolved_qty(parse_quantity(corrected), product, unit, cart, io)
  ```
  `corrected is None`（含 Windows 無 pypinyin、歧義、無夠近）→ 落回既有 `attempts++` / reprompt。

**行為規約**：
- 糾錯只在問數量放棄出口觸發；客服 / 拒絕 / 結帳 已先判定，**不被糾錯劫持**。
- 修正後數量走與顧客直接報數**完全相同**的 `classify_qty` / `at_cap` / `invalid_qty_reask` / `add_item` 路徑（含超量重問鏈 control 冒泡）。
- 失敗一律回 `None` → **最壞＝現狀（reprompt），不劣化**。

## 3. 改檔範圍（高層；step-by-step 見 plan）

| # | 檔 | 類型 | 估計 |
|---|---|---|---|
| 1 | `myProgram/sales/phonetic.py` | **新增** | ~90–110 行（`phonetic_match` + `_default_to_pinyin` + `_syllable_equiv` + `_canon_initial/_canon_final` + 等價表 + 閾值常數） |
| 2 | `myProgram/sales/states/_l2_l3_qty_followup.py` | 改 | ~+30 / −10（import + `_QTY_NUMBER_WORDS` + 抽 `_apply_resolved_qty` + has_quantity 分支改用 + 其他 bucket 插 phonetic） |
| 3 | `tests/sales/test_phonetic.py` | **新增** | `phonetic_match` 單元測試（注入 fake `to_pinyin`） |
| 4 | `tests/sales/test_states.py` | 改 | qty sub-loop phonetic 掛載整合測試（mock `phonetic_match` 驗 wiring；含「None → 既有 reprompt 不變」回歸） |

## 4. Out of scope（明示不動）

- **問商品掛載、合音還原、疊字去重、介音等價、不同字數子串規則** → 皆 Phase B。
- 既有 NLU 正常解析路徑（`has_quantity` 真命中、`classify_intent` 命中客服 / 拒絕 / 結帳）**零改動**。
- confirm / 錢包敏感 context 不碰。
- 閾值 / margin **最終值**（Pi 實測調，Phase A 只給初值 + seam）。
- pypinyin **安裝**（Pi 端 pineedtodo，非本 spec 的 code）。

## 5. 規範與參考

- 派 **sales-coder（opus）**；karpathy-guidelines + TDD skill 由 frontmatter 自動預載，派發 prompt 不複寫。
- 統領設計 §2.2 / §3 / §4 / §5 為權威；本 spec 為其 Phase A 切片。
- **既有可 reuse**：`cart_module.classify_qty` / `add_item`、`invalid_qty_reask`、`nlu.parse_quantity` / `has_quantity`、`PRODUCTS[product]["單位"]`、`AT_CAP_NOTICE_TEMPLATE`。
- `to_pinyin` seam 對齊既有 DI 風格（speak / read 等 callback 注入精神一致）。

## 6. 測試指令 + 預期結果

指令：`python -m pytest tests/sales/`
預期：現 **504 passed** + 新增測試全綠，**總數 > 504、0 failed**。

重點案例（注入 fake `to_pinyin`，不碰真 pypinyin）：
- **核心**：`phonetic_match("商品", ["三瓶","一瓶",…,"十瓶"], to_pinyin=fake)` → `"三瓶"`。
- 歧義（兩候選並列高分）→ `None`；無夠近（皆低於閾值）→ `None`。
- 聲母平翹舌等價（s/sh、z/zh…）、韻母前後鼻音等價（in/ing、an/ang、en/eng）各 1 案。
- 空 `text` / 空 `candidates` → `None`；完全相同 → 命中；長度不等 → 降分至 `None`。
- graceful：`to_pinyin=None` 且 pypinyin 不可用 → `None`（Windows）。
- **wiring**：mock `phonetic_match` 回 `"三瓶"` → 問數量 sub-loop 顧客答「商品」→ cart 得該商品 ×3；mock 回 `None` → 既有 reprompt / attempts 行為**不變**；mock 回超量詞 → 走 `invalid_qty_reask`。

## 7. Commit 規範

- worktree：`worktree-pinyin-phase-a`（approval 後建立）。
- 建議拆 2 commit（TDD 先 test 後 prod，可再細分）：
  1. `feat(phonetic): 新增拼音近音比對核心` — `phonetic.py` + `test_phonetic.py`。
  2. `feat(nlu): 問數量 sub-loop 掛載拼音糾錯` — `_l2_l3_qty_followup.py` + `test_states.py` 新案例。
- `git add` **明列檔名**（禁 `-A` / `.`）。
- message：英文簡短標題 + 繁中 body + `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
[本 spec/plan approval]
  → EnterWorktree(pinyin-phase-a) → commit spec/plan（worktree 首 commit）
  → 派 sales-coder（TDD：phonetic.py 核心 → qty 掛載）
  → 3 段審（spec-reviewer → code-quality-reviewer）→ Iron Law（pytest 全綠 + branch verify）
  → ff-merge main → push（Stop hook sync Pi）→ worktree 清理
  → Pi 端 pip install pypinyin（pineedtodo）→ 實測調 SIMILARITY_THRESHOLD / AMBIGUITY_MARGIN
  → 算法效力 OK → Phase B（問商品 + 合音還原 + 疊字/介音/子串）
```
