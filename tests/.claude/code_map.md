# tests/ — code_map（本層索引）

> 顆粒：中。

## 子目錄
- `sales/` — sales 業務邏輯的 pytest 回歸網（對應 `myProgram/sales/`，數百個測試；改 sales prod code 必跑）。
- `spec/` — spec / 行為層測試。
- `stt/` — STT worker 測試（fake 音源 / ws 注入，零真網路零真音訊；含 main.py arm/disarm 佈線測試）。
- `perf/` — 效能基線量測（`bench_sales.py`：micro 熱函式 / scenario 劇本 / import 冷啟動；`python -m tests.perf.bench_sales` 執行，非 pytest 收集）。
- `web/` — web transport 層測試（對應 `myProgram/web/`，Phase 1）：`test_bus.py`（EventBus 廣播 + 斷線剔除）、`test_display.py`（display→dict 映射 / total / 未知商品不 raise）。純 stdlib，Windows 可 pytest。
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
- `conftest.py` — pytest 共用 fixtures / 設定。
- `__init__.py` — 套件標記。
- `CLAUDE.md` — 本層導引。
