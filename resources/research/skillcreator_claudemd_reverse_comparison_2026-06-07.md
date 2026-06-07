# 逆向比對：skill-creator eval 機制 + claude-md-management vs 本專案 harness

> **本檔性質**：兩個官方 plugin（皆 Anthropic 親寫，源碼在本地 marketplace 快取，**只析不裝**）的逆向分析 × 本專案對照，2 個平行分析 agent 產出、主 agent 抽查關鍵引述逐字屬實後綜整。沿用 `security_guidance_reverse_comparison_2026-06-05.md` 的格式。
> **抓取日期**：2026-06-07。源碼：`~\.claude\plugins\marketplaces\claude-plugins-official\plugins\{skill-creator, claude-md-management}\`。

---

## 1. skill-creator eval 機制精華

官方其實是**兩條獨立管線**（常被混為一談）：

- **管線 A（輸出品質，人在迴路）**：主 agent 編排——同輪 spawn with_skill + baseline 兩組 run → grader subagent 逐 run 評 → `aggregate_benchmark.py` 統計（mean ± 樣本 stddev + delta）→ analyzer 抓 pattern → eval-viewer HTML 收人類 feedback → improve → iteration-N+1。工作區 `workspace/iteration-N/eval-X/{config}/run-K/grading.json`。
- **管線 B（觸發優化，全自動）**：`run_eval.py` 把 skill 描述寫成臨時 command 餵 `claude -p` 測觸發率（**每 query 3 次**取 rate、≥0.5 過）→ `improve_description.py` 餵失敗例請模型**泛化重寫**（反過擬 prompt、1024 字硬限）→ `run_loop.py` 最多 5 輪。**防過擬三道閘**：60/40 分層切分（seed=42）、improver 只見 train（history 剝 `test_` 欄）、最終以 test 分選優。

**三 agent 設計亮點**（與我們 navigator/grader/verdict 同構但取向不同）：
- `grader.md`（已逐字驗證）：「**You have two jobs: grade the outputs, and critique the evals themselves. A passing grade on a weak assertion is worse than useless — it creates false confidence**」——grader 兼批 eval 品質，回 `eval_feedback` 欄；另有隱含 claim 抽驗、「surface compliance」防呆（檔名對但內容空 = FAIL）。
- `comparator.md`：**盲評** A/B（不知哪個來自哪版 skill）防偏袒。
- `analyzer.md`：報 pattern 不提建議——專抓「永遠 pass 的非鑑別 assertion」「高變異 flaky eval」。
- `grading.json` 欄位硬約定 `text/passed/evidence`（viewer/aggregate 硬依賴，用 `name/met` 變體會顯示空值）。

## 2. claude-md-management 精華

兩件套全是**人觸發、批准才寫**（無 hook 無自動化）：
- **`claude-md-improver` skill 五階段**：find 全部 CLAUDE.md → 六維評分 → **先報告後更新**（強制）→ targeted additions（diff + 一行 why）→ 批准才 Edit。
- **`/revise-claude-md` command 五步**：session 收尾問「缺了什麼 context」→ 分流 CLAUDE.md（team）vs `.claude.local.md`（個人）→ 一概念一行 → Why+diff 呈現 → 批准才寫。
- **六維 rubric**（quality-criteria.md，已驗證）：Commands(20) / Architecture(20) / Non-Obvious Patterns(15) / Conciseness(15) / **Currency(15)** / Actionability(15)；A-F 五級。**Currency = 指令真的能跑、引用檔存在、技術棧 current**——要求與真實 codebase 交叉比對。
- **update-guidelines 核心原則**（已逐字驗證）：「The context window is precious — **every line must earn its place**」+ TO/NOT-to-add 清單 + 驗證 checklist。

## 3. 與本專案的關鍵差異（精選）

| 面向 | 官方 | 本專案 | 判定 |
|---|---|---|---|
| 定位 | skill-creator＝開發期 co-design（人看產物）；claude-md＝單體 CLAUDE.md 維護 | EDD＝CI 式回歸守門（自動 verdict 看決策）；CLAUDE.md＝分層+code_map+skill 三件分離 | **目標不同類**——可移植的是方法論不是工具 |
| grader 取向 | 評產物品質 + 兼批 eval | **對抗性更強**（不採信自評、強制引 skill 原文）但不批 eval | 我方優勢保留；補「批 eval」職責 |
| baseline | with/without skill 對照 + delta | 無（s5/s10 的 sonnet 變體是降級模型對照，非 with/without） | 官方有我方無 |
| 變異數 | 每 query 3 次、stddev、analyzer 抓 flaky | 單次跑 +「任一 fail 即紅」 | **我方最脆組合**（flaky 一次即誤判） |
| 結果落檔 | 每 run grading.json → 可跨輪聚合 | workflow 回傳不落檔 | 官方有我方無（聚合的前提） |
| 文檔時效 | Currency 維度系統化（跑指令/查引用/驗架構） | 無系統化「文檔↔codebase 脫節」檢查（watch-list 只重訪 harness 元件） | **官方有我方無——最大的洞** |
| session 學習 | 手動 /revise-claude-md | Stop hook 自動反思 + 帳本 + 轉 eval 閉環 | 我方完全覆蓋且更強 |
| 架構維度 | CLAUDE.md 內建目錄圖得 20 分 | 架構事實刻意抽離到 code_map | **直接相剋**——不可裝原樣 improver |

## 4. 採納候選清單（合併排序，狀態待定奪）

| # | 候選 | 來源依據 | 我方缺口 | 成本 | status |
|---|---|---|---|---|---|
| 1 | **code_map 死引用檢查（Currency 落地）**：code_map.md 列的每個路徑 Test-Path 一遍，報死引用 | quality-criteria Currency + Red Flag「references to deleted files」 | 「路徑單一事實來源」的脫節風險無人守 | 低（PS script，與 memory-health 對稱） | **adopted**（365f3a1：scripts/codemap-health.ps1 三段解析+祖先 walk-up，fixture 3 組 + 真實 repo 8 份全綠；用法在 pi-and-structure.md） |
| 2 | **grader 兼批 eval（weak_asserts 欄）**：gradePrompt 加「指出哪些 assertion 即使導航錯也會 pass」 | grader.md「weak assertion 的 pass 比沒有還糟」 | 我們的 assertion 多為「有 Read X」存在性檢查，正是官方點名的弱型 | 極低（prompt + schema 各一欄） | **adopted**（365f3a1：GRADE_SCHEMA + gradePrompt + verdictPrompt 三處；smoke 驗證見 iteration-5） |
| 3 | **EDD 結果落檔協議**：主 agent 收 workflow 回傳後寫 `resources/evals/iteration-N/result.json`（schema 固定） | 官方每 run grading.json 是一切聚合的基礎 | verdict 只回對話不落檔，跨輪趨勢不可查 | 低（協議寫進 README/workflow-authoring） | **adopted**（README「結果落檔」段 + workflow-authoring 資產行；iteration-5 回填今日三輪 dogfood） |
| 4 | **pass@k 變異數（正式守門輪 k=3）**：場景複跑 k 次按 rate 判，平時 k=1 | run_eval 每 query 3 次；analyzer 抓 flaky | 單次跑+任一 fail 即紅=flaky 誤判 | 中（~20 行 + token ×k——只在去噪守門輪開） | pending |
| 5 | **baseline 對照（選擇性場景）**：對「去噪有疑慮」場景跑裸 navigator 對照，驗證 skill 增益 | with/without delta 是 benchmark 核心 | 無從證明去噪後 skill 仍有增益 | 中（token ×2，僅限少數場景） | pending |
| 6 | **CLAUDE.md 分層健檢**（六維 rubric 改造：Architecture 維改「分層分配正確性」+ 行數預算硬 check） | 六維 rubric 骨架 | CLAUDE.md 無對等於 memory-health 的健檢 | 中（依賴候選 1 先做） | pending |
| 7 | **跨輪聚合 script**：讀各 iteration result.json 算每 assertion 跨輪 pass 率（抓非鑑別 assertion） | aggregate_benchmark.py | 依賴候選 3 | 中 | pending |

已在做的不重列：「Why+diff 呈現」（memory-management 第 5 步已採）、对抗 grader、帳本人定奪。

## 5. 不採納清單（疫苗）

| 不採納 | 理由 |
|---|---|
| 裝原樣 claude-md-improver | Architecture 維度獎勵「目錄樹寫進 CLAUDE.md」，會建議把 code_map 搬回 CLAUDE.md——逆轉分層 |
| `/revise-claude-md` 手動 command | 被 stop-reflect 自動反思完全覆蓋且更強；多入口稀釋協議 |
| `#` 鍵直接寫入 CLAUDE.md 的習慣 | 繞過「只提議不自動寫」鐵律，破壞人定奪帳本 |
| description 觸發優化全套（run_loop/run_eval） | 本專案 skill 是主動載入式，觸發率優化前提不成立；且 `claude -p` 子行程手法與本機紅線相衝 |
| eval-viewer HTML | 為「看二進位產物」設計；我們評的是純文字導航決策，verdict 繁中 summary 已足 |
| comparator 1-5 主觀 rubric | 我們的 assertion 是客觀二元，套主觀分反引噪音 |
| monorepo「root 總表」範本 | 與逐層 code_map 相反 |
| A-F 字母等級 / history.json 版本樹 | 單人專題噪音；git + iteration 目錄已足 |

## 6. 對照結論

- 本專案 EDD 的**結構性設計**（schema 強制、對抗 grader、失敗韌性、雙格式相容）已達或超過官方水準；缺的是**評測方法論**的三件配套：落檔聚合（3→7）、變異數（4）、baseline 證明（5）。
- claude-md 側真正的洞是 **Currency**：候選 1 的 code_map 死引用檢查成本最低、守的是我們體系最核心的「路徑單一事實來源」。
- grader 兼批 eval（候選 2）是「讓題庫自我改進」的最便宜入口——與 harness-evolution 的錯誤→eval 閉環互補（一個進貨、一個質檢）。
