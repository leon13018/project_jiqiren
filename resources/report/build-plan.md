# 期末報告 PDF 建置實作計畫（report.html）

> **For agentic workers:** REQUIRED SUB-SKILL: 本計畫為**視覺產出物**（HTML/CSS → Chromium print-to-PDF），render 必須序列化、每章使用者像素級驗收 → 用 `superpowers:executing-plans`（inline，非 subagent-driven）逐章執行。步驟用 checkbox（`- [ ]`）追蹤。

**Goal:** 把 `content-design.md` 的 9 章骨架做成一份 ~15–20 頁、Anthropic 淺色編輯風的橫式 PDF 期末報告，9 張系統圖全嵌入。

**Architecture:** 單一 `report.html`（每頁一個 `.page` 區塊，逐頁手排）+ `tokens.css`（`:root` 設計變數）→ 本機 headless Chromium `--print-to-PDF`。視覺權威全來自 `report-design-system` skill（`reference/report-pdf.md` 元件庫 + `reference/render-and-qa.md` 渲染/QA）；技術內容取材 `resources/architecture/00/10/20/30`（SSOT）。每章開頭一頁**全頁沉浸式 hero 分隔**（`.page--divider`：滿版章節色 + 右上大塗鴉 `.divider__doodle`（`#crayonBig` 濾鏡）+ 左下「Chapter N」膠囊 + 大章名）；塗鴉為**原創、貼題抽象**意象（1靶+箭/2路徑+杯/3分層方塊/4多軌+點/5節點環/6聲波/7畫面+雙向箭/8圈內勾選/9地平線+日出），**非仿 Anthropic 具體圖形**（避版權）。內文頁用輕量內聯標頭（`pill--inline` + `h-page`）。**沉浸式 hero 優先於頁數**（使用者定）→ 全頁碼重排、目錄指向各章分隔頁，報告約 35 頁。機器人吉祥物保留為封面/封底 logo（非章節塗鴉）。

**Tech Stack:** HTML5 + CSS（`@page` 橫式、`column-count:2` 雙欄、CSS 變數）；Google Fonts CDN（Fraunces / Source Serif 4 / Hanken Grotesk / JetBrains Mono / Noto Serif·Sans TC）；headless Chromium（PDF）；poppler `pdftoppm`（PDF→PNG 供視覺 QA）；系統圖以 `<img>` 引 `../architecture/diagrams/NN-*.svg`。

## Global Constraints

> 每個 task 的需求都隱含包含本節。值逐字抄自 `content-design.md` 與 `report-design-system` skill。

