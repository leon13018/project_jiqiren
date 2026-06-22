# resources/ — code_map（本層索引）

> 顆粒：中。

## 子目錄
- `specs/` — SDD 規格書。
- `plans/` — SDD 計畫 / 業務程式邏輯規劃（L0–L5）。
- `reviews/` — 程式碼審查報告。
- `research/` — 研究筆記（官方文檔轉述、最佳實踐、SDD 等）。
- `evals/` — skill EDD 回歸：場景庫（`evals.json` 舊格式 + `scenarios_*.json` 新格式）+ `README.md`（harness 跑法）+ `baseline/`、`iteration-*/` 歷史；harness 本體在 `.claude/workflows/skill-edd-regression.js`。
- `architecture/` — 系統架構文件（**以實作現況為準**，2026-06-21 重寫）：`README.md` 索引 + `00-system-overview`（鳥瞰 / process-thread 模型 / 啟動模式）+ `10-runtime-and-workers`（main.py 編排 + 四 worker 並行）+ `20-sales-state-machine`（L0–L5）+ `30-web-mirror-and-frontend`（web 交互狀態機）；`_archive/` 收已封存的舊願景 / 契約（FastAPI 願景式，過時不參考）。`diagrams/` 報告用系統架構圖（HTML/CSS + Chromium 截圖、交付 PNG + SVG）；**製作工作流＝ `.claude/skills/architecture-diagram` skill（已改宗 `report-design-system` 淺色蠟筆風）**。佈局：`specs/`（`00-diagram-backlog` 11 張清單 + 波次 + `01–05` 各圖內容 spec，風格無關、淺色重畫可重用）、`_legacy-dark/`（**深色 legacy 歸檔**：深色 `theme/` + 深色圖 ①–⑤ 三式；保留為淺色重畫的來源素材）、各圖淺色交付 `NN-*.{png,svg}` 置主層。狀態：**淺色 ①②③ 已交付**（png+svg；html 源在 report-design-system 基準）、④⑤ 待淺色重畫（源在 `_legacy-dark/`）、⑥–⑪ 待畫。
- `report/` — 報告 PDF 產出（Anthropic 淺色編輯風,橫式 11×8.5,HTML/CSS → 本機 Chromium print-to-PDF;**有別於** `architecture/diagrams/` 的深色霓虹圖風）：`design-system.md` = **薄 pointer**（設計系統權威已搬入完全自足的 `report-design-system` skill —— spec / vendored 依賴 / 三張對照基準全內附,改設計改該 skill reference/）；報告產出物（待建）report.html、tokens.css、assets/fonts、assets/doodles、out/ 仍建在本層,做法見 report-design-system skill 的 reference/report-pdf.md §10。
- `requirements/` — 需求文件（Raspberry Pi setup / 已安裝清單）。
- `pineedtodo/` — Pi 端待辦操作說明書（寫入 append-only；完成即 `git mv` 進 `archive/` 子目錄，主目錄只留未完成 pending）。
- `examples/` — 範例 code。
- `changelogs/` — 開發日誌分期詳錄（按時期一檔；索引在 `changelog.md`）。
- `roadmaps/` — 未來計畫詳檔（索引在 `roadmap.md`）。
- `reflections/` — （gitignored）人定奪帳本：`proposals.md`（反思提議）+ `memory_ledger.md`（memory 健檢/整併定奪）；處理完的反思 → `archive/`（比照 pineedtodo 歸檔慣例，active 帳本只留待定奪）。
- `presentation/` — （gitignored）報告 / 簡報。
- `userPrompt/` — （gitignored）prompt 存檔。
- `snapshots/` — （gitignored，只追蹤 README）架構圖自檢截圖暫存：畫圖時 Chromium 截圖確認 / 裁切放大逐項核對用，非交付物（正式圖檔交付進 `architecture/diagrams/`）；製作工作流見 skill `architecture-diagram`。
- `.claude/` — 本層 CC 配置（`code_map.md` 本檔）。

## 檔案
- `roadmap.md` — 路線圖**索引**：現況快照 + 下一步候選 + 路由到 `roadmaps/`。
- `watchlist.md` — harness 留觀察項目單一事實來源（重訪節奏 + 觸發訊號；協議見 skill reference/harness-evolution.md）。
- `changelog.md` — 開發日誌**索引**：每期一行路由到 `changelogs/`（**勿當 code map**）。
- `CLAUDE.md` — 本層導引。
