# perf campaign Phase 0＋1 執行計畫（plan — HOW）

> **對應傘狀設計**：`resources/specs/perf_review_2026-06-12_design.md` §4–§5。
> **執行者**：Task 1 派 sales-coder（worktree `worktree-perf-phase0`）；Task 0 / 2–5 主 agent。
> 本 plan 不改任何 prod code（`myProgram/**` 零變動）——Phase 0 只加 `tests/perf/`，Phase 1 只讀＋產 `resources/reviews/` 文件。

**Goal**：建立可重複的效能基線（micro 熱函式 / scenario 對話劇本 / import 冷啟動）＋四鏡頭全面 review 產出 findings 報告，供 Phase 2 裁決。

---

## Task 0：基線驗證（主 agent）

- [ ] **Step 0.1**：`python -m pytest tests/sales/` → 預期 `504 passed`。

---

## Task 1：bench 腳本（EnterWorktree ＋ 派 sales-coder）

**Files**：Create `tests/perf/__init__.py`（空檔）、Create `tests/perf/bench_sales.py`

> 主 agent 先 `EnterWorktree worktree-perf-phase0`，再派 sales-coder（prompt 給本 plan 路徑＋傘狀設計路徑）。
> 非 SDD 三段迴圈案（純 tests/ 新增、零 prod 改動）：sales-coder 完成後主 agent Iron Law 自驗即收尾，不派 reviewer。

- [ ] **Step 1.1**：建 `tests/perf/__init__.py`（空檔，讓 `python -m tests.perf.bench_sales` 可跑）。

- [ ] **Step 1.2**：建 `tests/perf/bench_sales.py`，完整內容：

