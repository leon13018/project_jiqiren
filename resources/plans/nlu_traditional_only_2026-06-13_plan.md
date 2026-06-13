# NLU 全繁體化 + 醬就好 Implementation Plan

> **For agentic workers:** sales-coder 執行，**Wave 6 招防護**（先列再做 / 每 list 改完跑 pytest / commit 前自檢 / `-v --tb=short` / 規格衝突停 / 任何 fail 停）。Spec：`resources/specs/nlu_traditional_only_2026-06-13_spec.md`。

**Goal:** 移除 nlu.py + keywords.py 全部簡體 keyword（STT 繁體故為 dead weight）、連動清簡體測試；順帶加「醬就好」合音到 CHECKOUT。

**Architecture:** 純資料層 keyword 刪除。準則：**標「簡體/簡體變體」的整行/區塊 → 整刪**；**繁體行內混的個別簡體字 → 逐字挑刪**。繁體 keyword 全保留 → 繁體行為測試必全綠（覆蓋零損失硬證明）。

**定位方式：** 用「list 名 + 項內容」定位（**勿靠行號**，編輯後漂移）。每改一個 list 即 `python -m pytest tests/sales/ -q` 確認繁體未壞。

---

### Task 1: 加「醬就好」合音到 CHECKOUT（TDD）

**Files:** `tests/sales/test_nlu.py`、`myProgram/sales/nlu.py`

- [ ] **Step 1: failing test**（接在 `test_nlu_zheyang_jiu_hao_classified_as_checkout` 後）

```python
def test_nlu_jiang_jiu_hao_homophone_classified_as_checkout() -> None:
    """台灣合音：「這樣」連讀成「醬」(zhè-yàng→jiàng)，斷字不清的顧客講「醬就好/醬就好了」
    = 不追加 → 結帳。延續 test_nlu_zheyang_jiu_hao。只加繁體（STT 繁體輸出）。"""
    assert nlu.classify_intent("醬就好") == "結帳"
    assert nlu.classify_intent("醬就好了") == "結帳"
    assert nlu.classify_intent("醬就好", mode="normal") == "結帳"
```

- [ ] **Step 2: 跑見 FAIL**：`python -m pytest tests/sales/test_nlu.py::test_nlu_jiang_jiu_hao_homophone_classified_as_checkout -q` → FAIL（「醬就好」現為無法判斷）
- [ ] **Step 3: 加 keyword**：`nlu.py` `_KEYWORDS_CHECKOUT` 繁體列（含「就這樣」「這樣就好」那行）加 `"醬就好"`。**只加繁體列，不加簡體列**（簡體列下一個 task 整個刪）。
- [ ] **Step 4: 跑見 PASS**：同 Step 2 指令 → PASS
- [ ] **Step 5: commit**：`git add myProgram/sales/nlu.py tests/sales/test_nlu.py` → `feat(nlu): 醬就好合音加入 CHECKOUT（這樣→醬連讀）`

---

### Task 2: 刪 nlu.py 簡體 keyword

**File:** `myProgram/sales/nlu.py`。逐 list 刪除（改完跑 `pytest tests/sales/ -q`）：

| list | 動作 |
|---|---|
| `_KEYWORDS_CROSS_L_CANCEL` | 整刪簡體行 `"取消这次交易", "退出这次交易",` |
| `_KEYWORDS_REJECT` | 整刪簡體行 `"不买", "不想买", "不买了",` 與 `"没有额外",`（繁體「沒有額外」保留） |
| `_KEYWORDS_REJECT_STRICT_SHORT` | **混合行逐字**：`["沒", "没", "沒有", "沒了", "不了", "没有"]` → `["沒", "沒有", "沒了", "不了"]`（刪「没」「没有」） |
| `_KEYWORDS_REJECT_L3_STRICT` | 整刪兩簡體行 `"整单取消", "不想买了", "取消购买", "不买了",` 與 `"不要买了", "不想买",` |
| `_KEYWORDS_CHECKOUT` | 整刪簡體行 `"结账", "买单", "付款", "就这样", "这样就好", "可以了", "没了", "没有了", "够了", "没事", "没问题",` |

- [ ] 逐 list 刪 → 每 list 後跑 `pytest tests/sales/ -q`，**繁體測試 FAIL 即停報**（誤刪繁體警訊）
- [ ] 全 list 完成後跑全量確認

---

### Task 3: 刪 keywords.py 簡體 keyword

**File:** `myProgram/sales/constants/keywords.py`。逐 list：