- **開本**：橫式 `@page{size:11in 8.5in;margin:0}`；每頁一個 `.page`；`* { print-color-adjust:exact }`（滿版色必印）。
- **字型守門**：`window.READY = document.fonts.ready.then(...)`；render PDF 時 `--virtual-time-budget=15000` 給 CDN 字型 + 嵌圖載入時間（否則繁中掉字 / FOUT / 圖未載）。
- **繁中**：思源 Noto Serif/Sans **TC**（繁體，非 SC）。產出物全繁中（程式碼註解 / 字串 / 文案）。
- **商標**：⛔ 不用 Anthropic 星芒 logo；封面 / 封底放**自家專題標記**（`Project_01` / 校系 / 學號）。
- **配圖**：9 張系統圖一律 `<img src="../architecture/diagrams/NN-*.svg">`（向量容器內嵌 2×PNG，列印清晰）。
- **程式碼**：精選 **≤4 段短碼**（每段 <15 行），用 `.code` 元件；**逐字對照實際 `myProgram/` 原碼**，不得改寫示意（⛔ 不編造）。
- **技術取材**：`architecture/00/10/20/30` 四文件為 SSOT；本報告改寫成報告語氣，**不複製**亦不臆造主程式不存在的狀態 / 欄位 / 計時。
- **篇幅**：文字/敘事頁求精（原訂 ~15–20 標準頁）；但**大圖可讀性優先於頁數**——詳圖各用自訂大頁（見下），報告實際頁數會因此增加、可超 20，可接受。
- **🔑 系統圖＝全屏 hero 頁（使用者定）**：每張系統圖獨佔一頁、**頁尺寸＝該圖長寬比、零頁邊、圖滿版 edge-to-edge**（`.page--bleed{padding:0}` + per-圖具名 `@page bleedNN{size:<圖aspect>;margin:0}` + `.page--bleedNN`；img `width/height:100%;object-fit:cover`）營造 hero 視覺張力；圖內已含 FIG.NN 標題故**不另加圖說**（說明文字放前一頁敘事）。各圖**先量 PNG aspect**（`System.Drawing`/pdfinfo）再定頁：tall 圖（④ 0.82）直式、wide 圖（①②③⑤⑥⑦⑧⑨）橫式。Chromium print-to-PDF 實證支援同檔多頁尺寸。
- **圖檔畫質（使用者定：盡量 SVG／不失真）— 已驗證足夠、無須重算**：系統圖 `.svg` ＝「邏輯尺寸殼內嵌 **2× PNG**」（蠟筆/毛玻璃點陣、無法真向量），但**內嵌即為 2×**（④ 4080×4964、①②③⑤ ~3920px、⑥⑦⑧⑨ 3920px）；Chromium print-to-PDF **不降採樣、原樣保留**（`pdfimages -list` 實測 ④ full-bleed = 4080×4964 @ **371ppi**）→ 全屏 hero 已印刷級清晰。**⚠️ 教訓：判畫質看 `.svg` 內嵌 PNG 解析（或 `pdfimages -list` 驗 PDF 內實際 ppi），別只量 `.png` 交付檔**——`.png` 是 1× 縮圖（如 ④ 2040×2482），會誤判成「偏軟」而做白工重算。webui 截圖 3440×1440 點陣、無 SVG，原生夠用。
- **真機照片**：P1–P4 由使用者提供；先用 `.photo-ph` 虛線佔位框（標「待補：P1…」）。
- **手繪塗鴉（§6）**：每章首頁右上一張 inline SVG（`stroke:var(--ink)` 粗筆觸 round cap/join + `fill:var(--ivory)` 幾何塊），呼應主題 — 1緒論＝燈泡、2概觀＝對話泡泡、3架構＝盒子+插頭、4並行＝多軌平行線、5狀態機＝節點連線、6語音＝聲波、7前端＝畫面框+觸點、8成果＝勾選、9結論＝旗幟。塗鴉 `.chap-doodle` 絕對定位右上、與章頭/prose ≥30px 不壓（守 `render-and-qa.md §2` 零覆蓋）。
- **封面/封底資訊**：林秉宏・11013018・資工4A・人形機器人(2708)・吳世弘教授・2026-06-25（封面 `.cover__meta`、封底 `.backlink`）。
- **專案標誌（lockup）**：`Project_01` 左側放原創蠟筆機器人吉祥物 logo（對應 Anthropic [星芒]Claude 位置、但自創非商標）；字標 Source Serif 4 **600 粗體**、與 logo 貼緊（gap .04in）。**🔑 機器人 logo 對齊鐵則（使用者標準指令，所有 robot logo 一律照辦）**：以**方形臉中點（不含頭頂天線）** 對齊文字垂直中點，而非整個 SVG 框置中——靠 `.brand__logo { transform:translateY(-0.09in) }` 補償天線造成的偏移。
- **執行紀律**：render 序列化、orchestrator **自己** render+QA（不派 subagent 做視覺迭代）；**每章 render→pdftoppm→自檢→使用者驗收**才 commit（逐章驗收）。視覺 critical gotchas 守 `render-and-qa.md §2`。

### 標準頁面製程（每個內容 task 末尾跑這個「render-QA-accept loop」）

