# 報告 PDF 設計系統 — Anthropic 淺色編輯風（橫式 11×8.5）

> **🎯 何時讀本檔**：做報告 PDF 頁面（封面 / 章節分隔 / 目錄 / 雙欄內文 / 表格 / 程式碼塊 / 塗鴉）、抽 `tokens.css`、調色票 / 字型 / 網格 / 元件 / 出 PDF 配方時。系統圖蠟筆換膚 → 讀 [diagram-crayon.md](diagram-crayon.md)；渲染 / 截圖 / 自檢 → [render-and-qa.md](render-and-qa.md)。
>
> **本檔＝報告設計系統單一事實來源**（原 `resources/report/design-system.md` §0–§8,§10，已搬入本 skill）。複刻 Anthropic《The Complete Guide to Building Skills for Claude》的品牌設計語言（來源檔 `resources/research/The-Complete-Guide-to-Building-Skill-for-Claude.pdf`，33 頁，Adobe InDesign + Anthropic 專有字型）。
> **產出路徑**：HTML/CSS → 本機 headless Chromium `print-to-PDF`（向量、文字可選取、繁中原生）。**非** WeasyPrint/Typst。
> **狀態**：v1 規格。色票為像素取樣值；標 `≈` / `待校` 者於首版 proof 對 reference 渲染圖校準（reference 圖在 `%TEMP%\pdfpeek\pg-NN.png`，由 `pdftoppm -r 150` 產生）。

## 目錄
0. 鐵則 · 1. 頁面格式 · 2. 色彩 Tokens · 3. 字型 · 4. 版面網格 · 5. 元件庫 · 6. 手繪塗鴉 · 7. JavaScript + PDF 配方 · 8. 待校準項 · 10. 檔案規劃

---

## 0. 鐵則（複刻此風格的不可省項）

1. **逐字字型拿不到** → Anthropic Sans/Serif 為專有字，用開源近似字替代（§3）。觀感擬真,非像素相同。
2. **不可挪用 Anthropic 商標** → 封面/封底的星芒 logo 是 Anthropic 註冊標誌；本報告改放**自己的專題標題/標記**。
3. **全出血色彩必須印出** → Chromium 預設不印背景色,務必加 `print-color-adjust:exact`（§1）。
4. **字型載入完成才列印** → 否則 PDF 內 FOUT/掉字,用 `document.fonts.ready` 守（§7）。
5. **繁中走思源** → Noto Serif/Sans CJK **TC**（繁體,非 SC）。

---

## 1. 頁面格式

- **開本**：US Letter **橫式** = `11in × 8.5in`（792 × 612 pt = 279.4 × 215.9 mm）。
- **出血**：來源檔無出血框（DTP 直接滿版色）；HTML 走「滿版 `.page` + 內距」模型,不需出血標記。
- **分頁**：每頁一個 `.page` 元素,`break-after:always`。內容若會回流溢頁 → 疊 **Paged.js**（§7）；本報告若逐頁手排,純 CSS 即可。

```css
@page { size: 11in 8.5in; margin: 0; }          /* 尺寸來自此處,邊距交給 .page 內距 */

html, body { margin: 0; padding: 0; background: #d9d9d9; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact; box-sizing: border-box; }

.page {
  position: relative;
  width: 11in; height: 8.5in;
  overflow: hidden;
  background: var(--paper);
  page-break-after: always;     /* 最後一頁可移除 */
}
.page:last-child { page-break-after: auto; }
.page--content { padding: var(--margin); }       /* 內文頁有內距 */
.page--hero    { color: var(--ink); }            /* 滿版色頁,內容絕對定位 */
```

---

## 2. 色彩 Tokens（像素取樣值）

| Token | Hex | 用途 |
|---|---|---|
| `--paper` | `#FFFFFF` | 內頁底 |
| `--ivory` | `#FAF9F5` | 造型塊面 / logo 米白 / 章節頁裝飾形 |
| `--ink` | `#141413` | 文字 / 手繪線條（Anthropic 標準墨色） |
| `--ink-soft` | `#5C5B57` `≈` | 次級文字 / 註腳 / 頁碼（估,待校） |
| `--coral` | `#D97757` | 封面/封底滿版 · 行內連結 · 強調（Anthropic 品牌珊瑚） |
| `--tan` | `#E3DACC` | 表格表頭 · 膠囊標籤底（如需填色） · ch6 砂色 |
| `--code-bg` | `#F4F5F0` `待校` | 程式碼塊底（極淡暖灰/沙；取樣近白,首版 proof 校準） |
| `--rule` | `#D9D1C0` `≈` | 表格細線 |

