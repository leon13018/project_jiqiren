# myProgram 效能極限質檢 — 傘狀設計（2026-06-12）

> 多 phase campaign 的**架構契約**：目標、流程、benchmark 規格、review 鏡頭、波次協議、不變式。
> Phase 3 每波開工時依 SDD 另寫 `specs/perf_w<N>_<date>_spec.md` + `plans/perf_w<N>_<date>_plan.md`；與本檔衝突時先回頭修本檔再動工。

## 1. 背景與目標

myProgram（vendor 除外）共 37 檔 / 約 4,400 行。前兩輪 campaign 已完成：oop W1–W6（2026-06-10，四個教科書模式收系統性重複）、quality_fix W1–W4（2026-06-11，dispatch 核心統一 + helper 抽取 + 死碼清理）。

本輪換鏡頭：**效能最大化**。user 授權（2026-06-12）：

1. **全面掃**——不預設面向，發現什麼算什麼；目錄可極大化重構、檔名可改、底層可重做。
2. **行為 100% 不變**——文案、L0–L5 狀態轉換、計時倒數、取消/服務確認流程全保留；504 測試當回歸網，import 路徑可改、**斷言語義不變**。
3. **分路徑治理**——熱路徑（每輪輸入都跑的 NLU 匹配 / 狀態分派）效能贏，抽象只准零成本的（預編譯、查表、模組級常數）；冷路徑（啟動、一次性建構）簡潔結構贏，OOP / 泛型盡量上。
4. **benchmark 驗收**——標準庫量測，重構前後對比，數據進 spec。

## 2. 流程鳥瞰

```
Phase 0  benchmark 基線
  └─ tests/perf/bench_sales.py（量測腳本）
     resources/reviews/perf_baseline_2026-06-12.md（基線數據）

Phase 1  四鏡頭全面 review（只讀不改 prod code）
  └─ resources/reviews/full_review_2026-06-12.md（findings 報告）

Phase 2  user 裁決 + 波次規劃
  └─ 採納清單 + 目標架構設計（若鏡頭④成案大搬遷）
     波次序列 perf_w1..wN，每波一份 SDD spec + plan

Phase 3  逐波 SDD 實作（嚴格序列化，一波 merge 完才開下一波）
  └─ 每波：worktree → spec/plan approval → sales-coder → 三段 reviewer
     → Iron Law（pytest 全綠 + benchmark 對比）→ merge/push → Pi sync
```

**波次排序原則**：結構搬遷最先（後續優化寫在最終結構上）→ 重複邏輯合併（熱點變少、優化只做一次）→ 熱點效能優化（benchmark 歸因清楚）→ 收尾 sweep（docstring / code_map / 文件同步）。

## 3. 行為邊界不變式（每波 spec 附此對照）

> 說話內容、順序、倒數秒數、狀態轉換 = **行為，不可變**；
> 開始說話前的等待、每輪決策耗時 = **效能，優化對象**。

oop 傘狀設計 §7 的 10 條領域不變式（NO 先於 YES、strict-short 防誤命中、wall-clock 起算點、L4 雙計時器、C-2 語意、cart 世界狀態驅動、sales/ 不 import vendor…）全數繼承沿用。

## 4. Phase 0 — benchmark 規格

| 量什麼 | 怎麼量 |
|---|---|
| 單輪決策耗時 | 代表性輸入集（涵蓋 L0–L5、取消/服務確認/數量追問/無效數量路徑），沿用 `tests/` fake-IO 駕駛方式餵 dialog 邏輯，量「輸入字串 → 決策＋回應文案產出」純邏輯耗時 |
| 冷啟動 import | `python -X importtime -c "import myProgram.sales"`（不碰 vendor，Windows 可跑） |

- 標準庫 only（`time.perf_counter`），每場景重複多次取**中位數**，另記 P95。
- **顯著閾值 10%**：低於此視為噪音，不得作為「變快」宣告依據（Iron Law 效能版）。
- 檔名 `bench_` 前綴 → pytest 不收集，不污染回歸網。
- worker 端（TTS / 動作）Windows 跑不了，不入 benchmark；其改善靠靜態分析 + Pi 端 demo 驗證點。

## 5. Phase 1 — 四鏡頭 review

四個 fresh reviewer subagent 並行（只讀不改），派發依 dispatch.md：