```python
"""效能基線量測腳本（perf campaign Phase 0）。

量測對象（Windows 可跑，sales 純邏輯，不碰 vendor / edge-tts）：
    1. micro：每輪輸入都會跑的熱路徑純函式（nlu / product_parser）
    2. scenario：完整對話劇本走 run_dialog / run_l4 / run_l5
       （fake-IO 即時回覆 → 量純計算耗時，無真實等待；劇本皆取自
       tests/sales/test_states.py 既有已知可走通序列）
    3. import：子行程冷啟動 import myProgram.sales（扣除直譯器啟動基線）

用法（repo root）：
    python -m tests.perf.bench_sales          # smoke ＋ 全部量測
    python -m tests.perf.bench_sales --smoke  # 只驗劇本走向
輸出 stdout markdown 表，貼進 resources/reviews/ 基線 / 對比文件。

注意：
    - 非 pytest 測試（pytest.ini testpaths=tests/sales 不會收集本目錄）。
    - scenario 計時區含 fresh cart ＋ stub 重建（sub-µs 級、前後對比同含，
      不影響差值有效性）。
    - L4 場景只用即時退出路徑（"s" 掃碼）——L4 雙計時器是真 wall-clock
      （time.monotonic），timeout 路徑會空轉真實秒數，禁用。
"""

import gc
import statistics
import subprocess
import sys
import time

from myProgram.sales import cart as cart_module
from myProgram.sales import nlu, product_parser, states


# ============================================================
# fake-IO stub（同 tests/sales/test_states.py 駕駛模式）
# ============================================================

class FakeCustomerInput:
    """顧客輸入序列 stub：str = 回應、None = timeout；不實際等待。"""

    def __init__(self, sequence):
        self._seq = list(sequence)

    def read(self, timeout):
        if not self._seq:
            return None
        return self._seq.pop(0)


def _noop(*args, **kwargs):
    return None


# ============================================================
# 量測核心
# ============================================================

def _sample(fn, reps, warmup):
    """跑 fn reps 次回傳每次耗時（秒）list；前 warmup 次不計；取樣期間關 gc。"""
    for _ in range(warmup):
        fn()
    samples = []
    gc.disable()
    try:
        for _ in range(reps):
            t0 = time.perf_counter()
            fn()
            samples.append(time.perf_counter() - t0)
    finally:
        gc.enable()
    return samples


def _report(title, rows):
    print(f"\n### {title}\n")
    print("| 項目 | 中位數 (µs) | P95 (µs) | reps |")
    print("|---|---:|---:|---:|")
    for name, samples in rows:
        med = statistics.median(samples) * 1_000_000
        p95 = sorted(samples)[int(len(samples) * 0.95) - 1] * 1_000_000
        print(f"| {name} | {med:.1f} | {p95:.1f} | {len(samples)} |")


# ============================================================
# 1. micro：熱路徑純函式
# ============================================================

MICRO_REPS = 2000
MICRO_WARMUP = 100

MICRO_CASES = [
    ("normalize_input", lambda: nlu.normalize_input("我要兩瓶冰紅茶，謝謝")),
    ("classify_intent(l2 商品)", lambda: nlu.classify_intent("我要兩瓶冰紅茶", mode="l2")),
    ("classify_intent(normal 商品)", lambda: nlu.classify_intent("我要兩瓶冰紅茶")),
    ("classify_intent(拒絕)", lambda: nlu.classify_intent("不用了謝謝")),
    ("classify_intent(無命中)", lambda: nlu.classify_intent("今天天氣真好啊")),
    ("has_quantity", lambda: nlu.has_quantity("三十五瓶冰紅茶")),
    ("parse_quantity(複合中文)", lambda: nlu.parse_quantity("三十五瓶")),
    ("parse_products(雙商品)", lambda: product_parser.parse_products("兩瓶冰紅茶和三張刮刮樂")),
    ("parse_products(無命中)", lambda: product_parser.parse_products("今天天氣真好啊")),
]


# ============================================================
# 2. scenario：完整對話劇本
# ============================================================

SCENARIO_REPS = 200
SCENARIO_WARMUP = 10

# (名稱, cart 預置 [(商品, 數量)], 劇本, 進入點, 預期 next_state)
SCENARIOS = [
    ("L2 timeout 拒絕(鏈路A)", [], [None], "dialog", "L1_via_subroutine_a"),
    ("L2 點餐→追問→確認", [], ["冰紅茶", "一瓶", None, None, "對"], "dialog", "L4"),
    ("L2 點餐連數量", [], ["冰紅茶兩個", None, None, "對"], "dialog", "L4"),
    ("L3 結帳", [("冰紅茶", 2)], ["結帳", "1"], "dialog", "L4"),
    ("L3 取消確認流程", [("冰紅茶", 2)], ["結帳", "我想取消交易", "是"], "dialog", "L1_via_subroutine_a"),
    ("L4 掃碼付款", [("冰紅茶", 2)], ["s"], "l4", "L5"),
    ("L5 致謝", [("冰紅茶", 2)], [], "l5", "L1_via_subroutine_a"),
]


def _make_scenario_run(pre_cart, script, entry):
    def run():
        cart = cart_module.new_cart()
        for product, qty in pre_cart:
            cart_module.add_item(cart, product, qty)
        reader = FakeCustomerInput(script).read
        if entry == "dialog":
            return states.run_dialog(
                speak=_noop, print_terminal=_noop, read_customer_input=reader,
                cart=cart, think_count=0, opencv_disable=_noop, do_action=_noop)
        if entry == "l4":
            return states.run_l4(
                speak=_noop, print_terminal=_noop, read_customer_input=reader,
                cart=cart, opencv_disable=_noop, do_action=_noop)
        return states.run_l5(speak=_noop, cart=cart, sleep=_noop, do_action=_noop)
    return run


def _smoke():
    """每場景跑一次驗走向——劇本失效（assert 爆）時不得進量測。"""
    for name, pre_cart, script, entry, expected in SCENARIOS:
        result = _make_scenario_run(pre_cart, script, entry)()
        state = result[0] if isinstance(result, tuple) else result
        assert state == expected, (
            f"{name}: 劇本走向 {state!r} ≠ 預期 {expected!r}"
            f"（劇本失效，回查 tests/sales/test_states.py 既有序列替換）"
        )
    print(f"smoke：{len(SCENARIOS)} 場景走向全數符合預期")


# ============================================================
# 3. import 冷啟動
# ============================================================

def _bench_import(reps=5):
    def once(code):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)
        return time.perf_counter() - t0
    interp = statistics.median([once("pass") for _ in range(reps)])
    full = statistics.median([once("import myProgram.sales") for _ in range(reps)])
    print("\n### import 冷啟動\n")
    print("| 項目 | 中位數 (ms) |")
    print("|---|---:|")
    print(f"| 直譯器基線 | {interp * 1000:.0f} |")
    print(f"| import myProgram.sales（扣基線） | {(full - interp) * 1000:.0f} |")


def main():
    print("# perf bench（sales 純邏輯）")
    print(f"- Python {sys.version.split()[0]} / platform {sys.platform}")
    _smoke()
    if "--smoke" in sys.argv:
        return
    _report("micro：熱路徑純函式",
            [(name, _sample(fn, MICRO_REPS, MICRO_WARMUP)) for name, fn in MICRO_CASES])
    _report("scenario：對話劇本",
            [(name, _sample(_make_scenario_run(pre, script, entry), SCENARIO_REPS, SCENARIO_WARMUP))
             for name, pre, script, entry, _ in SCENARIOS])
    _bench_import()


if __name__ == "__main__":
    main()
```

- [ ] **Step 1.3**：`python -m tests.perf.bench_sales --smoke` → 預期 `smoke：7 場景走向全數符合預期`。
  若某場景 assert 爆：該劇本與假設的 cart 預置不合 → 從 `tests/sales/test_states.py` 找同路徑的既有可走通序列替換（**只准用既有測試出現過的序列**），回報列出替換內容。