**章節分隔滿版色**（每章一色,循環）：

| 章 | Token | Hex | 色名 |
|---|---|---|---|
| 1 | `--ch1` | `#788C5D` | 橄欖綠 |
| 2 | `--ch2` | `#C46686` | 玫瑰紫 |
| 3 | `--ch3` | `#9B8BC7` | 矢車菊紫 |
| 4 | `--ch4` | `#6A9BCC` | 天藍 |
| 5 | `--ch5` | `#BCD1CA` | 薄荷綠 |
| 6 | `--ch6` | `#E3DACC` | 暖砂 |

```css
:root {
  /* 紙與墨 */
  --paper:#ffffff; --ivory:#faf9f5; --ink:#141413; --ink-soft:#5c5b57;
  /* 品牌 */
  --coral:#d97757; --tan:#e3dacc; --code-bg:#f4f5f0; --rule:#d9d1c0;
  /* 章節分隔 */
  --ch1:#788c5d; --ch2:#c46686; --ch3:#9b8bc7; --ch4:#6a9bcc; --ch5:#bcd1ca; --ch6:#e3dacc;
  /* 版面 */
  --page-w:11in; --page-h:8.5in; --margin:0.85in; --col-gap:0.5in;
  /* 字型 */
  --font-display:"Fraunces","Noto Serif CJK TC",serif;             /* 標題/章名/封面 */
  --font-serif:"Source Serif 4","Noto Serif CJK TC",Georgia,serif; /* 內文襯線 */
  --font-sans:"Hanken Grotesk","IBM Plex Sans","Noto Sans CJK TC",sans-serif;
  --font-mono:"JetBrains Mono","Noto Sans Mono CJK TC",monospace;
  /* 字級（pt,橫式 11×8.5 印刷） */
  --fs-cover:64pt; --fs-chapter:52pt; --fs-h1:34pt;
  --fs-h2:13pt; --fs-h3:11pt; --fs-body:10.5pt; --fs-label:9.5pt;
  --fs-pill:8.5pt; --fs-folio:8pt; --fs-code:9pt;
}
```

---

## 3. 字型

| 角色 | 原檔（專有,拿不到） | 開源替代 | 繁中 |
|---|---|---|---|
| 顯示（封面/章名/頁標題,襯線） | Anthropic Serif | **Fraunces**（球狀字腳、對比近似） | 思源宋體 Noto Serif CJK TC |
| 內文襯線 | Anthropic Serif Text | **Source Serif 4** | 思源宋體 Noto Serif CJK TC |
| 無襯線（小標/標籤/表格/頁碼） | Anthropic Sans | **Hanken Grotesk**（或專案既用 IBM Plex Sans） | 思源黑體 Noto Sans CJK TC |
| 程式碼 | JetBrains Mono | **JetBrains Mono**（免費,與原檔相同） | — |

```css
/* 線上（render 時有網路即可）。離線版改為本機 @font-face,字型檔放 assets/fonts/ */
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,600&family=Source+Serif+4:ital,wght@0,400;0,600;1,400&family=Hanken+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
/* 繁中（檔大,建議離線子集化；線上備援如下） */
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+TC:wght@300;400;600&family=Noto+Sans+TC:wght@400;500;700&display=swap');
```

- **Fraunces 調性**：用 `opsz`（光學字級）拉大顯示字、`wght:300` 對齊原檔細標題；正文 Source Serif 4 `400`。
- **離線/可重現**：把上述 woff2 下載進 `assets/fonts/`,以本機 `@font-face` 載入,免依賴 CDN（繁中思源建議 `pyftsubset` 子集化以縮檔）。本 skill 預設僅 vendored 蠟筆手寫字 `assets/fonts/jason8.ttf`，web font 走 CDN（要全離線再自行下載 woff2 進 `assets/fonts/`）。
- **字級節奏**：封面 64 / 章名 52 / 頁標題（Contents·Introduction）34 / sans 小標 13 / 內文 10.5（行高 1.5）/ 標籤·頁碼 8–9.5。