```bash
# 1) 出 PDF（路徑空白用 %20）
"/c/Program Files/Google/Chrome/Application/chrome.exe" --headless=new --disable-gpu \
  --no-pdf-header-footer --virtual-time-budget=15000 \
  --print-to-pdf="C:/Users/LIN HONG/Desktop/Project_01/resources/report/out/report.pdf" \
  "file:///C:/Users/LIN%20HONG/Desktop/Project_01/resources/report/report.html"

# 2) PDF → 每頁 PNG（150dpi）供視覺 QA
pdftoppm -r 150 -png "C:/Users/LIN HONG/Desktop/Project_01/resources/report/out/report.pdf" \
  "$TEMP/pdfpeek/pg"
```
然後 **`Read` 本 task 新增的頁 PNG**（`pg-NN.png`），對照 §2 視覺自檢清單；不過關自己改 HTML 重跑。過關 → 給使用者驗收 → commit。

**§2 每頁視覺自檢清單**（違反返工）：① 字型就緒（繁中不掉字、無 FOUT）② hero 滿版色有印出 ③ 文字不溢頁、不貼邊（留 `--margin`）④ 雙欄平衡不溢出 ⑤ 嵌入系統圖清晰可讀、不被裁、與內文 ≥30px 不擠 ⑥ 無大片死空白（底部 / 欄底 >12% 畫布高 = FAIL）⑦ `.code` 每行 < 欄寬（`white-space:pre;overflow:hidden` 會截字）⑧ 頁碼 folio 正確 ⑨ pill / 章頭文字對應正確。

---

## Task 1: 鷹架 — `tokens.css` + `report.html` 骨架 + render 管線

**Files:**
- Create: `resources/report/tokens.css`
- Create: `resources/report/report.html`
- Create: `resources/report/out/`（gitignore；放 `report.pdf`）

**Interfaces:**
- Produces: 全域 `.page` / `.page--content` / `.page--hero` 版面類；§5 元件類（`.cover` `.chapter` `.pill` `.h-page` `.toc` `.prose` `.t` `.code` `.aside` `.folio` `.brand` `.backlink`）+ 報告專用 `.photo-ph`（照片佔位）/ `.fig`（系統圖容器 + 圖說）；CSS 變數（色票 / 字型 / 字級 / 版面）；`window.READY` 字型守門。後續所有 task 只在 `<body>` 插 `.page` 區塊、複用這些類。

- [ ] **Step 1: 寫 `tokens.css`**（抄 `report-pdf.md` §2/§3 的 `:root` + 字型 `@import`）

```css
/* tokens.css — 報告設計系統變數（權威：report-design-system skill reference/report-pdf.md §2/§3）*/
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,600&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@300;400;600&family=Noto+Sans+TC:wght@400;500;700&display=swap');
:root{
  --paper:#ffffff; --ivory:#faf9f5; --ink:#141413; --ink-soft:#5c5b57;
  --coral:#d97757; --tan:#e3dacc; --code-bg:#f4f5f0; --rule:#d9d1c0;
  --ch1:#788c5d; --ch2:#c46686; --ch3:#9b8bc7; --ch4:#6a9bcc; --ch5:#bcd1ca; --ch6:#e3dacc;
  --page-w:11in; --page-h:8.5in; --margin:0.85in; --col-gap:0.5in;
  --font-display:"Fraunces","Noto Serif TC",serif;
  --font-serif:"Source Serif 4","Noto Serif TC",Georgia,serif;
  --font-sans:"Hanken Grotesk","Noto Sans TC",sans-serif;
  --font-mono:"JetBrains Mono",monospace;
  --fs-cover:64pt; --fs-chapter:52pt; --fs-h1:34pt;
  --fs-h2:13pt; --fs-h3:11pt; --fs-body:10.5pt; --fs-label:9.5pt;
  --fs-pill:8.5pt; --fs-folio:8pt; --fs-code:9pt;
}
```

