# STT keyterm prompting Implementation Plan

> **For agentic workers:** 由 sales-coder 逐 task 執行（RED→GREEN→commit）。Spec（WHAT）：`resources/specs/stt_keyterm_2026-06-13_spec.md`。

**Goal:** `stt.py` 連線 URL 加入 Nova-3 keyterm prompting 詞表（點餐場景 29 詞，percent-encoded），降低「三瓶→商品」這類近音誤辨識。

**Architecture:** 純連線參數——模組層新增 `KEYTERMS` 常數，`DEEPGRAM_URL` 末尾 append 各詞 `&keyterm=<quote(詞)>`；不動 `SttWorker` 任何邏輯、不動 sales/。

**Tech Stack:** Python 3.11、`urllib.parse.quote`（stdlib，頂層 import 安全）。

**工作環境提醒：** worktree `.claude/worktrees/stt-keyterm/`、branch `worktree-stt-keyterm`；測試 `python -m pytest <path> -q`；commit 後 `git branch --contains HEAD` 自驗非 main。

---

### Task 1: keyterm 詞表與 URL 編碼

**Files:**
- Modify: `myProgram/stt.py`（頂部 import 區、`_normalize_transcript` 與 `DEEPGRAM_URL` 之間、`DEEPGRAM_URL` 本身）
- Create: `tests/stt/test_keyterm.py`

- [ ] **Step 1: 寫 failing test**

`tests/stt/test_keyterm.py`：

```python
"""keyterm 詞表與 DEEPGRAM_URL 編碼測試（純模組常數，無網路無音訊）。"""
from urllib.parse import quote

from myProgram.stt import DEEPGRAM_URL, KEYTERMS


def test_every_keyterm_percent_encoded_in_url():
    # 每個詞以 percent-encoded 形式出現在 URL（中文必須 encode）
    for kt in KEYTERMS:
        assert f"keyterm={quote(kt)}" in DEEPGRAM_URL


def test_raw_chinese_not_in_url():
    # 強制 encode：裸中文不得出現在 URL（否則 websockets handshake 會壞）
    assert "三瓶" not in DEEPGRAM_URL
    assert "冰紅茶" not in DEEPGRAM_URL


def test_table_covers_critical_and_excludes_shangpin():
    assert "三瓶" in KEYTERMS          # 原始誤辨識回歸案例
    assert "冰紅茶" in KEYTERMS
    assert "刮刮樂" in KEYTERMS
    assert "商品" not in KEYTERMS       # 反例不可入清單（會反向 boost 加劇 bug）


def test_full_one_to_ten_bottles_and_sheets():
    for n in "一兩三四五六七八九十":
        assert f"{n}瓶" in KEYTERMS
        assert f"{n}張" in KEYTERMS


def test_base_params_preserved():
    # keyterm 是 append，既有參數不得被破壞
    assert "model=nova-3" in DEEPGRAM_URL
    assert "language=zh-TW" in DEEPGRAM_URL
    assert "endpointing=300" in DEEPGRAM_URL
```

- [ ] **Step 2: 跑測試確認 FAIL**

Run: `python -m pytest tests/stt/test_keyterm.py -q`
Expected: FAIL（`ImportError: cannot import name 'KEYTERMS'`）

- [ ] **Step 3: 最小實作**

`myProgram/stt.py` 頂部 import 區（在 `import threading` 之後）加：

```python
from urllib.parse import quote
```

`_normalize_transcript` 函式之後、`DEEPGRAM_URL` 之前，插入詞表常數：

```python
# Keyterm prompting 詞表（Nova-3 contextual biasing）——點餐場景高頻詞，引導模型
# 在近音模糊時偏向「清單內」的詞。解「三瓶」誤辨識為「商品」：sān-píng / shāng-pǐn
# 平翹舌＋前後鼻音雙重混淆，而「商品」不在清單、「三瓶」在 → 模型偏向正確輸出。
# 純連線參數、inference 內偏置，零額外延遲（非事後糾錯階段）。約 29 詞，遠低於
# Deepgram 500 token 上限。數量用中文數字（顧客口語＋既有 NLU 吃中文數字）。
KEYTERMS = [
    "一瓶", "兩瓶", "三瓶", "四瓶", "五瓶", "六瓶", "七瓶", "八瓶", "九瓶", "十瓶",
    "一張", "兩張", "三張", "四張", "五張", "六張", "七張", "八張", "九張", "十張",
    "冰紅茶", "紅茶", "刮刮樂",
    "結帳", "取消", "繼續", "繼續選購", "幾瓶", "幾張",
]
```

`DEEPGRAM_URL` 改為在既有固定參數後 append keyterm（surgical——保留原字串，只加 join）：

```python
DEEPGRAM_URL = (
    "wss://api.deepgram.com/v1/listen"
    "?model=nova-3&language=zh-TW&encoding=linear16&sample_rate=16000"
    "&channels=1&interim_results=true&endpointing=300&smart_format=false"
    + "".join(f"&keyterm={quote(_kt)}" for _kt in KEYTERMS)
)
```

- [ ] **Step 4: 跑測試確認 PASS**

Run: `python -m pytest tests/stt/test_keyterm.py -q`
Expected: `5 passed`

- [ ] **Step 5: 全量回歸**

Run: `python -m pytest tests/ -q`
Expected: 既有 540 + 新增 5 全綠（0 failed；DEEPGRAM_URL 變更不影響任何既有 stt 測試——它們注入 fake ws，不解析真 URL）

- [ ] **Step 6: Commit**

```bash
git add myProgram/stt.py tests/stt/test_keyterm.py
git commit -m "feat(stt): keyterm prompting 詞表偏置（解三瓶誤辨識為商品）

點餐場景 29 詞（1-10 瓶/張＋商品名＋意圖詞）percent-encoded 進 DEEPGRAM_URL；
Nova-3 contextual biasing、inference 內偏置零額外延遲。不動 SttWorker 邏輯與 sales/。

Co-Authored-By: Claude Opus <noreply@anthropic.com>"
```

---

### Task 2: 收尾自查（sales-coder handoff 前）

- [ ] `python -m pytest tests/ -q` 全量綠（截 summary 行進回報）
- [ ] `git branch --contains HEAD` 顯示 `worktree-stt-keyterm`（非 main）
- [ ] grep 自查：`grep -n "import websockets" myProgram/stt.py` 仍僅在 `_default_ws_factory` 內（頂層只多了 `urllib.parse`，未動 websockets lazy）
- [ ] 確認 `git diff` 僅動 `DEEPGRAM_URL` 區塊 + 新 import + 新常數，`SttWorker` class 零改動
- [ ] 回報 4-status + 改檔清單 + pytest summary

> 主 agent 後續（不在 sales-coder 範圍）：Iron Law 複驗 → spec/code-quality reviewers → pineedtodo（Pi 重測辨識率：同一批短句加 keyterm 前後對比）→ ff-merge → push → Pi 實測。