---

## 4. 版面網格

```
┌─ 11in ─────────────────────────────────────────┐
│  ⟵0.85in⟶                          ⟵0.85in⟶     │ 0.85in
│   ┌── col 1 ──┐  0.5in  ┌── col 2 ──┐           │
│   │  內文襯線  │  gutter │  內文襯線  │           │ 8.5in
│   └───────────┘         └───────────┘           │
│                                        folio →  │ 右下頁碼
└─────────────────────────────────────────────────┘
```

- **邊距** `--margin: 0.85in`（四邊；左邊距視覺約 1in,首版可微調）。
- **內文雙欄** `column-count:2`、`column-gap:0.5in`。
- **頁碼** 右下,距邊 `--margin`,sans 8pt,`--ink`（封面無頁碼,內頁起算）。

---

## 5. 元件庫

### 5.1 封面 Hero（滿版珊瑚）

```html
<section class="page page--hero" style="--bg:var(--coral)">
  <div class="cover">
    <h1 class="cover__title">互動式銷售輔助機器人<br><span>期末專題報告</span></h1>
    <div class="brand">
      <!-- 換成自己的專題標記,勿用 Anthropic 星芒 -->
      <span class="brand__name">Project_01</span>
    </div>
  </div>
</section>
```
```css
.page--hero { background: var(--bg); }
.cover { position:absolute; inset:var(--margin); display:flex; flex-direction:column; }
.cover__title {
  margin:0; max-width:64%;
  font-family:var(--font-display); font-weight:300; font-size:var(--fs-cover);
  line-height:1.05; letter-spacing:-0.01em; color:var(--ink);
}
.cover__title span { font-size:0.6em; }
.brand { margin-top:auto; display:flex; align-items:center; gap:.16in; }
.brand__name { font-family:var(--font-display); font-size:22pt; color:var(--ink); }
```

### 5.2 章節分隔 Hero（滿版換色 + 膠囊標籤 + 手繪藝術 + 大章名）

```html
<section class="page page--hero" style="--bg:var(--ch1)">
  <div class="doodle"><!-- inline SVG,見 §6 --></div>
  <div class="chapter">
    <span class="pill">Chapter 1</span>
    <h1 class="chapter__title">系統架構</h1>
  </div>
  <span class="folio">4</span>
</section>
```
```css
.doodle { position:absolute; top:0; right:0; width:55%; height:72%; }
.chapter { position:absolute; left:var(--margin); bottom:var(--margin); }
.pill {
  display:inline-block; border:1.5px solid var(--ink); border-radius:999px;
  padding:.05in .17in; font-family:var(--font-sans); font-weight:600;
  font-size:var(--fs-pill); letter-spacing:.02em; color:var(--ink);
}
.chapter__title {
  margin:.26in 0 0; font-family:var(--font-display); font-weight:300;
  font-size:var(--fs-chapter); line-height:1.02; letter-spacing:-0.01em; color:var(--ink);
}
.folio {
  position:absolute; right:var(--margin); bottom:var(--margin);
  font-family:var(--font-sans); font-size:var(--fs-folio); color:var(--ink);
}
```

### 5.3 目錄（Contents）

```html
<section class="page page--content">
  <h1 class="h-page">Contents</h1>
  <nav class="toc">
    <a class="toc__row"><span class="toc__title">系統架構</span><span class="toc__page">3</span></a>
    <a class="toc__row"><span class="toc__title">STT / TTS 管線</span><span class="toc__page">7</span></a>
  </nav>
  <span class="folio">2</span>
</section>
```
```css
.h-page { margin:0 0 .4in; font-family:var(--font-display); font-weight:400; font-size:var(--fs-h1); color:var(--ink); }
.toc { max-width:6.4in; }
.toc__row {
  display:flex; align-items:baseline; justify-content:space-between;
  padding:.13in 0; font-family:var(--font-sans); font-weight:500; font-size:13pt;
  color:var(--ink); text-decoration:none;
}
.toc__page { font-variant-numeric:tabular-nums; }
/* 來源檔頁碼置於中段 tab、無點線引導；如需點線:在 row 內加 .toc__dots{flex:1;border-bottom:1px dotted} */
```

