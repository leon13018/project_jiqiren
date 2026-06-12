# Changelog — 效能極限 campaign（2026-06-12，單日五波）

> 詳細規格、逐波 Iron Law 實測數據、findings 全文都在指標檔，本檔只記結論與指標位置。
> 傘狀設計（含 §10 關閉記錄與 watch-list）：`resources/specs/perf_review_2026-06-12_design.md`。

## 成果指標

- sales 純邏輯熱路徑中位數 **-33%～-55%**（基線 `resources/reviews/perf_baseline_2026-06-12.md`，對比數據在各波 spec 文末「實測結果」段）。
- TTS：固定語音**零合成零網路**（內容定址快取，55 句資產 1.5MB tracked 進 git）、連發句間無縫、**demo 斷網可播全部固定句**；Pi 實測 user 回報通過。
- **行為 100% 不變**；測試 504 → **515**（+11 新增、既有零修改）。
- 四鏡頭 review 27 findings：14 採納全落地、13 不採留檔防重提（`resources/reviews/full_review_2026-06-12.md`；結論：不搬遷目錄）。

## 五波（執行序）

| 波 | 主題 | spec |
|---|---|---|
| perf_w1 | keyword 預 lower＋regex 預編譯＋`keyword_group` 搬入 `constants/` | `specs/perf_w1_2026-06-12_spec.md` |
| perf_w3 | `cart.classify_qty` 收斂三處數量分類＋`_cancel_gate` helper | `specs/perf_w3_2026-06-12_spec.md` |
| perf_w4 | `_entry_prompt_for`＋`AUTO_CHECKOUT_NOTICE` 死常數連衛兵移除 | `specs/perf_w4_2026-06-12_spec.md` |
| perf_w2 | TTS 常駐 event loop＋播放中 prefetch（雙 buffer） | `specs/perf_w2_2026-06-12_spec.md` |
| perf_w5 | 內容定址快取（雙 buffer 退役）＋`tts_prewarm`＋資產進 git（user 追加提案） | `specs/perf_w5_2026-06-12_spec.md` |

## 架構級變化（影響後續開發）

- `keyword_group.py` 現居 `myProgram/sales/constants/`（純值原語歸資料層，反向 import 消除）。
- TTS 管線改三層：快取 → prefetch → 合成；**文案常數改動 SOP** 見 skill `sales-tts-ux.md` §合成管線（Pi 跑 prewarm → dev scp 回 commit）。
- 新工具：`tests/perf/bench_sales.py`（效能前後對比，非 pytest 收集）、`myProgram/tts_prewarm.py`。

## 流程沉澱

- cwd-pinned session 的 `EnterWorktree(path)` hop 模式（`worktree.md` cwd-pinned 例外段已記）。
- Watch-list（傘狀 §10）：`C2_DECISION_TIMEOUT` 無守值斷言、`shared.py` 軟上限、快取孤兒 mp3 清理工具、pytest 偶發跨 test daemon warning。
