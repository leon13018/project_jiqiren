# 報告設計系統 — Anthropic 淺色編輯風（橫式 11×8.5）

> **用途**：Project_01 期末報告 PDF 的單一視覺事實來源。複刻 Anthropic《The Complete Guide to Building Skills for Claude》之品牌設計語言（來源檔 `resources/research/The-Complete-Guide-to-Building-Skill-for-Claude.pdf`，33 頁，Adobe InDesign + Anthropic 專有字型）。
> **產出路徑**：HTML/CSS → 本機 headless Chromium `print-to-PDF`（向量、文字可選取、繁中原生）。**非** WeasyPrint/Typst（毛玻璃無關，但此風格也不依賴瀏覽器專屬效果，故任一 Chromium 引擎皆可）。
> **本檔狀態**：v1 規格。色票為像素取樣值；標 `≈` / `待校` 者於首版 proof 對 reference 渲染圖校準（reference 圖在 `%TEMP%\pdfpeek\pg-NN.png`，由 `pdftoppm -r 150` 產生）。

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
- **離線/可重現**：把上述 woff2 下載進 `assets/fonts/`,以本機 `@font-face` 載入,免依賴 CDN（繁中思源建議 `pyftsubset` 子集化以縮檔）。
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

## 7. JavaScript

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

---

## 8. 待校準項（首版 proof 對 reference 圖核對）

- `--code-bg`：取樣多為近白,確認是否有極淡沙/綠 tint。
- `--ink-soft` / `--rule`：次級文字與表線實際值。
- 連結色：暫定 `--coral`,核對是否更深。
- `--margin` 與字級：對 `pg-03/05/06.png` 量測微調（左邊距、欄寬、內文字級）。
- 各章手繪藝術：逐章設計呼應主題的 SVG。

---

## 9. 系統圖手繪蠟筆風（`resources/presentation/` 的 01–03）

> 範圍：報告內的**系統架構圖**（圖①Process/Thread、圖②L0–L5 狀態機、圖③Web phase 狀態機），由 `architecture/diagrams/` 深色霓虹版**換膚**成本設計系統的淺色＋手繪蠟筆風,存 gitignored `presentation/`。**自足單檔**（樣式內聯,不外連 `theme/diagram.css`）。

### 9.1 淺色版面慣例
- 底：ivory `#faf9f5` + 40px 格線 `#ece6da`（`.stage` 雙 linear-gradient）。
- 標題：置中 Fraunces 31 + **珊瑚 `#d97757` 的 FIG.NN 牌**（mono 21/600、珊瑚框）。
- 卡片：ivory/白填底 + 細彩邊 + 圓角 + 極淺陰影；**無純白卡**（legend/chip/閘卡一律 ivory `#faf9f5`）。
- **珊瑚只給「主角環 / hero」**（emit 閉環、input queue inject）；其餘節點用 palette 章節色分類（同類同色）。
- **不畫 process 外框**（背景留乾淨格線,比照各圖一致）。
- **z-index 分層**：背景面板（`.frame`/`.group`）`1` < 箭頭 `.edges` `2` < 內容（卡/標籤）`3` —— 否則不透明面板會蓋掉 SVG 箭頭（圖1 踩過）。
- 多線接同一卡邊 → **接點等距平均分配**（例：machine._emit 右緣 4 線 y434/464/494/524,卡 y404–554 對稱）。

### 9.2 手繪蠟筆技法（核心）
原理（Rough.js／CSS-Tricks「Pencil Effect」）：**低頻位移＝手繪抖動不直；高頻噪聲侵蝕 alpha＝蠟筆紙面顆粒「粉感」**；筆畫要**夠粗**顆粒才不會把線打斷。單純位移（無顆粒）只會像波浪細線、不像蠟筆。

**兩個濾鏡**（放各圖 `.edges <defs>` 內）：
```svg
<!-- 線條/箭頭：userSpaceOnUse 大區域,避免細線位移被裁 -->
<filter id="crayon" filterUnits="userSpaceOnUse" x="-40" y="-40" width="2040" height="1410" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="2" seed="5" result="wob"/>
  <feDisplacementMap in="SourceGraphic" in2="wob" scale="5" xChannelSelector="R" yChannelSelector="G" result="line"/>
  <feTurbulence type="fractalNoise" baseFrequency="0.5 0.62" numOctaves="2" seed="9" result="grain"/>
  <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.9 -0.1" result="grainMask"/>
  <feComposite in="line" in2="grainMask" operator="in"/>
</filter>
<!-- 卡片外框：objectBoundingBox 區域隨卡縮放（效率高,不必每卡都開大 buffer）-->
<filter id="crayonEdge" x="-12%" y="-15%" width="124%" height="130%" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.014" numOctaves="2" seed="4" result="wob"/>
  <feDisplacementMap in="SourceGraphic" in2="wob" scale="4" result="ln"/>
  <feTurbulence type="fractalNoise" baseFrequency="0.5 0.6" numOctaves="2" seed="8" result="gr"/>
  <feColorMatrix in="gr" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.95 -0.05" result="grm"/>
  <feComposite in="ln" in2="grm" operator="in"/>
</filter>
```