### 5.4 內文頁（雙欄）+ 標題 / 小標 / 內文 / 清單

```html
<section class="page page--content">
  <span class="pill pill--inline">Chapter 1</span>
  <h1 class="h-page">系統架構</h1>
  <div class="prose">
    <h2>程序與執行緒模型</h2>
    <p>主程式以 <code>main.py</code> 編排四個 worker……</p>
    <h3>啟動模式</h3>
    <ul><li>S6 監督下常駐</li><li>手動 CLI 除錯</li></ul>
    <p class="aside">提示：本節對應 <code>resources/architecture/10-runtime-and-workers</code>。</p>
  </div>
  <span class="folio">5</span>
</section>
```
```css
.pill--inline { margin-bottom:.12in; }
.prose { column-count:2; column-gap:var(--col-gap);
  font-family:var(--font-serif); font-size:var(--fs-body); line-height:1.5; color:var(--ink); }
.prose h2 { font-family:var(--font-sans); font-weight:600; font-size:var(--fs-h2);
  margin:.22in 0 .07in; break-after:avoid; }
.prose h3 { font-family:var(--font-sans); font-weight:600; font-size:var(--fs-h3);
  margin:.15in 0 .04in; break-after:avoid; }
.prose p  { margin:0 0 .12in; }
.prose ul { margin:0 0 .12in; padding-left:1.1em; }
.prose li { margin:.04in 0; }
.prose h2:first-child, .prose h3:first-child { margin-top:0; }
```

### 5.5 表格（砂色表頭）

```css
.t { width:100%; border-collapse:collapse; font-family:var(--font-sans);
  font-size:var(--fs-label); color:var(--ink); margin:.1in 0 .18in; }
.t th { background:var(--tan); font-weight:600; text-align:left; }
.t th, .t td { border:1px solid var(--rule); padding:.1in .14in; vertical-align:top; }
```

### 5.6 程式碼塊

```css
.code { background:var(--code-bg); border-radius:6px; padding:.16in .18in;
  font-family:var(--font-mono); font-size:var(--fs-code); line-height:1.45;
  white-space:pre; overflow:hidden; color:var(--ink); margin:.1in 0 .16in; }
/* 行內 code */
code { font-family:var(--font-mono); font-size:.92em; }
```

### 5.7 Aside / 重點（斜體襯線）

```css
.aside { font-style:italic; color:var(--ink-soft); }
/* 變體:左側珊瑚色標線 */
.aside--bar { font-style:italic; border-left:2px solid var(--coral); padding-left:.16in; }
```

### 5.8 行內連結

```css
.prose a { color:var(--coral); text-decoration:underline; text-underline-offset:2px;
  text-decoration-thickness:1px; }
```

### 5.9 頁碼 / running footer

兩種策略,**手排首選 (A)**：
- **(A) 手放 `.folio`**（每頁一個元素,精準、可逐頁略過封面）——見上各模板。
- **(B) Paged.js 自動**：`@page { @bottom-right { content: counter(page); font:8pt var(--font-sans); color:var(--ink); } }`，封面用具名 page 關閉計數。內容會回流時用。

### 5.10 封底（滿版珊瑚）

```html
<section class="page page--hero" style="--bg:var(--coral)">
  <div class="brand" style="position:absolute;left:var(--margin);bottom:var(--margin)">
    <span class="brand__name">Project_01</span>
  </div>
  <span class="backlink">github / 學號 / 日期</span>
</section>
```
```css
.backlink { position:absolute; right:var(--margin); bottom:var(--margin);
  font-family:var(--font-sans); font-weight:600; font-size:10pt; color:var(--ink); }
```

---

## 6. 手繪塗鴉系統

來源檔每章一張手繪有機線條（黑墨粗筆觸 + 米白幾何形）,呼應該章主題：樓梯＝迭代、大括號+!＝troubleshooting、線圈筆記本＝resources、插頭/方塊＝planning。複刻方式＝**inline SVG**。