- [ ] **Step 1.4**：`python -m tests.perf.bench_sales` → 三區 markdown 表正常輸出、無例外。
- [ ] **Step 1.5**：`python -m pytest tests/sales/` → `504 passed`（bench 不在 testpaths，確認零收集污染）。
- [ ] **Step 1.6**：

```bash
git add tests/perf/__init__.py tests/perf/bench_sales.py
git commit -m "test(perf): add sales benchmark baseline script (phase 0)"
git branch --contains HEAD
```

**主 agent 收尾**：Iron Law 自驗（自跑 Step 1.3–1.5 三指令＋branch verify）→ `ExitWorktree(keep)` → `git merge worktree-perf-phase0 --ff-only` → `git push origin main` → worktree remove ＋ branch -d。

---

## Task 2：跑基線＋寫報告（主 agent）

- [ ] **Step 2.1**：`python -m tests.perf.bench_sales` 連跑 3 輪，確認各項中位數輪間漂移 < 10%（噪音閾值內）。
- [ ] **Step 2.2**：建 `resources/reviews/perf_baseline_2026-06-12.md`：環境（CPU / Python 版本 / Windows）＋三區表（取 3 輪中間值那輪）＋輪間漂移觀察。標注「Pi 端絕對值會不同；本基線只供同機前後對比」。
- [ ] **Step 2.3**：

```bash
git add resources/reviews/perf_baseline_2026-06-12.md
git commit -m "docs(reviews): perf baseline on Windows (phase 0)"
git push origin main
```

---

## Task 3：已處理項摘要（主 agent，彙整進派發 prompt）

派發 reviewer 時複製以下區塊（防重提已做過的項目）：

```
## 近兩輪 campaign 已處理項（勿重提）
- oop W1–W6（2026-06-10 教科書 OOP 重構）：KeywordGroup 雙集封裝（contains_any+equals_strict_short 合併）；
  DialogIO callback 束（8 處 speak fallback 三元式收斂、私有函式收 io 一參）；TimedConfirm(ABC) Template
  Method 收 cancel/service/invalid_qty 三 confirm 家族；ModePolicy(Strategy)+DialogSession 統一意圖分派
  （收 L2/L3 三胞胎＋think_silence 雙胞胎）；State pattern+SalesMachine（logic.run 變 facade、Transition
  取代魔法 tuple）；QueueWorker(ABC) 收 tts/action worker＋TerminalSim＋_tick_countdown＋drain_queue。
- quality_fix w1–w4（2026-06-11）：dialog dispatch 主迴圈/inner 語境統一；tts speak_and_wait 委派 speak；
  unclear final confirmation reuse 單一 DialogSession；刪死碼（L4 pause 量測、run_l1 直回）；
  cart.remaining_capacity 收 5 處 inline 計算；AT_CAP_NOTICE_TEMPLATE 抽常數；tts play-stage 失敗處理
  try/finally 收斂；_match_tens 抽取；nlu REJECT KeywordGroup 化＋cross-L cancel 共享清單；
  刪 no-op INVALID_QTY strict_short 子集；L4 fresh-deadlines/pay-success helper。
- 既知刻意決策（勿當 finding）：invalid_qty_reask 主迴圈與 _dialog_c2_second_stage 不入 TimedConfirm
  （reset 鏈/重入主迴圈）；InputReader 不繼承 QueueWorker（producer 形狀）；cart/nlu/product_parser
  維持純函式；QueueWorker 無 except-all（保留現狀行為）；shutdown 不入基底（兩 worker 順序相反）。
```

---

## Task 4：派發四鏡頭 reviewer（主 agent，單訊息 4 個 Agent 並行）

**共用 prompt 模板**（`<鏡頭名>` / `<範圍>` / `<焦點>` 按下表代入；`general-purpose` ＋ `model: "opus"`）：