- [ ] **Step 2: 寫 `report.html` 骨架**（`<head>` 內聯 §1 版面 + §5 全部元件類；`<body>` 先放一張封面煙霧測試頁 + 字型守門 script）

```html
<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">
<title>互動式銷售輔助機器人 — 期末專題報告</title>
<link rel="stylesheet" href="tokens.css">
<style>
@page{size:11in 8.5in;margin:0;}
html,body{margin:0;padding:0;background:#d9d9d9;}
*{-webkit-print-color-adjust:exact;print-color-adjust:exact;box-sizing:border-box;}
.page{position:relative;width:11in;height:8.5in;overflow:hidden;background:var(--paper);page-break-after:always;}
.page:last-child{page-break-after:auto;}
.page--content{padding:var(--margin);}
.page--hero{color:var(--ink);}
/* —— §5 元件類：.cover/.chapter/.pill/.h-page/.toc/.prose/.t/.code/.aside/.folio/.brand/.backlink 全抄 report-pdf.md §5 —— */
/* —— 報告專用 —— */
.fig{margin:.12in 0;}
.fig img{width:100%;height:auto;display:block;border:1px solid var(--rule);border-radius:6px;}
.fig figcaption{font-family:var(--font-sans);font-size:var(--fs-label);color:var(--ink-soft);margin-top:.06in;}
.photo-ph{display:flex;align-items:center;justify-content:center;border:2px dashed var(--rule);border-radius:8px;background:var(--ivory);color:var(--ink-soft);font-family:var(--font-sans);font-size:var(--fs-label);min-height:2.2in;text-align:center;}
</style></head><body>
<section class="page page--hero" style="background:var(--coral)">
  <div class="cover">
    <h1 class="cover__title">互動式銷售輔助機器人<br><span>期末專題報告</span></h1>
    <div class="brand"><span class="brand__name">Project_01</span></div>
  </div>
</section>
<script>window.READY=document.fonts.ready.then(()=>document.documentElement.classList.add('fonts-ready'));</script>
</body></html>
```

- [ ] **Step 3: 跑 render-QA loop（見 Global Constraints）** → `Read pg-01.png`

Expected: 封面滿版珊瑚（`#d97757`）有印出、標題繁中思源宋體不掉字、`Project_01` 標記在左下。若珊瑚沒印 → 查 `print-color-adjust:exact`；若繁中掉字 → 查 `--virtual-time-budget` 與字型 `@import`。

- [ ] **Step 4: 建 `out/` 並把 `out/` 加進 `.gitignore`**

Run（確認 gitignore 已含）：在 repo 根 `.gitignore` 加 `resources/report/out/`。

- [ ] **Step 5: Commit**

```bash
git add resources/report/tokens.css resources/report/report.html .gitignore
git commit -m "feat(report): 報告 PDF 鷹架 — tokens.css + report.html 骨架 + 封面煙霧測試"
```

---

## Task 2: 前置 — 封面定稿 + 目錄 + 摘要

**Files:** Modify: `resources/report/report.html`（封面補課程/學號資訊；新增目錄頁、摘要頁）

**Interfaces:** Consumes: Task 1 的 `.cover` `.toc` `.h-page` `.prose` `.folio`。Produces: 第 1–3 頁（封面 / 目錄 / 摘要）。目錄頁碼**先留佔位**，Task 13 總裝時回填。

- [ ] **Step 1: 封面補資訊** — `.cover__title` 與 `.brand` 之間加 `.cover__meta`：人形機器人 (Humanoid Robots)・課程代碼 2708・吳世弘 教授／資工4A・11013018・林秉宏／2026 年 6 月 25 日（sans、`--ink`）。
- [ ] **Step 2: 目錄頁**（`.page--content` + `.h-page>Contents` + `.toc`，9 章 + 章名，頁碼佔位 `—`）。用 §5.3 `.toc__row` 模板。
- [ ] **Step 3: 摘要頁**（`.page--content` + `.h-page>摘要` + 單欄 `.prose`，~200 字）。取材 `00 §1`：一句定義 + 規則匹配(非 LLM) + L1–L5 + 語音/觸控雙模態 + 成果（711 測試 / Pi 實機驗收）。
- [ ] **Step 4: render-QA loop** → `Read pg-01..03.png`（§2 清單；目錄對齊、摘要不溢欄）。
- [ ] **Step 5: 使用者驗收** → **Step 6: Commit**：`feat(report): 前置三頁 — 封面定稿/目錄/摘要`