**套用 — 箭頭線**（只套有 class 的邊：flow/hawk/async;**文字標籤不套**以保清晰;marker 隨 path 一起被濾、箭頭頭也手繪化）：
```css
.edges path, .edges line { stroke-width: 3.0; stroke-linecap: round; }
.edges .hawk { stroke-width: 3.8; }                      /* 主角環粗一階 */
.edges path[class] { filter: url(#crayon); stroke-opacity: 0.82; }
```

**套用 — 卡片外框**（`::before` 畫蠟筆框,**不動底色/文字**;`overflow:visible` 讓抖動外擴不被剪）：
```css
.card, .legend, .note, .chip, .group, .gate, .cmd { border-color: transparent; overflow: visible; }
.card::before, .legend::before, .note::before, .chip::before, .group::before, .gate::before, .cmd::before {
  content:""; position:absolute; inset:0; border-radius:inherit; pointer-events:none;
  border:2px solid var(--edge, var(--gray-edge));
  filter:url(#crayonEdge);
}
.card::before  { --edge: var(--c-edge, var(--gray-edge)); }
.legend::before,.note::before { --edge: var(--rule); }
.chip::before,.cmd::before    { --edge: var(--gray-edge); }
.group::before { --edge: var(--c-edge, var(--cyan-edge)); }
.gate::before  { --edge: var(--cyan-edge); }
```
- **內聯邊特殊卡（hero）**：把 inline `border:…solid <色>` 改 `border:…solid transparent; --c-edge:<色>`,讓 ::before 用該色畫蠟筆框、避免清邊＋蠟筆邊雙框。

