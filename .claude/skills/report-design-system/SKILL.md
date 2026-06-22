---
name: report-design-system
description: 產出 / 修改 Project_01 期末報告的 Anthropic 淺色編輯風視覺成果 —— 報告 PDF 頁面（封面 / 章節分隔 / 目錄 / 雙欄內文 / 表格 / 程式碼塊 / 手繪塗鴉）與把深色霓虹系統圖換膚成淺色＋手繪蠟筆風的簡報圖（圖①②③風格）。只要任務沾到報告 PDF 排版、report.html / tokens.css、淺色編輯風 / Anthropic 風 / 米白紙＋珊瑚、把某張架構圖弄成「報告淺色版 / 蠟筆風 / 簡報版」，即使沒明說「設計系統」都載入本 skill。產出 HTML/CSS → 本機 Chromium print-to-PDF（報告）或 screenshot（圖）。本 skill 完全自足（設計 spec + vendored 依賴 rough.js/jason8.ttf + 三張定版對照基準 HTML/PNG/SVG 全內附，不依賴外部檔）。不觸發：畫新的深色霓虹架構圖（→ architecture-diagram skill）、改 webui 點餐頁前端、改 architecture 文字文件(.md)、跟 Project_01 無關的圖。
---

# 報告設計系統製作工作流（Anthropic 淺色編輯風）

把期末報告做成 Anthropic《The Complete Guide to Building Skills for Claude》的品牌設計語言 —— **米白紙 + 墨字 + 珊瑚強調 + 手繪有機線條**。兩條產線共用同一套 tokens／元件：

- **產線 A · 報告 PDF**：HTML/CSS → 本機 Chromium **print-to-PDF**（向量、文字可選取、繁中原生）。
- **產線 B · 系統圖淺色蠟筆換膚**：把深色霓虹系統圖**換膚**成淺色＋手繪蠟筆風的簡報圖，存 gitignored `resources/presentation/`。

> **本 skill 完全自足、可打包帶走**：設計 spec、vendored 依賴、對照基準全在內，**不引用任何 skill 外的檔**（唯 render 時 web font 走 Google Fonts CDN；要全離線把 woff2 下載進 `assets/fonts/`）。動手前讀對應 `reference/`。

## 🔑 自足資源地圖（先讀，知識都在 skill 內）

| 資源 | 路徑 | 是什麼 |
|---|---|---|
| 報告 PDF 設計系統 | `reference/report-pdf.md` | §0 鐵則 / §1 頁面 / §2 色票 / §3 字型 / §4 網格 / §5 元件庫 / §6 塗鴉 / §7 JS+PDF 配方 / §8 待校 / §10 檔案規劃（單一事實來源） |
| 系統圖蠟筆風 | `reference/diagram-crayon.md` | §9：淺色版面慣例 / 蠟筆濾鏡 / Rough.js 填色 / 塗鴉標題 / 強度旋鈕（單一事實來源） |
| 渲染 / 截圖 / SVG / 自檢 | `reference/render-and-qa.md` | Chromium 配方 + 視覺 critical gotchas + 像素自檢 + SVG 匯出（自足，不依賴 architecture-diagram skill） |
| 定版對照基準 | `assets/benchmarks/` | 圖①②③ HTML+PNG+SVG 的 gold standard（先讀 `README.md`） |
| vendored 依賴 | `assets/rough.js` · `assets/fonts/jason8.ttf` | 蠟筆填色 lib（~28KB）· 清松手寫⑧塗鴉標題字（~8MB） |

## ⛔ 鐵則（複刻此風格不可省 — 細節在 `reference/report-pdf.md` §0）

1. **不挪用 Anthropic 商標** — 封面 / 封底星芒 logo 是註冊標誌；放**自己的專題標記**。
2. **全出血色彩必印** — Chromium 預設不印背景色，務必 `print-color-adjust:exact`。
3. **字型載入完成才列印 / 截圖** — 否則 PDF/PNG 內 FOUT、繁中掉字，用 `document.fonts.ready` 守。
4. **繁中走思源 TC** — Noto Serif/Sans CJK **TC**（繁體，非 SC）；專有字拿不到 → 開源近似字替代。
5. **換膚＝只換視覺、逐字逐座標保留** — 產線 B 從深色 HTML 複製，**內容 / 結構 / SVG path 座標 / `.stage` 尺寸 / 卡座標一律保留原樣**，只換 class/變數定義（三張基準即此做法）。**要新增 / 改圖的內容 → 回讀實際碼核對**，嚴禁畫主程式不存在的狀態 / 轉移 / 計時 / 欄位（編造一進報告就是事實錯誤、難事後抓）。

## 📋 產線 A · 報告 PDF 頁面

> 改 HTML = 寫 code，遵守 `karpathy-guidelines`；render 後逐塊自檢（`reference/render-and-qa.md` §2/§3），不給半成品。