---

## Task 3: 第 1 章 · 緒論（動機與目標，1–1.5 頁）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.pill--inline` `.h-page` `.prose`。Produces: 第 1 章內容頁；無配圖。

- [ ] **Step 1: 章頭** — `<span class="pill pill--inline">Chapter 1</span>` + `<h1 class="h-page">緒論：動機與目標</h1>`。
- [ ] **Step 2: 內文**（雙欄 `.prose`，取材 `00 §1`）：擺攤銷售情境 → 互動式銷售輔助機器人（Hiwonder TonyPi 站攤、規則匹配非 LLM）；範圍界定（兩商品冰紅茶/刮刮樂、L1–L5）；成果速覽（前向後章導覽一句）。小標 `h2`：研究動機 / 系統目標 / 範圍界定。
- [ ] **Step 3: render-QA loop** → `Read` 該頁 PNG（§2；單章首頁不留大片底部空白，內容約滿 1 頁；超過 1.5 頁則精簡）。
- [ ] **Step 4: 使用者驗收** → **Step 5: Commit**：`feat(report): 第1章 緒論`

---

## Task 4: 第 2 章 · 系統概觀「一杯飲料的旅程」（2 頁，配圖 ④）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.fig`（嵌 ④）`.photo-ph`（P1）。Produces: 第 2 章 2 頁。

- [ ] **Step 1: 章頭 + 故事內文**（取材 `00 §5`，B 手法）：以「觸控/語音點一瓶冰紅茶 → 結帳 → 致謝」一輪互動串全局。五步小標：喚醒 / 進 dialog / 點餐 / 結帳 / 致謝，逐步講資料流。
- [ ] **Step 2: 嵌圖 ④** — `<figure class="fig"><img src="../architecture/diagrams/04-end-to-end-sequence.svg"><figcaption>圖 4 · 一輪互動端到端時序</figcaption></figure>`。
- [ ] **Step 3: 照片佔位 P1** — `<div class="photo-ph">待補：P1 攤位＋機器人＋平板全景</div>`。
- [ ] **Step 4: render-QA loop** → `Read pg PNG`（§2；時序圖跨欄/單欄擇一使圖清晰可讀、不被裁；P1 佔位框比例合理）。
- [ ] **Step 5: 使用者驗收** → **Step 6: Commit**：`feat(report): 第2章 系統概觀（一杯飲料的旅程，圖④）`

---

## Task 5: 第 3 章 · 系統架構與部署（2–2.5 頁，配圖 ⑤ + ⑧）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.fig`×2（⑤⑧）`.aside--bar`（取捨）。Produces: 第 3 章。

- [ ] **Step 1: 內文**（取材 `00 §3–4`、`30 §8`）：單 process 形狀 / 業務邏輯嚴格不碰硬體 / callback 注入；六層模組地圖概覽；硬體拓樸（Pi 4 / ReSpeaker / TonyPi SDK / client 筆電渲染）。
- [ ] **Step 2: 嵌圖 ⑤ `05-deployment-topology.svg` + ⑧ `08-module-dependency.svg`**（各 `.fig` + figcaption「圖 5 · 部署拓樸」「圖 8 · 模組依賴（Hexagonal 注入邊界）」）。
- [ ] **Step 3: 設計取捨小節**（`.aside--bar`）：為何 callback 注入 = sales/ 可在 Windows 跑 pytest；為何 Pi 只當 server（OKLCH / GPU / Chromium<111）、畫面由筆電渲染。
- [ ] **Step 4: render-QA loop** → `Read` PNG（§2；兩張圖都清晰、與內文不擠；總頁 ≤2.5）。
- [ ] **Step 5: 使用者驗收** → **Step 6: Commit**：`feat(report): 第3章 系統架構與部署（圖⑤⑧）`