```
## 任務（只讀不改）
對 myProgram/（vendor/ 除外）做「<鏡頭名>」效能/品質 review。
絕對不編輯任何檔案、不 commit；只用 Read/Grep/Glob。

## 系統背景
- Raspberry Pi 4 規則匹配點餐/收款機器人；終端文字輸入模擬語音、edge-tts 雲端合成、
  廠商動作組。輸入頻率 = 人類對話節奏（每輪一句）。
- 行為 100% 不變是硬約束（文案/計時值/狀態轉換不可動）；你找的是「不變行為下的更快/更簡潔」。
- 治理原則：熱路徑（每輪輸入都跑：NLU 匹配/解析/狀態分派）效能優先、只接受零成本抽象
  （預編譯/查表/模組級常數）；冷路徑（啟動/一次性建構）簡潔結構優先（OOP/泛型盡量上）。
- 目錄/檔名可大改（user 已授權極大化重構），結構建議不必保守。

<Task 3 已處理項摘要區塊>

## 鏡頭範圍與焦點
<範圍>
<焦點>

## 輸出格式（最終回覆 = 純 findings 清單，不要敘事）
每條：
[P0|P1|P2 - hot|cold] <檔>:<行> — <問題一句>
  證據：<code 片段或行為描述>
  建議修法：<具體>
  預估收益：<量級與依據>
  風險：低/中/高＋一句
  建議波次：搬遷/合併/熱點/sweep
P0=高收益高確定性、P1=中、P2=低收益或高風險。低收益也要列（標 P2），但無 finding 的面向
誠實寫「無」，不硬湊。
```

**四鏡頭參數**：

| 鏡頭 | `<範圍>` | `<焦點>` |
|---|---|---|
| ① 熱路徑效能 | `myProgram/sales/nlu.py`、`product_parser.py`、`keyword_group.py`、`constants/keywords.py`、`cart.py`、`states/l2_l3_dialog.py`（DialogSession 分派核心）、`states/machine.py` | 每呼叫重建可預編譯的結構（regex/list/dict/tuple）、同一輸入被多 keyword 集重複線性掃描、可查表化的 if-elif 鏈、可 frozenset/set 化的 `in` 檢查、可 lru_cache 的純函數、重複 normalize、字串重複切片/正規化 |
| ② 阻塞與排程 | `myProgram/tts.py`、`action.py`、`input_reader.py`、`queue_worker.py`、`main.py` | 感知延遲：TTS 合成→播放可否 pipeline/prefetch（邊合成邊播）、queue 交接多餘等待、輪詢 sleep 間隔過粗、不必要的 join/lock 持有範圍、worker 啟動順序。約束：計時倒數語義不變；本鏡頭 findings 屬靜態分析（Windows 跑不了），實作驗證須標注「Pi 端驗證」 |
| ③ 重複邏輯與抽象 | `myProgram/sales/states/` 全部、`constants/*_text.py`、`constants/timing.py`、`constants/shared.py` | oop/quality_fix 兩輪後仍殘留的相似流程（reask 家族 vs confirm 家族邊界、`_l2_l3_qty_followup` vs `_invalid_qty_reask` 結構相似度）、可參數化的重複文案組裝、可泛化的 pattern；每條標注合併點落不落熱路徑（落 → 只准零成本抽象） |
| ④ 架構結構 | `myProgram/` 全目錄（vendor 除外）＋ `tests/` 對應結構 | 目錄/檔名是否反映職責、模組邊界與依賴方向、constants 七檔拆分合理性、`states/__init__.py` 匯出面、底線前綴檔命名一致性、main.py wire-up 簡化空間；**若支持大搬遷 → 給目標目錄樹 before/after ＋ 檔名對映表 ＋ tests import 影響清單** |

- [ ] **Step 4.1**：組四份 prompt（模板＋參數＋Task 3 摘要），單訊息發 4 個 Agent。
- [ ] **Step 4.2**：收齊四份 findings；任一 reviewer 失敗 / 回空 → 同 prompt 重派一次。

---

## Task 5：彙整報告＋裁決 gate（主 agent）

- [ ] **Step 5.1**：去重（同 finding 多鏡頭命中 → 合併保留最強證據）＋衝突調解（③加抽象 vs ①去間接層 → 按治理原則裁：熱路徑效能贏）＋主 agent 抽查可疑 findings（Read 原檔驗證 file:line 與證據屬實，防 reviewer 幻覺）。
- [ ] **Step 5.2**：建 `resources/reviews/full_review_2026-06-12.md`：
  - 開頭 summary 表：finding 總數、P0/P1/P2 分布、四鏡頭各自貢獻、建議波次分組。
  - 主體：依建議波次分組的 findings 全文（含被去重合併的記錄）。
  - 結尾：「建議裁決選項」段（全採 / 只採 P0+P1 / 逐項勾選）。
- [ ] **Step 5.3**：

```bash
git add resources/reviews/full_review_2026-06-12.md
git commit -m "docs(reviews): four-lens full perf review findings (phase 1)"
git push origin main
```

- [ ] **Step 5.4**：PushNotification（「findings 報告完成，N 條待裁決」）→ 等 user 裁決 → 進 Phase 2（波次規劃，逐波另立 spec/plan）。

---

## 完成定義

- [ ] bench 腳本進 main、smoke 7 場景過、pytest `504 passed` 不變。
- [ ] 基線報告＋findings 報告進 main。
- [ ] user 已收到裁決請求通知。Phase 2 之後的波次 spec/plan **不在本 plan 範圍**。
