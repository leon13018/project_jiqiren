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
    ("L2 timeout 拒絕(鏈路A)", [], [None], "dialog", "L1_enter_hawk"),
    ("L2 點餐→追問→確認", [], ["冰紅茶", "一瓶", None, None, "對"], "dialog", "L4"),
    ("L2 點餐連數量", [], ["冰紅茶兩個", None, None, "對"], "dialog", "L4"),
    ("L3 結帳", [("冰紅茶", 2)], ["結帳", "1"], "dialog", "L4"),
    ("L3 取消確認流程", [("冰紅茶", 2)], ["結帳", "我想取消交易", "是"], "dialog", "L1_enter_hawk"),
    ("L4 掃碼付款", [("冰紅茶", 2)], ["s"], "l4", "L5"),
    ("L5 致謝", [("冰紅茶", 2)], [], "l5", "L1_enter_hawk"),
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
                cart=cart, think_count=0, do_action=_noop)
        if entry == "l4":
            return states.run_l4(
                speak=_noop, print_terminal=_noop, read_customer_input=reader,
                cart=cart, do_action=_noop)
        return states.run_l5(cart=cart, sleep=_noop, do_action=_noop)
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