### 9.2b 卡片填色 — Rough.js hachure 手繪上色
卡片**內部填色**用 **Rough.js**（vendored 本機 `presentation/rough.js`，~28KB）重畫成 hachure 斜線手工塗色（Excalidraw 同款，業界/得獎手繪標準做法）；**外框仍用 §9.2 的蠟筆 `::before`**（填色與框分工，使用者定版偏好）。
- 載入：`<script src="rough.js"></script>`（本機檔,免 CDN/SRI;headless 可載）。
- JS（`window load` 後）：每張 `.card` 讀 `getComputedStyle().backgroundColor` 當填色 → 設 `background:transparent` → 卡內插一張 `z-index:-1` 的 SVG，`rough.svg().path(roundedRectPath, { fillStyle:'hachure', hachureGap, fillWeight, hachureAngle, roughness, bowing, stroke:'none' })` 畫填色,墊在蠟筆框與文字之下。
- **關鍵**：`.card { isolation: isolate; }` 讓卡自成 stacking context,`z-index:-1` 填色才會墊在框後、又在頁面之上 —— **少了它,填色會掉到整卡後面消失**（踩過）。
- 參數：`hachureGap` 5.5（疏密=塗色密度）、`fillWeight` 1.4（塗色筆觸粗細）、`hachureAngle` 每卡 `-41+i%3*8`（角度微變,不呆板）、`roughness` 1.4 / `bowing` 1.4（手抖）。
- **退場**：無 JS → 卡片保留實色 + 蠟筆 ::before 框（graceful fallback）。
- 變體：`fillStyle` 可換 `cross-hatch`（交叉影線）/`zigzag`/`dots`/`sunburst`；密度調 `hachureGap`。
- **範圍＝所有 attribute 框**：選擇器 `.card, .legend, .note, .chip, .cmd, .gate, .group, .misalign, .subphase-tag, .tok, .sw` 全納入（各自 `isolation:isolate`）。**中性淺色框**（ivory/gray,`r≈g≈b`）填色壓深 ×0.95 + `node.opacity 0.6`（否則與頁同色看不見）；**色票 `.sw`** 用其**邊色**填、`hachureGap` 加密(2.2)、inset 1.6 幾乎填滿；**所有框的外框一律走 §9.2 蠟筆 `::before`**（含 `.sw`/`.tok`,JS 把該元素邊色寫進 inline `--edge` 讓框用對色;虛線框 `.misalign::before { border-style:dashed }`）；**`.group` 容器**也填(內層卡浮其上)。
> 來源：[Rough.js fill styles](https://roughjs.com/)、[RoughJS 演算法](https://shihn.ca/posts/2020/roughjs-algorithms/)、[draw.io rough 模式](https://www.drawio.com/blog/rough-style)（Excalidraw 同源技法）。

### 9.2c 手繪塗鴉標題（FIG.NN · 主題）
標題用**手繪塗鴉字 + 輕蠟筆 filter**（字型管「形」、filter 管「質」,別雙重扭形＝會糊）。
- **字型**：拉丁/數字 **Shantell Sans**（麥克筆變體字,Google Fonts @import,wght 800）；繁中 **清松手寫體⑧隨性**（`JasonHandwriting8.ttf`,vendored `presentation/jason8.ttf`,SIL OFL 可商用可嵌,Chromium 直吃 ttf 免轉 woff2,~8MB）；缺字 fallback **jf 粉圓 Huninn**（Google Fonts,圓潤、零缺字保底）。
  ```css
  @font-face { font-family:'Jason Scribble'; src:url('jason8.ttf') format('truetype'); font-display:swap; }
  .title { font-family:"Shantell Sans","Jason Scribble","Huninn",var(--font-display);
           font-size:33px; font-weight:800; filter:url(#crayonText); }
  ```
- **`#crayonText` filter**（套 `.title`,連 FIG 牌一起吃）：輕位移(`feDisplacementMap scale 2.6` 邊抖)+ 顆粒**只咬邊**(`feColorMatrix` alpha 末兩值 `-2.4 2.0`＝咬少→字實偏深;往 `-1.2 1.06` 走＝更碎更淡)。scale 小保易讀,**比卡片邊框 filter 更克制**。
- **FIG.NN 牌**：`.num` 字型也用塗鴉字（Shantell）、色 **深珊瑚 `#c25e39`**、框加粗 `2.5px`。
- **副標 `.subtitle` 維持乾淨 mono**（`JetBrains Mono`）做層次,不套手繪。
- 缺字驗證：清松逐字手寫,生僻字可能缺 → 上線前用**實際標題字串**渲染檢查(缺字會 fallback Huninn,不會 tofu)。
> 來源：[Shantell Sans (ArrowType)](https://github.com/arrowtype/shantell-sans)、[清松手寫體](https://github.com/jasonhandwriting/JasonHandwriting)、[jf 粉圓 Huninn](https://github.com/justfont/open-huninn-font)、[Codrops feDisplacementMap on text](https://tympanus.net/codrops/2019/02/12/svg-filter-effects-conforming-text-to-surface-texture-with-fedisplacementmap/)。

### 9.3 渲染 / 校驗
- 本機 Chrome 截圖：`chrome --headless --disable-gpu --force-device-scale-factor=2 --window-size=W,H --virtual-time-budget=15000 "--screenshot=out.png" "file:///…/NN.html"`（路徑空白用 `%20`）。
- ⚠ **`--headless=new` + `--screenshot` 本機不寫檔**（踩過）→ 用舊 `--headless`;濾鏡重,`--virtual-time-budget` 給足（≥12000）。
- 驗收：Read 截圖目視 + PowerShell `System.Drawing.Bitmap.GetPixel` 取樣關鍵點色值（如確認接點/底色 hex）。

### 9.4 強度旋鈕
- 更粉/顆粒重 → grain `feColorMatrix` alpha 末兩值更負（`0.9 -0.1` → `0.9 -0.15`）。
- 更彎/手繪重 → `feDisplacementMap scale`↑（線 5→8）。
- 更透 → `stroke-opacity`↓（0.82→0.65）。
- 更粗蠟筆桿 → `stroke-width` / 框 `border` ↑。
- 想要 Excalidraw「多筆 sketchy」而非「蠟筆顆粒」→ 改走 **Rough.js**（隨機化 bezier 控制點、每線多筆疊畫）。

> 來源：[Rough.js](https://roughjs.com/)、[CSS-Tricks: Pencil Effect](https://css-tricks.com/creating-a-pencil-effect-in-svg/)、[Here Dragons Abound](https://heredragonsabound.blogspot.com/2020/02/creating-pencil-effect-in-svg.html)、[Codrops feTurbulence](https://tympanus.net/codrops/2019/02/19/svg-filter-effects-creating-texture-with-feturbulence/)。

---

## 10. 檔案規劃（`resources/report/`）

```
resources/report/
├── design-system.md      ← 本 spec(單一事實來源)
├── report.html           ← (待建) 全本報告
├── tokens.css            ← (待建) 由 §2/§3 抽出的 :root,供 report.html @import
├── assets/
│   ├── fonts/            ← (待建) 離線 woff2(含思源 TC 子集)
│   └── doodles/          ← (待建) 各章 ch-N.svg
└── out/                  ← (待建,建議 gitignore) Chromium 產出 report.pdf
```
> 交付路徑與 git 收尾協議見 `project-01-workflow` skill；新增子目錄已登錄於 `resources/.claude/code_map.md`。