---

## Task 6: 第 4 章 · 執行期與並行模型（2 頁，配圖 ①，程式碼 §A）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.fig`（①）`.code`（QueueWorker）`.aside--bar`。Produces: 第 4 章。

- [ ] **Step 1: 內文**（取材 `10 §1–4`）：主線程單線程狀態機 + 四 worker（Tts/Action/Input/Stt）+ queue/EventBus 解耦；QueueWorker 消費者骨架；lazy import seam（Windows 紅線）。
- [ ] **Step 2: 嵌圖 ① `01-process-thread.svg`**（figcaption「圖 1 · 進程／執行緒並行模型」）。
- [ ] **Step 3: 程式碼塊 §A** — `QueueWorker._loop` 骨架（<15 行，逐字對照 `myProgram/queue_worker.py`；先 `Read` 原碼再貼）。`.code`。
- [ ] **Step 4: 設計取捨小節**（`.aside--bar`）：全 daemon + `os._exit(0)` 強退；單 queue 單消費者避免旗號分流 race。
- [ ] **Step 5: render-QA loop** → `Read` PNG（§2；**程式碼每行 < 欄寬不被 `overflow:hidden` 截**）。
- [ ] **Step 6: 使用者驗收** → **Step 7: Commit**：`feat(report): 第4章 執行期與並行模型（圖①＋QueueWorker 碼）`

---

## Task 7: 第 5 章 · 核心對話引擎 L0–L5 狀態機 ★（3 頁，配圖 ② + ⑨，程式碼 §B）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.fig`×2（②⑨）`.code`（SalesMachine.run）`.t`（跨層流程表）`.aside--bar`。Produces: 第 5 章（最重，3 頁）。

- [ ] **Step 1: 內文**（取材 `20 §1–6`）：cart 唯一驅動狀態（L2/L3 由 cart 空/非空即時推導）；L1→dialog→L4→L5 轉移；State pattern 調度（Transition / State ABC / 4 個 *State）。
- [ ] **Step 2: 跨層流程表**（`.t` 砂色表頭）：cancel 6s / service 24s / checkout confirm / C-2 自動結帳 / qty followup 各一列（觸發 → 行為 → 保守 default）。
- [ ] **Step 3: 嵌圖 ② `02-sales-state-machine.svg`（行為）+ ⑨ `09-class-diagram.svg`（結構）**（figcaption「圖 2 · L0–L5 銷售狀態機」「圖 9 · State pattern 類別圖」）。
- [ ] **Step 4: 程式碼塊 §B** — `SalesMachine.run` 主迴圈（<15 行，逐字對照 `myProgram/sales/states/machine.py`；cart invariant + `_emit` + Transition）。
- [ ] **Step 5: 設計取捨小節**（`.aside--bar`）：cart 是唯一驅動狀態（非動作歷史）；錢包保守原則（confirm silent/timeout → 保守 default）；TimedConfirm Template Method 收斂三 confirm。
- [ ] **Step 6: render-QA loop** → `Read pg PNG`×3（§2；3 頁分配均衡、兩圖都清晰、表格不溢欄、碼不截行）。
- [ ] **Step 7: 使用者驗收** → **Step 8: Commit**：`feat(report): 第5章 L0–L5 狀態機（圖②⑨＋SalesMachine 碼）`

---

## Task 8: 第 6 章 · 語音管線「聽與說」（2.5 頁，配圖 ⑥ + ⑦）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.fig`×2（⑥⑦）`.aside--bar`（C 精華）`.t`（STT env，選用）。Produces: 第 6 章。

