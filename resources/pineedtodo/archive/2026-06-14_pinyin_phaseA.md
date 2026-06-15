# Pi 端待辦 — 拼音糾錯 Phase A（pypinyin 安裝 + 閾值實測調校）

- **建立日期**：2026-06-14
- **對應提交**：`c82f64b`（phonetic 核心）+ `6375cb0`（問數量掛載）
- **簡介**：phonetic.py 用 pypinyin 取聲韻母做近音比對。本機（Windows）刻意未裝 pypinyin → graceful no-op（糾錯靜默關閉，不影響既有流程）。**Pi 端裝上 pypinyin 後拼音糾錯才真正生效**，再依實測調閾值。

---

## Step 1 — 安裝 pypinyin

pypinyin 為**純 Python**套件，piwheels 版可直接用（無 GLIBC source-build 坑）：

```bash
python3.11 -m pip install pypinyin
```

> 萬一 piwheels 版異常，fallback 走 pypi source：
> `python3.11 -m pip install --no-binary :all: --index-url https://pypi.org/simple/ pypinyin`

## Step 2 — 驗證 pypinyin 取音 + 核心糾錯

在 repo 根（`/home/pi/Desktop/project_jiqiren`）跑：

```bash
python3.11 -c "from myProgram.sales.phonetic import phonetic_match; print(phonetic_match('商品', ['一瓶','兩瓶','三瓶','四瓶','五瓶','六瓶','七瓶','八瓶','九瓶','十瓶']))"
```

**預期輸出**：`三瓶`（ASR 把「三瓶」聽成「商品」→ 平翹舌 s/sh + 前後鼻音 an/ang、in/ing 全模糊命中 → 修回）。
若印 `None` → pypinyin 沒裝成功或取音格式與預期不符（檢查 `_default_to_pinyin`）。

## Step 3 — 實機跑點餐流程驗效力 + 調閾值

跑 `python3.11 -m myProgram`，走到「請問⋯要幾瓶／張？」追問，故意讓 ASR 把數量聽成近音詞，觀察是否糾回正確數量。

**閾值調校**（`myProgram/sales/phonetic.py` 頂部常數，初值偏保守）：
- `SIMILARITY_THRESHOLD = 0.75`（太高 → 該糾的沒糾；太低 → 誤糾）。
- `AMBIGUITY_MARGIN = 0.25`（太高 → 歧義時太常放棄；太低 → 模稜兩可也硬糾）。

依實測「漏糾 / 誤糾」傾向微調這兩值（改完跑 `python -m pytest tests/sales/` 確認單元測試仍綠，再 push）。這就是 Phase A 要驗證的核心：**聲韻母模糊比對對真實台灣國語 ASR 輸出到底準不準**。效力 OK 才開 Phase B（問商品 + 合音還原）。

---

## 驗證

- `python3.11 -m pip show pypinyin` 有版本資訊 = 裝成功。
- Step 2 一行指令印 `三瓶` = 取音 + 核心糾錯在 Pi 上生效。
- 實機追問近音數量被糾回 = 整層掛載成功。

**回報**：請回報 pypinyin 是否**成功**裝上（我據此更新 `resources/requirements/raspberry_pi_setup.md`）+ 實測後想定的閾值（若有調）。失敗 / 未完成不必報。