- **線條**：`stroke:var(--ink)`、`stroke-width:13~16`、`stroke-linecap/linejoin:round`、`fill:none`；路徑刻意輕微不規則（手感）。
- **塊面**：米白 `fill:var(--ivory)` 的三角/多邊/方形,墊在線條後。
- **配置**：右上,佔頁面右側 ~55%×70%。
- **本報告對應**（建議）：點餐＝對話泡泡、收款＝硬幣/收據、STT/TTS＝聲波、狀態機＝節點連線、測試＝勾選、部署＝盒子/箭頭。

```html
<svg class="doodle" viewBox="0 0 600 460" preserveAspectRatio="xMidYMid meet">
  <polygon points="360,250 470,250 415,150" fill="var(--ivory)"/>          <!-- 米白三角 -->
  <path d="M120,300 C180,250 150,360 220,330 S330,300 380,260"
        fill="none" stroke="var(--ink)" stroke-width="14"
        stroke-linecap="round" stroke-linejoin="round"/>                   <!-- 手繪線 -->
  <circle cx="120" cy="300" r="16" fill="var(--ink)"/>                     <!-- 端點圓 -->
</svg>
```
> 每章 SVG 另存 `assets/doodles/ch-N.svg` 或 inline 進模板。可用 `feTurbulence`+`feDisplacementMap` 給線條加極輕「手抖」位移增手感（選用）。

---

## 7. JavaScript + Chromium PDF 配方

```html
<!-- (選用) Paged.js:內容回流自動分頁 + running footer。逐頁手排則免 -->
<script src="https://unpkg.com/pagedjs/dist/paged.polyfill.js"></script>

<script>
  // 列印前確保字型就緒,避免 PDF 內 FOUT / 繁中掉字
  window.READY = document.fonts.ready.then(() => document.documentElement.classList.add('fonts-ready'));

  // (選用) 依 .page[data-ch] 自動套章節色
  document.querySelectorAll('.page--hero[data-ch]').forEach(p => {
    p.style.setProperty('--bg', `var(--ch${p.dataset.ch})`);
  });
</script>
```

**Chromium 出 PDF 配方**（零安裝,用截圖管線同一個 Chromium）：
```bash
chrome --headless=new --disable-gpu \
  --no-pdf-header-footer \
  --print-to-pdf="report.pdf" \
  "file:///C:/Users/.../resources/report/report.html"
```
- 尺寸由 `@page{size:11in 8.5in}` 決定；`--no-pdf-header-footer` 去掉瀏覽器頁眉頁腳。
- 背景色靠 `print-color-adjust:exact`（§1）保留滿版色。
- 字型未就緒風險：先在頁面 `await window.READY` 或加載延遲後再列印（Playwright `page.pdf()` 可 `await page.evaluate(()=>window.READY)`）。
> ⚠️ 出 **PDF** 用 `--print-to-pdf` 可走 `--headless=new`；但出 **PNG 截圖**（§9 系統圖）要用舊 `--headless`（`--headless=new`+`--screenshot` 本機不寫檔，見 [render-and-qa.md](render-and-qa.md)）。

---

## 8. 待校準項（首版 proof 對 reference 圖核對）

- `--code-bg`：取樣多為近白,確認是否有極淡沙/綠 tint。
- `--ink-soft` / `--rule`：次級文字與表線實際值。
- 連結色：暫定 `--coral`,核對是否更深。
- `--margin` 與字級：對 `pg-03/05/06.png` 量測微調（左邊距、欄寬、內文字級）。
- 各章手繪藝術：逐章設計呼應主題的 SVG。

---

## 10. 檔案規劃（`resources/report/`）

```
resources/report/
├── design-system.md      ← 薄 pointer（權威已搬入本 skill reference/）
├── report.html           ← (待建) 全本報告
├── tokens.css            ← (待建) 由 §2/§3 抽出的 :root,供 report.html @import
├── assets/
│   ├── fonts/            ← (待建) 離線 woff2(含思源 TC 子集)
│   └── doodles/          ← (待建) 各章 ch-N.svg
└── out/                  ← (待建,建議 gitignore) Chromium 產出 report.pdf
```
> 設計權威＝本 skill（`reference/report-pdf.md` + `reference/diagram-crayon.md`）；報告**產出物**（report.html / tokens.css / fonts / doodles / out）建在 `resources/report/`。交付路徑與 git 收尾協議見 `project-01-workflow` skill。