- [ ] **Step 1: 內文**（取材 `10 §3.1–3.2`、`20 §4`、`00 §6`）：STT（Deepgram Nova-3 串流 / ch0 反交錯抽取 / arm-disarm / 每輪新連線）；TTS（edge-tts / 內容定址快取 / 播放期 prefetch）；繁中 NLU + 本地拼音糾錯小節。
- [ ] **Step 2: 嵌圖 ⑥ `06-stt-pipeline.svg` + ⑦ `07-tts-pipeline.svg`**（figcaption「圖 6 · STT 管線」「圖 7 · TTS 管線」）。
- [ ] **Step 3: 設計取捨小節（本章重頭，`.aside--bar`，取材 `roadmap.md` STT 弧 + memory `respeaker_mic_array_v2`）**：ch0 突破（6 聲道降混稀釋 + 相位互抵 → 抽晶片處理過 ch0）；真 barge-in 經 AEC 實測不可行；首字暖機是 Deepgram 串流固有地板（三輪實驗皆 revert）；內容定址快取 = 斷網可播。
- [ ] **Step 4: render-QA loop** → `Read` PNG（§2；兩管線圖清晰、取捨小節不溢；總頁 ≤2.5，超則壓）。
- [ ] **Step 5: 使用者驗收** → **Step 6: Commit**：`feat(report): 第6章 語音管線（圖⑥⑦＋ch0/barge-in 取捨）`

---

## Task 9: 第 7 章 · 前端鏡像與雙模態互動（2 頁，配圖 ③，照片 P2/P3）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.fig`（③）`.photo-ph`×2（P2/P3）`.aside--bar`。Produces: 第 7 章。

- [ ] **Step 1: 內文**（取材 `30 §1–5`）：phase-driven 狀態鏡像（後端 emit phase → 前端折成 standby + overlay）；語音/觸控雙模態（觸控只送命令、走同一 input queue、對話層零改動）；斷線韌性（指數退避 + 回歡迎畫面）；Glaze 玻璃 UI。
- [ ] **Step 2: 嵌圖 ③ `03-web-phase-state-machine.svg`**（figcaption「圖 3 · 後端 phase → 前端畫面」）。
- [ ] **Step 3: 照片佔位 P2/P3** — `.photo-ph`「待補：P2 點餐主畫面截圖」「待補：P3 確認卡/結帳QR/致謝截圖」。
- [ ] **Step 4: 設計取捨小節**（`.aside--bar`）：phase-driven 禁前端樂觀旗號（觸發可能來自語音/自動結帳）；web 故障不得拖垮機器人服務（display try/except）。
- [ ] **Step 5: render-QA loop** → `Read` PNG（§2）。
- [ ] **Step 6: 使用者驗收** → **Step 7: Commit**：`feat(report): 第7章 前端鏡像與雙模態（圖③）`

---

## Task 10: 第 8 章 · 成果與驗證（1.5–2 頁，表格 + 照片 P4）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.t`（測試/驗收表）`.photo-ph`（P4）。Produces: 第 8 章。

- [ ] **Step 1: 內文 + 表格**（取材 `roadmap.md` 現況快照、`changelogs/`「Pi 實測通過」紀錄）：711 pytest 回歸網（sales/ 不碰硬體 → Windows 可完整測）；Pi 實機驗收項（辨識大幅改善 / 觸控全鏈路 / 點餐→結帳→付款→次客）。`.t` 砂色表頭表：驗收項 | 方法 | 結果。
- [ ] **Step 2: 照片佔位 P4** — `.photo-ph`「待補：P4 demo 進行中（顧客互動）」。
- [ ] **Step 3: render-QA loop** → `Read` PNG（§2；表格不溢欄、數字對齊）。
- [ ] **Step 4: 使用者驗收** → **Step 5: Commit**：`feat(report): 第8章 成果與驗證`

---