1. **頁面骨架**：`reference/report-pdf.md` §1 — `@page{size:11in 8.5in}` 橫式、每頁一個 `.page`、`print-color-adjust:exact`。
2. **抽 tokens.css**：§2/§3 的 `:root` → 獨立 `tokens.css` 供 `report.html` `@import`（檔案規劃見 §10）。
3. **拼頁用元件庫**：§5 — 封面 hero / 章節分隔 hero / 目錄 / 雙欄內文 / 砂色表頭表格 / 程式碼塊 / aside / 行內連結 / folio / 封底。
4. **手繪塗鴉**：§6 — 每章一張 inline SVG 呼應主題（墨色粗筆觸 + 米白幾何塊面）。
5. **JS 守門**：§7 — `document.fonts.ready` + 章節色自動套；內容會回流才疊 Paged.js。
6. **出 PDF**：§7 配方（`reference/render-and-qa.md` §1）— `chrome --headless=new --no-pdf-header-footer --print-to-pdf=…`。
7. **校準**：§8 待校項 — 對 reference 渲染圖核對 `--code-bg` / `--ink-soft` / `--margin` / 字級。

## 📋 產線 B · 系統圖淺色蠟筆換膚

來源＝ `resources/architecture/diagrams/NN-*.html`（深色霓虹定版）。每張：

1. **複製、保留幾何**：複製成 `resources/presentation/NN-*.html`，**逐字逐座標保留**內容 / 結構 / SVG path / `.stage` 尺寸 / 卡座標（鐵則 5）。
2. **內聯換淺色**：把原 `theme/diagram.css` + `tokens.css` 用到的 class / 變數，以淺色設計系統**內聯重定義**（`reference/diagram-crayon.md` §9.1 + 色票 `reference/report-pdf.md` §2）。**self-contained 單檔、不外連 theme**。
3. **加蠟筆濾鏡**：`diagram-crayon.md` §9.2 — `#crayon`（線/箭頭）+ `#crayonEdge`（卡 `::before` 框）放 `.edges <defs>`；§9.2c `#crayonText`（標題）。
4. **Rough.js hachure 填色**：§9.2b — 用本 skill `assets/rough.js`，`window load` 後重畫每張卡填色（`.card{isolation:isolate}` + `z-index:-1` 鐵則，少了填色會消失）。
5. **render 校驗**：`reference/render-and-qa.md` §1（**用舊 `--headless`**、`--virtual-time-budget≥12000`）→ **對 `assets/benchmarks/` 的 PNG 比風格** + 走 §2/§3 自檢紀律。
6. **存 `presentation/`**（gitignored）。強度要調 → §9.4 旋鈕。

## 🔴 視覺 critical gotchas（摘要 — 全文在 `reference/render-and-qa.md` §2）

零卡片覆蓋（含 legend/note/標籤，≥30px）· 文字不溢框 · 字別貼邊（≥圓角半徑）· 卡內容垂直置中 · 卡片大小取決於內容（不做空蕩大卡）· 無大片死空白 · 箭頭走線整齊流暢 · **線↔三角箭頭頭同色**（marker 用 `#ah`/`#ah-hawk` ID 提 specificity，GetPixel 驗）· 箭頭↔文字零交疊。**本蠟筆風額外守**：

- **蠟筆框走 `::before`**：原乾淨邊改 `border-color:transparent` + `overflow:visible`，框由 `::before` + `#crayonEdge` 畫 —— 少了 `overflow:visible` 抖動會被剪。hero 卡 inline `border` 改 `transparent` + `--c-edge:<色>` 避免雙框。
- **Rough 填色掉不見**：每個填色框 `isolation:isolate`，填色 SVG `z-index:-1` 才墊在蠟筆框後、頁面之上（漏了會掉到整卡後消失）。
- **標題別雙重扭形**：字型管「形」、`#crayonText` 管「質」，兩者都重扭＝糊。
- **缺字驗證**：清松手寫⑧生僻字可能缺 → 上線前用實際標題字串 render 檢查（缺字 fallback Huninn，不 tofu）。

## 📦 自足資產

- **設計 spec（單一事實來源）**：`reference/{report-pdf.md, diagram-crayon.md}`。改它＝改設計（原 `resources/report/design-system.md` 已改為指回本 skill 的薄 pointer）。
- **渲染 / QA**：`reference/render-and-qa.md`（自足，不依賴 architecture-diagram skill）。
- **對照基準**：`assets/benchmarks/{01,02,03}-*.{html,png,svg}` + `README.md`。HTML 引用 skill 內 `../rough.js` / `../fonts/jason8.ttf`，可從 skill 內就地 render。
- **vendored 依賴**：`assets/rough.js`、`assets/fonts/jason8.ttf`。

## 🧰 維護原則

- 本 skill 與 `architecture-diagram` 是**「同 HTML/CSS+SVG+Chromium 管線、異主題」的雙生 skill**：深色霓虹（架構圖交付）vs 淺色蠟筆（報告 / 簡報）。風格由任務語意定誰觸發（淺色 / 蠟筆 / 報告 / 簡報 → 本 skill；深色 / 霓虹 / 毛玻璃 / 新架構圖 → architecture-diagram）。**視覺 QA gotchas 與 render 管線兩 skill 各自有自足副本**（本 skill 為自足刻意不共用 architecture-diagram 的 reference；改了通用 gotchas 兩邊都要顧）。
- 新慣例 / 新踩坑 → 寫進對應 `reference/`（spec 在此、即 SSOT）；**新增 / 改對照基準 → 更新 `assets/benchmarks/README.md`**。
- repo 結構變動 → 更新該層 `.claude/code_map.md`（本 skill 已登錄於 root code_map）。