| 鏡頭 | 範圍 | 找什麼 |
|---|---|---|
| ① 熱路徑效能 | `nlu.py`、`product_parser.py`、`keyword_group.py`、`constants/keywords.py`、`states/` 每輪分派核心、`cart.py` | 每呼叫重建可預編譯的結構（regex/list/dict）、同一輸入重複線性掃描、可查表化的分支鏈、可 frozenset 化的成員檢查、可快取的純函數 |
| ② 阻塞與排程 | `tts.py`、`action.py`、`input_reader.py`、`queue_worker.py`、`main.py` | 感知延遲大頭：TTS pipeline/prefetch（邊合成邊播）、queue 排程多餘等待、輪詢 sleep 間隔、不必要的 join/lock。約束：計時倒數語義不變 |
| ③ 重複邏輯與抽象 | `sales/states/` 全部（timed_confirm/service_confirm/cancel_confirm/reask/followup 家族）、`constants/*_text.py` | 可合併的相似流程、可泛化的基底/組合 pattern；每條標注合併點是否落熱路徑——落熱路徑只准零成本抽象 |
| ④ 架構結構 | 全目錄 | 目錄/檔名是否反映職責、模組邊界與依賴方向、constants 組織、匯出面；若支持大搬遷 → 給目標目錄樹 before/after + 檔名對映表 |

**彙整規則**（主 agent）：

- 去重 + 衝突調解（③加抽象 vs ①去間接層 → 按分路徑治理裁）。
- 派發 prompt 附「oop W1–W6 + quality_fix W1–W4 已處理項摘要」，避免重提已做過或已被否決項。
- finding 統一格式：`[P0/P1/P2 - hot/cold] 檔:行 — 問題/證據/建議修法/預估收益/風險/建議波次`。
- **全面掃**：低收益項也列出（標 P2），報告不先過濾，採納由 user 裁決。

## 6. Phase 2 — 裁決與波次規劃

- 報告完成 → 通知 user 審查 → 逐項或分批裁決採納範圍。
- 鏡頭④成案大搬遷時，目標架構設計（目錄樹 before/after、檔名對映、import 影響面、tests import 改動清單）作為裁決附件一併定案。
- 採納項按 §2 排序原則編波次，每波單一聚焦主題。

## 7. Phase 3 — 實作協議與風險

- 每波標準 SDD 4 階段；approval 與驗收節點發手機通知。
- **Iron Law 兩條**：`python -m pytest tests/sales/` 全綠（總數以 SessionStart 快照為準，campaign 起點 504）+ 主 agent 親跑 bench 對比表（前/後/差%）。
- **每 finding 原子 commit**：benchmark 無改善或變慢 → 單獨 revert，finding 降級記回報告。
- 搬遷波規約：`git mv` 保留歷史、tests import 同波機械調整（斷言零改）、各層 `code_map.md` 同步更新。
- worker 檔改動波：Windows 驗證受限 → `pineedtodo` 記 Pi 端驗證點，集中兩個時點請 user Pi 實測（worker 波完成後 + 全案收尾）。

| 風險 | 對策 |
|---|---|
| 504 紅掉修不動 | 整波 revert，finding 降級回報告，不帶紅 merge |
| 優化反而變慢 | 原子 commit 單獨 revert |
| 重構中發現真 bug | 直接修、分開 commit、回報透明列出 |
| benchmark 噪音 | 中位數 + 10% 閾值 |

## 8. 測試策略

1. 既有 504 測試 = 行為等價性證明；搬遷波 import 調整視為機械改動、斷言零改。
2. 新基底類 / helper 引入新分支 → 該波 plan 內嵌 TDD 步驟補測。
3. benchmark 腳本不進 pytest 收集；其數據對比由主 agent 於每波收尾親跑。

## 9. Out of scope

- `vendor/` 不動（紅線）。
- 任何對外行為（文案 / 計時值 / keyword 內容 / 狀態轉換）不動。
- 504 測試斷言語義不動、不刪。
- Pi 端環境調優（OS / Python 版本 / 硬體超頻）不在本 campaign。

---

## 10. Campaign 關閉記錄（2026-06-12 append）

五波全數落地（w1 熱點預編譯／w3 分類收斂／w4 sweep／w2 TTS prefetch／
w5 內容定址快取＋預熱，w5 為 user 追加提案），各波 spec 文末附 Iron Law 實測：

- sales 純邏輯熱路徑中位數 **-33%～-55%**（bench 留檔對比）；行為 100% 不變。
- TTS：固定語音零合成零網路（快取命中即播）、連發句間無縫、demo 斷網可播固定句。
- 測試 504 → **515**（+11，既有零修改）；27 findings 全處置（14 採納、13 不採留檔）。
- **Pi 實測 user 回報通過**（2026-06-12）：prefetch／快取即播／demo 實跑皆正常，
  兩張 pineedtodo 驗證單關閉。
- 殘留追蹤：prewarm 資產的 git bootstrap（Pi 端 commit/push）於關閉時尚未完成
  ——快取在 Pi 本地已生效，僅「資產進版控＝斷網保險＋換機免重跑」一步待補
  （指令在 `pineedtodo/2026-06-12_tts_cache_bootstrap.md` 步驟 3）。
- Watch-list（findings／reviewer 場外觀察）：`C2_DECISION_TIMEOUT` 無守值斷言、
  `shared.py` 軟上限、快取孤兒 mp3 清理工具、pytest 偶發跨 test daemon warning。