## Task 11: 第 9 章 · 結論與展望（1 頁）

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.prose`。Produces: 第 9 章；無配圖。

- [ ] **Step 1: 內文**（取材 `roadmap.md` 下一步候選）：總結（規則匹配雙模態銷售機器人、可測試架構）；未來工作 — 真掃碼器（改 `_PAY_TOKEN` 映射）、cap retry redesign、S7 搶話中斷、更多商品、NLU parser 邊緣。
- [ ] **Step 2: render-QA loop** → `Read` PNG（§2）。
- [ ] **Step 3: 使用者驗收** → **Step 4: Commit**：`feat(report): 第9章 結論與展望`

---

## Task 12: 後置 — 參考資料 + 封底

**Files:** Modify: `resources/report/report.html`

**Interfaces:** Consumes: `.prose` `.page--hero` `.brand` `.backlink`。Produces: 參考資料頁 + 封底。

- [ ] **Step 1: 參考資料頁**（`.page--content`，`.prose` 單欄清單）：Deepgram Nova-3 / edge-tts / Hiwonder TonyPi SDK / FastAPI / uvicorn / pypinyin（名稱 + 用途一行）。
- [ ] **Step 2: 封底**（`.page--hero` 滿版珊瑚 + `.brand` 左下 + `.backlink` 右下「github / 學號 / 日期」；§5.10）。
- [ ] **Step 3: render-QA loop** → `Read` PNG（§2；封底珊瑚滿版印出）。
- [ ] **Step 4: 使用者驗收** → **Step 5: Commit**：`feat(report): 後置 參考資料＋封底`

---

## Task 13: 總裝 — folio 回填 + 目錄頁碼 + 全文 QA + 出最終 PDF

**Files:** Modify: `resources/report/report.html`（folio + 目錄頁碼）

**Interfaces:** Consumes: 全部前序頁。Produces: 定稿 `out/report.pdf`。

- [ ] **Step 1: 數總頁、逐頁回填 `.folio`**（封面不編、內頁起算），並回填 **Task 2 目錄頁碼**（章名 → 實際頁）。
- [ ] **Step 2: 全文 render-QA loop** → `Read` 全部 `pg-NN.png`（downscale 掃全局：黑邊 / 大片空白 / 圖被裁 / 章序錯 / folio 連續）。確認**總頁落 15–20**；超則回對應章壓 0.5 頁。
- [ ] **Step 3:（選用）派 3-opus QA panel 讀靜態 PNG 交叉複查**（memory `diagram_qa_cadence`：panel 讀靜態檔、render 序列化已由 orchestrator 跑完）。
- [ ] **Step 4: 使用者最終驗收**（PushNotification 通知）。
- [ ] **Step 5: Commit**：`feat(report): 總裝定稿 — folio/目錄頁碼/全文 QA，出 report.pdf`

---

## Self-Review（對 `content-design.md` 核對）

- **章節覆蓋**：spec §3 九章 + 前後置 → Task 2–12 一一對應；9 張圖（§2 表）→ ④T4 / ⑤⑧T5 / ①T6 / ②⑨T7 / ⑥⑦T8 / ③T9 全嵌；程式碼 §4（≤4 段，SalesMachine.run 必選）→ §A(T6 QueueWorker)+§B(T7 SalesMachine.run) 共 2 段，餘 2 段額度留作 T8 選用；真機素材 §5（P1–P4）→ T4/T9/T9/T10 佔位。**無缺口**。
- **置位決定**：每章一頁全頁沉浸式 hero 分隔（`.page--divider` 大塗鴉 + 膠囊 + 大章名）+ 內文輕量標頭；沉浸感優先於頁數（使用者定，報告約 35 頁）。folio 重排、目錄指向分隔頁。
- **執行模型**：視覺產出物 + render 序列化 + 逐章驗收 → 選 `executing-plans`（inline），非 subagent-driven（合 memory `diagram_fixes_self_not_subagent`）。
- **取材防編造**：每 task Step 標明 `architecture` 來源節 + 程式碼「先 Read 原碼再貼」；守 Global Constraints「不編造」。