| list | 動作 |
|---|---|
| `KEYWORDS_CONFIRM_YES` | 整刪簡體區塊三行（`"对的"…"正确"` / `"对哦", "对呢", "对啊"` / `"结账", "买单", "付款"`） |
| `KEYWORDS_CONFIRM_YES_STRICT_SHORT` | **混合逐字**：`["好","是","對","对","嗯","ok","y"]` → 刪「对」 |
| `KEYWORDS_CONFIRM_NO` | 整刪簡體行 `"不对", "不正确", "不是", "不行", "不要", "不用", "重来", "重新",` |
| `KEYWORDS_C2_CONTINUE` | 整刪簡體行 `"继续选购", "继续购买", "继续买", "再买", "再加",` |
| `KEYWORDS_C2_CANCEL` | 整刪簡體行 `"取消购买", "我要取消", "想取消", "我想取消", "不想要了",` |
| `KEYWORDS_L4_ACK_OR_WAIT` | 整刪簡體行 `"没问题", "没事", "稍等", "等一下", "马上", "来了", "找一下",` |
| `KEYWORDS_WANT_TO_BUY_VAGUE` | 整刪簡體行 `"想买", "还要", "还想", "想加买",` 與 `"好了", "对了",`（繁體「好了」「對了」保留在繁體行） |
| `KEYWORDS_ICED_TEA` | **混合逐字**：刪「红茶」「冰红茶」（留「紅茶」「冰紅茶」「hong cha」「iced tea」「black tea」） |
| `KEYWORDS_SCRATCH` | **混合逐字**：刪「刮刮乐」「乐透」「即时乐」（留繁體 + 「彩券」「彩卷」「lottery」「scratch」） |
| `KEYWORDS_CANCEL_CONFIRM_YES` | 整刪簡體行 `"我想取消", "取消这次", "取消这次交易", "取消交易",`（繁體「取消交易」保留在繁體行） |
| `KEYWORDS_CANCEL_CONFIRM_NO` | 整刪簡體行 `"不要取消", "不想取消", "别取消",` 與 `"继续交易", "我想继续交易",` |
| `KEYWORDS_CANCEL_CONFIRM_NO_STRICT_SHORT` | **混合逐字**：刪「别」「继续」（留「別」「繼續」） |
| `KEYWORDS_INVALID_QTY_CANCEL_TRIGGER` | 整刪簡體行 `"不买", "不买了", "不想买", "不想要了", "放弃",` |
| `KEYWORDS_INVALID_QTY_CONTINUE` | 整刪簡體行 `"继续交易", "继续",` |
| `KEYWORDS_INVALID_QTY_EXIT` | **混合逐字**：刪「离开」（留「離開」） |

> 註：`KEYWORDS_CONFIRM_NO_STRICT_SHORT`（`["no","nope","n","否","錯","錯誤","不"]`）、`CHINESE_DIGIT_MAP` 無簡體，不動。註解內提到「簡體」的說明文字保留（不是 keyword）。

- [ ] 逐 list 刪 → 每 list 後 `pytest tests/sales/ -q`，繁體 FAIL 即停報

---

### Task 4: 連動處理簡體測試（pytest 反向暴露）

**Files:** `tests/sales/`（test_nlu.py / test_states.py / test_product_parser.py / test_nlu_boundary.py）

- [ ] **Step 1**：跑全量 `python -m pytest tests/ -v --tb=short`，列出所有 FAIL
- [ ] **Step 2**：逐一分類處理：
  - 驗**簡體輸入分類**的 case（如 `test_nlu_iced_tea_simplified_variants_also_classified`、product_parser 簡體案例）→ 功能已移除，**刪該 case**（或移除其中簡體 assert，保留繁體 assert）
  - **`test_constants` 類**斷言 list 含簡體項 → 更新斷言為繁體版
  - **繁體 case FAIL** → 誤刪繁體警訊，**停下回報**，不改測試遷就
- [ ] **Step 3**：全量 `python -m pytest tests/ -q` 全綠
- [ ] **Step 4: commit**：`git add` 明列所有改動檔 → `refactor(nlu): 移除全部簡體 keyword 與對應測試`

---

### Task 5: handoff 自查

- [ ] `python -m pytest tests/ -q` 全綠（截 summary 回報移除前後測試數）
- [ ] `git branch --contains HEAD` = `worktree-nlu-trad`（非 main）
- [ ] grep 自查殘留：`grep -nE '对|确|结|账|买|这|继|续|离|红|乐|马|弃|没错|够|题|样|别|刮刮乐' myProgram/sales/nlu.py myProgram/sales/constants/keywords.py` → 僅應命中註解說明文字，**keyword list 內零簡體**（混合行的「没」「对」「别」「继续」「红茶」等已挑除）
- [ ] 回報 4-status + 改檔清單 + 各 commit SHA + pytest summary + grep 自查結果
