# WebUI Phase 0 — Pi 玻璃效能切片 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **驗證方式特例**：這是**靜態前端**，沒有 pytest 單元測試。每個 task 的「驗證」是**視覺/手動**（瀏覽器開頁、切狀態、Pi 上量 fps），不是 `python -m pytest`。本專案 Stop hook 的 pytest 守衛只在改 `sales/*.py` 時觸發；Phase 0 不碰 `.py`，不受其管。

**Goal:** 把 Claude Design 的「In-Person Ordering」玻璃點餐頁重建成 buildless 靜態網站，搬上 Raspberry Pi 4 接 HDMI 量測 fps，確認 Liquid Glass 效果在真機上流暢可用，再決定是否投入後端串接（Phase 1+）。

**Architecture:** 純靜態 `myProgram/webui/`（無打包、無框架 runtime）。一個 `index.html` + 一支 `app.js`：state/購物車/QR 邏輯**逐字移植**自設計檔內嵌的 `DCLogic`（本來就是純 JS），`render()` 以 template-literal 重畫 DOM 取代 Claude Design 的 `<x-dc>` 模板 runtime；5 個 Glaze 元件（AdBanner / QuantityStepper / Button / Badge / IconButton）重寫成回傳 HTML 字串的小函式 + 事件委派。設計的 6 個 token CSS 沿用（`fonts.css` 因指向未打包的 SF Pro 而重寫）。用 Python stdlib `http.server` 服務，零新依賴。

**Tech Stack:** HTML5 + CSS（Glaze tokens）+ 原生 ES JS（無 bundler / 無 React runtime）；Phosphor Icons（在地化）；Inter + Noto Sans TC（在地化字型）；`python3.11 -m http.server`（Pi 服務）。

## Global Constraints

（每個 task 都隱含遵守這些；數值逐字取自決策與專案紅線）

- **Buildless**：不得引入 npm / bundler / 任何 build step。**Windows 本機禁 `npm`/`pip`/`apt` 安裝**（hook 擋的紅線）；靜態資產用 `Invoke-WebRequest`/`curl` 下載即可（抓檔 ≠ 裝依賴）。
- **落點 `myProgram/webui/`**：因 `sync_pi.ps1` 只同步 `myProgram/`，前端放此處才會自動部署到 Pi。
- **UI 文案一律繁體中文**（產出物紅線）。
- **不碰 `vendor/`、不改 `sales/*.py` 或任何 `myProgram/*.py`**（Phase 0 純前端；不觸發 SDD）。
- **離線可跑**：Phosphor + Inter + Noto Sans TC 在地化到 `webui/assets/`；**不打包 SF Pro**（專利 + 60 個 .otf binary + Pi 用不到）。中文走 Noto Sans TC、英數走 Inter。
- **零新 Python 依賴**：Pi 端用 `python3.11 -m http.server` 服務（stdlib）。**不需 pineedtodo**（無安裝動作）。
- **互動模式 A（顯示鏡像）**：Phase 0 先用設計內建假資料 + demo 狀態切換器；真資料/語音事件留 Phase 2。觸控元件保留可動（之後當備援）。
- **平台**：Pi 4 + Chromium（GPU 受限——backdrop-filter blur 是 fps 風險，正是本階段要量的）。
- **流程**：myProgram/ 改動 → 走 **worktree**；新增 `webui/` 目錄 → 更新 `myProgram/.claude/code_map.md`。`git add` 明列檔名，**禁 `-A`/`.`**。

---

## File Structure

```
myProgram/webui/
├── index.html              # 單頁：<head> 載 tokens+app.css+字型+phosphor；<body><div id="app"></div>
├── app.css                 # 頁面專屬樣式（背景光暈 keyframes、wf-fade/wf-sheet、版面 grid）
├── app.js                  # state + 移植自 DCLogic 的邏輯 + render() + 5 元件 + 事件委派 + AdBanner 計時
├── tokens/                 # 沿用設計（fonts.css 重寫，其餘照搬）
│   ├── colors.css
│   ├── effects.css
│   ├── fonts.css           # ← 重寫：Inter + Noto Sans TC @font-face（移除 SF Pro）
│   ├── motion.css
│   ├── spacing.css
│   └── typography.css      # ← 微調：font 堆疊插入 "Noto Sans TC"
└── assets/
    ├── fonts/              # Inter + Noto Sans TC woff2（在地化）
    └── phosphor/           # Phosphor regular/bold/fill 的 css + woff2（在地化）
```

各檔職責邊界清楚：`tokens/` = 設計語彙（穩定）；`app.css` = 本頁版面/動畫；`app.js` = 狀態+渲染+互動。改版面動 `app.css`、改邏輯動 `app.js`、改設計語彙動 `tokens/`。

---

## Task 1: Scaffold `webui/` + 沿用 tokens + 在地化字型/圖示

**Files:**
- Create: `myProgram/webui/tokens/colors.css`, `effects.css`, `motion.css`, `spacing.css`, `typography.css`（搬運）
- Create: `myProgram/webui/tokens/fonts.css`（重寫）
- Create: `myProgram/webui/assets/fonts/*.woff2`、`myProgram/webui/assets/phosphor/*`（下載）
- Create: `myProgram/webui/index.html`（最小骨架，本 task 只驗證 tokens/字型生效）

**Interfaces:**
- Produces: `webui/tokens/*.css` 提供全套 `--bg-base / --text-* / --accent / --glass-* / --blur-* / --fluid-* / --radius-* / --font-*` 變數與 `.glass*`、`.anim-*`、`.t-*` utility class，供 Task 2/3 使用。字型 family：`"Inter"`（英數）、`"Noto Sans TC"`（中文）、`"Phosphor"`/`ph` class（圖示）。

- [ ] **Step 1: 建目錄並搬運 5 個照用 token CSS**

從 Claude Design 專案（`projectId 12b7a4eb-6b04-4c45-ac0c-124de6d9a262`，路徑前綴 `_ds/glaze-design-system-9579f26a-23b1-444a-b6a7-da5f32a50af8/tokens/`）取下列 5 檔，**內容一字不改**寫入 `myProgram/webui/tokens/`：`colors.css`、`effects.css`、`motion.css`、`spacing.css`、`typography.css`。（本對話已 `DesignSync get_file` 取得全文，可直接 Write；新 session 執行則重新 `DesignSync get_file`。）

- [ ] **Step 2: 重寫 `tokens/fonts.css`（移除 SF Pro，改 Inter + Noto Sans TC）**

原 `fonts.css` 全是指向 `../fonts/SF-Pro-*.otf` 的 `@font-face`（未打包）。整檔換成在地化字型宣告：

```css
/* GLAZE · FONTS — buildless 在地化版（取代未打包的 SF Pro）
   英數 → Inter；中文 → Noto Sans TC。兩者皆 self-host 於 ../assets/fonts。 */

/* Inter（拉丁，UI/標題/數字主力） */
@font-face { font-family:"Inter"; font-style:normal; font-weight:400; font-display:swap;
  src:url("../assets/fonts/Inter-Regular.woff2") format("woff2"); }
@font-face { font-family:"Inter"; font-style:normal; font-weight:500; font-display:swap;
  src:url("../assets/fonts/Inter-Medium.woff2") format("woff2"); }
@font-face { font-family:"Inter"; font-style:normal; font-weight:600; font-display:swap;
  src:url("../assets/fonts/Inter-SemiBold.woff2") format("woff2"); }
@font-face { font-family:"Inter"; font-style:normal; font-weight:700; font-display:swap;
  src:url("../assets/fonts/Inter-Bold.woff2") format("woff2"); }
@font-face { font-family:"Inter"; font-style:normal; font-weight:800; font-display:swap;
  src:url("../assets/fonts/Inter-ExtraBold.woff2") format("woff2"); }

/* Noto Sans TC（繁中） */
@font-face { font-family:"Noto Sans TC"; font-style:normal; font-weight:400; font-display:swap;
  src:url("../assets/fonts/NotoSansTC-Regular.woff2") format("woff2"); }
@font-face { font-family:"Noto Sans TC"; font-style:normal; font-weight:500; font-display:swap;
  src:url("../assets/fonts/NotoSansTC-Medium.woff2") format("woff2"); }
@font-face { font-family:"Noto Sans TC"; font-style:normal; font-weight:700; font-display:swap;
  src:url("../assets/fonts/NotoSansTC-Bold.woff2") format("woff2"); }
@font-face { font-family:"Noto Sans TC"; font-style:normal; font-weight:800; font-display:swap;
  src:url("../assets/fonts/NotoSansTC-ExtraBold.woff2") format("woff2"); }
@font-face { font-family:"Noto Sans TC"; font-style:normal; font-weight:900; font-display:swap;
  src:url("../assets/fonts/NotoSansTC-Black.woff2") format("woff2"); }
```

- [ ] **Step 3: 微調 `tokens/typography.css` 的 font 堆疊插入 Noto Sans TC**

原堆疊無 CJK 字型，中文會掉系統字。把三個變數的 fallback 鏈插入 `"Noto Sans TC"`（放在 `"Inter"` 之後即可，Inter 無中文字符會自動 fall through 到 Noto）：

```css
  --font-text: "SF Pro Text", "SF Pro", -apple-system, BlinkMacSystemFont,
    "Inter", "Noto Sans TC", system-ui, "Helvetica Neue", sans-serif;
  --font-display: "SF Pro Display", "SF Pro", -apple-system, BlinkMacSystemFont,
    "Inter", "Noto Sans TC", system-ui, "Helvetica Neue", sans-serif;
  --font-rounded: "SF Pro Rounded", ui-rounded, -apple-system,
    BlinkMacSystemFont, "Inter", "Noto Sans TC", system-ui, sans-serif;
```
（保留 SF Pro 名稱無害：Pi 上不存在會自動跳過。）

- [ ] **Step 4: 在地化下載字型與 Phosphor 圖示**

在 worktree 根用 PowerShell 抓檔（**抓靜態檔，非裝依賴**）。Inter / Noto Sans TC 取 woff2，Phosphor 取 regular/bold/fill 三套 `style.css` + 其引用的 `Phosphor*.woff2`。範例（實際 URL 以 unpkg / google-webfonts-helper 對應檔為準，抓不到時 fallback 見 Step 6 註記）：

```powershell
$ww = "myProgram/webui/assets"
New-Item -ItemType Directory -Force "$ww/fonts","$ww/phosphor" | Out-Null
# Phosphor（與設計 CDN 同版 2.1.1）
foreach ($w in "regular","bold","fill") {
  Invoke-WebRequest "https://unpkg.com/@phosphor-icons/web@2.1.1/src/$w/style.css" -OutFile "$ww/phosphor/$w.css"
  Invoke-WebRequest "https://unpkg.com/@phosphor-icons/web@2.1.1/src/$w/Phosphor$(if($w -ne 'regular'){"-$($w.Substring(0,1).ToUpper()+$w.Substring(1))"}).woff2" -OutFile "$ww/phosphor/Phosphor-$w.woff2" -ErrorAction SilentlyContinue
}
# 把各 css 的 url(...) 改指向同目錄已存檔名（離線生效關鍵；否則仍指原檔名 Phosphor.woff2 → 圖示靜默失效）
foreach ($w in "regular","bold","fill") {
  $css = "$ww/phosphor/$w.css"
  (Get-Content $css -Raw) -replace 'url\([^)]*Phosphor[^)]*\.woff2\)', "url(./Phosphor-$w.woff2)" | Set-Content $css -NoNewline
}
```
Inter / Noto Sans TC 的 woff2 從 google-webfonts-helper（`gwfh.mranftl.com`）下載對應 weight，存入 `$ww/fonts/`，檔名對齊 Step 2 的 `src`。

- [ ] **Step 5: 寫最小 `index.html` 載入鏈驗證**

```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>機器人點餐</title>
<link rel="stylesheet" href="tokens/fonts.css">
<link rel="stylesheet" href="tokens/colors.css">
<link rel="stylesheet" href="tokens/typography.css">
<link rel="stylesheet" href="tokens/spacing.css">
<link rel="stylesheet" href="tokens/effects.css">
<link rel="stylesheet" href="tokens/motion.css">
<link rel="stylesheet" href="assets/phosphor/regular.css">
<link rel="stylesheet" href="assets/phosphor/bold.css">
<link rel="stylesheet" href="assets/phosphor/fill.css">
<style>body{margin:0;background:var(--bg-base);color:var(--text-primary);font-family:var(--font-text);}</style>
</head>
<body>
  <h1 class="t-hero" style="font-family:var(--font-display)">機器人點餐 Glaze</h1>
  <p class="t-body">冰紅茶 NT$27 · 刮刮樂 NT$180 <i class="ph-fill ph-drop"></i></p>
</body>
</html>
```

- [ ] **Step 6: 手動驗證（瀏覽器）**

在 worktree 根開臨時服務並開瀏覽器：
```powershell
python -m http.server 8000 --directory myProgram/webui
```
開 `http://localhost:8000`，**預期**：純黑背景、白字；「機器人點餐 Glaze」用粗體顯示；**中文不是豆腐字（Noto Sans TC 生效）**；水滴 Phosphor 圖示出現。
> 抓字型/圖示失敗的 fallback：暫時改回設計用的 CDN（`unpkg` Phosphor + Google Fonts Noto Sans TC/Inter）跑完 Phase 0 fps 測試，在地化留待後續補（fps 與資產來源無關）。

- [ ] **Step 7: Commit**

```powershell
git add myProgram/webui/tokens/colors.css myProgram/webui/tokens/effects.css myProgram/webui/tokens/fonts.css myProgram/webui/tokens/motion.css myProgram/webui/tokens/spacing.css myProgram/webui/tokens/typography.css myProgram/webui/index.html myProgram/webui/assets
git commit -m "feat(webui): scaffold buildless webui + vendor Glaze tokens & fonts"
```

---

## Task 2: Buildless render harness + 5 個 Glaze 元件

**Files:**
- Create: `myProgram/webui/app.js`（本 task 寫元件 + render 骨架）
- Create: `myProgram/webui/app.css`（元件/版面樣式）
- Create: `myProgram/webui/_components_probe.html`（暫時的元件驗證頁，本 task 末刪除或留作 dev 工具）

**Interfaces:**
- Consumes: Task 1 的 token 變數與 `ph` 圖示 class。
- Produces: 全域函式 `Button(opts)`, `IconButton(opts)`, `Badge(text,variant)`, `QuantityStepper(opts)`, `AdBanner(opts)` — 各回傳 HTML 字串；事件委派 `bindEvents(rootEl)`；AdBanner 計時 `startAdAutoplay(rootEl)`。元件以 `data-act="<name>"` + `data-*` 攜帶意圖，由委派層解讀（template-literal 無法直接綁 onClick）。

- [ ] **Step 1: 寫元件函式（回傳 HTML 字串）到 `app.js`**

```js
// === Glaze 元件（buildless：回傳 HTML 字串，事件用 data-act 委派）===
const esc = (s) => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

function Button({ label, icon, variant = "primary", size = "lg", block = false, act, data = {} }) {
  const h = size === "lg" ? 50 : 38;
  const bg = variant === "primary" ? "var(--brand-solid, var(--accent))" : "var(--glass-tint)";
  const fg = variant === "primary" ? "var(--text-on-brand)" : "var(--text-primary)";
  const dataAttrs = Object.entries(data).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");
  return `<button class="g-btn" data-act="${esc(act)}" ${dataAttrs}
    style="display:inline-flex;align-items:center;justify-content:center;gap:8px;
    ${block ? "width:100%;" : ""}min-height:${h}px;padding:0 20px;border:0.5px solid var(--glass-border);
    border-radius:var(--radius-capsule);background:${bg};color:${fg};font-family:var(--font-text);
    font-size:16px;font-weight:600;cursor:pointer;box-shadow:var(--glass-shadow);">
    ${icon ? `<i class="${esc(icon)}" style="font-size:18px;"></i>` : ""}${esc(label)}</button>`;
}

function IconButton({ icon, label, act, data = {} }) {
  const dataAttrs = Object.entries(data).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");
  return `<button class="g-iconbtn" aria-label="${esc(label)}" data-act="${esc(act)}" ${dataAttrs}
    style="width:40px;height:40px;display:grid;place-items:center;border:0.5px solid var(--glass-border);
    border-radius:var(--radius-capsule);background:var(--glass-tint);color:var(--text-primary);cursor:pointer;">
    <i class="${esc(icon)}" style="font-size:18px;"></i></button>`;
}

function Badge(text, variant = "accent") {
  const bg = variant === "accent" ? "var(--accent)" : "var(--fill-2)";
  const fg = variant === "accent" ? "var(--text-on-brand)" : "var(--text-primary)";
  return `<span style="min-width:22px;height:22px;padding:0 7px;display:inline-grid;place-items:center;
    border-radius:999px;background:${bg};color:${fg};font-size:12px;font-weight:700;
    font-variant-numeric:tabular-nums;">${esc(text)}</span>`;
}

// id = 用來在 data 裡標識是哪個商品列；size lg=44 / sm=32
function QuantityStepper({ id, value, min = 0, max = 50, size = "lg" }) {
  const h = size === "lg" ? 44 : 32;
  const btn = (sym, act) => `<button class="g-step" data-act="${act}" data-id="${esc(id)}"
    style="width:${h}px;height:${h}px;flex:none;display:grid;place-items:center;border:none;
    border-radius:var(--radius-capsule);background:var(--fill-2);color:var(--text-primary);cursor:pointer;">
    <i class="ph-bold ph-${sym}" style="font-size:${size === 'lg' ? 18 : 14}px;"></i></button>`;
  return `<div style="display:inline-flex;align-items:center;gap:8px;">
    ${btn("minus", "dec")}
    <span style="min-width:28px;text-align:center;font-family:var(--font-display);font-weight:700;
      font-variant-numeric:tabular-nums;">${value}</span>
    ${btn("plus", "inc")}</div>`;
}

// slides: [{eyebrow,title,subtitle,cta,tone}]；只渲染目前 index，計時由 startAdAutoplay 推進
function AdBanner({ slides, index = 0, height = 240 }) {
  const s = slides[index % slides.length];
  return `<div class="g-ad anim-drift" data-ad
    style="position:relative;height:${height}px;border-radius:var(--radius-2xl);overflow:hidden;
    background:${s.tone};background-size:220% 220%;display:flex;flex-direction:column;justify-content:flex-end;
    padding:28px;color:#fff;box-shadow:var(--glass-shadow);">
    <span aria-hidden="true" style="position:absolute;inset:0;background:var(--droplet-sheen);"></span>
    <span style="position:relative;font-size:12px;font-weight:700;letter-spacing:1.5px;opacity:.9;">${esc(s.eyebrow)}</span>
    <h3 style="position:relative;margin:6px 0 4px;font-family:var(--font-display);font-size:30px;font-weight:800;">${esc(s.title)}</h3>
    <p style="position:relative;margin:0;font-size:15px;opacity:.92;">${esc(s.subtitle)}</p></div>`;
}
```

- [ ] **Step 2: 寫 `app.css`（背景光暈 + 過場動畫 + 版面）**

把設計 `In-Person Ordering.dc.html` `<helmet>` 內 `<style>` 的 keyframes 與背景光暈搬出來成檔（`glaze-bg-drift`、`wf-sheet-up`、`wf-fade-in`、`.wf-fade`、`.wf-sheet`、`prefers-reduced-motion` gate），加上頁面 grid 版面：

```css
/* 背景固定光暈（OKLCH） */
.bg-glows { position:fixed; inset:0; pointer-events:none; z-index:0;
  background:
    radial-gradient(48% 38% at 12% 8%, oklch(0.62 0.18 300 / 0.26), transparent 70%),
    radial-gradient(46% 40% at 92% 16%, oklch(0.72 0.16 28 / 0.22), transparent 72%),
    radial-gradient(60% 50% at 70% 100%, oklch(0.70 0.13 200 / 0.20), transparent 72%);
  animation: glaze-bg-drift 24s var(--ease-standard) infinite; }
@keyframes glaze-bg-drift { 0%{transform:translate(0,0)} 50%{transform:translate(-3%,2%)} 100%{transform:translate(0,0)} }
@keyframes wf-sheet-up { from{transform:translateY(100%)} to{transform:translateY(0)} }
@keyframes wf-fade-in { from{opacity:0} to{opacity:1} }
.wf-fade { animation: wf-fade-in var(--dur-base,.28s) var(--ease-standard,ease) both; }
.wf-sheet { animation: wf-sheet-up var(--dur-slow,.42s) var(--ease-fluid,cubic-bezier(.4,0,.2,1)) both; }
.body-grid { position:relative; z-index:1; display:grid; grid-template-columns:minmax(0,1fr) 380px;
  gap:28px; max-width:1280px; margin:0 auto; padding:24px 28px 88px; }
@media (prefers-reduced-motion: reduce) {
  .wf-fade,.wf-sheet,.bg-glows,.anim-drift { animation:none !important; }
}
```

- [ ] **Step 3: 寫元件驗證頁 `_components_probe.html`**

```html
<!DOCTYPE html><html lang="zh-Hant"><head><meta charset="utf-8">
<link rel="stylesheet" href="tokens/fonts.css"><link rel="stylesheet" href="tokens/colors.css">
<link rel="stylesheet" href="tokens/typography.css"><link rel="stylesheet" href="tokens/spacing.css">
<link rel="stylesheet" href="tokens/effects.css"><link rel="stylesheet" href="tokens/motion.css">
<link rel="stylesheet" href="assets/phosphor/regular.css"><link rel="stylesheet" href="assets/phosphor/bold.css">
<link rel="stylesheet" href="assets/phosphor/fill.css"><link rel="stylesheet" href="app.css">
<style>body{background:var(--bg-base);color:var(--text-primary);font-family:var(--font-text);padding:40px;display:flex;flex-direction:column;gap:24px;}</style>
</head><body><div id="probe"></div>
<script src="app.js"></script>
<script>
  document.getElementById("probe").innerHTML = [
    Button({label:"加入購物車", icon:"ph-bold ph-plus", act:"noop"}),
    Button({label:"結帳 · NT$234", icon:"ph-bold ph-qr-code", variant:"primary", act:"noop"}),
    IconButton({icon:"ph ph-x", label:"關閉", act:"noop"}),
    Badge("3"),
    QuantityStepper({id:"x", value:2}),
    AdBanner({slides:[{eyebrow:"限時優惠",title:"冰紅茶　全面 9 折",subtitle:"透心涼，現場掃碼即享優惠價。",cta:"立即點購",tone:"var(--fluid-warm)"}]}),
  ].join('<div style="height:8px"></div>');
</script></body></html>
```

- [ ] **Step 4: 手動驗證（瀏覽器）**

```powershell
python -m http.server 8000 --directory myProgram/webui
```
開 `http://localhost:8000/_components_probe.html`，**預期**：兩顆膠囊按鈕（含圖示、主按鈕海藍底）、圓形關閉鈕、紅/藍 Badge、+/− 數量器顯示「2」、一張會緩慢漂移漸層的廣告卡（繁中標題）。文字皆繁中無豆腐。

- [ ] **Step 5: Commit**

```powershell
git add myProgram/webui/app.js myProgram/webui/app.css myProgram/webui/_components_probe.html
git commit -m "feat(webui): buildless Glaze components + page styles"
```

---

## Task 3: 點餐頁主體 + 移植 DCLogic 狀態 + 五狀態 demo 切換器

**Files:**
- Modify: `myProgram/webui/app.js`（補 state/邏輯/render/事件委派/啟動）
- Modify: `myProgram/webui/index.html`（換成正式 `<div id="app">` + `<script src="app.js">`）

**Interfaces:**
- Consumes: Task 2 的 5 元件函式 + Task 1 tokens。
- Produces: 一個 `App` 物件含 `state`、`products()/ads()/fmt()/totalOf()/setQty()/openCheckout()/closeOverlay()/placeOrder()/finishOrder()/exitStandby()/setView()/qrCells()`（**逐字移植自設計 `DCLogic`**）+ `render()`（重畫 `#app`）+ `bindEvents()`（委派 `data-act`）。

- [ ] **Step 1: 移植 DCLogic 純邏輯到 `app.js`**

從設計檔 `<script type="text/x-dc">` 內 `class Component extends DCLogic` **逐字搬**下列方法（皆純 JS、無 DC 依賴）：`products()`、`ads()`、`fmt()`、`totalOf(cart)`、`setQty(id,n)`、`openCheckout/closeOverlay/placeOrder/finishOrder/exitStandby`、`setView(v)`、`qrCells(seed)`。改寫成一個普通物件 `App`，`state` 初始 = `{ cart:{bingcha:2,guagua:1}, overlay:null, standby:false, paidTotal:0, reviewOpen:false }`；`setState(patch)` 改成 `Object.assign(this.state, patch); this.render();`（取代 React 式 setState）。`setQty` 等內部呼叫 `this.setState(...)` 維持原樣即可。

```js
const App = {
  state: { cart: { bingcha: 2, guagua: 1 }, overlay: null, standby: false, paidTotal: 0, reviewOpen: false },
  setState(patch) {
    const next = typeof patch === "function" ? patch(this.state) : patch;
    Object.assign(this.state, next);
    this.render();
  },
  // ↓↓↓ 以下 products/ads/fmt/totalOf/setQty/openCheckout/closeOverlay/placeOrder/
  //     finishOrder/exitStandby/setView/qrCells 逐字移植自設計 DCLogic（內容見設計檔）
  products() { return [
    { id:"bingcha", name:"冰紅茶", priceNow:27, priceOrig:30, unit:"瓶", icon:"ph-drop",
      tone:"linear-gradient(140deg, oklch(0.62 0.13 52), oklch(0.43 0.10 35))" },
    { id:"guagua", name:"刮刮樂", priceNow:180, priceOrig:200, unit:"張", icon:"ph-ticket",
      tone:"linear-gradient(140deg, oklch(0.72 0.17 28), oklch(0.60 0.16 332))" } ]; },
  // ... ads(), fmt(), totalOf(), setQty(), overlay handlers, setView(), qrCells() 同設計檔逐字 ...
};
```
> 規則：邏輯方法**不得改動行為**，只把 `this.setState(updater)` 的語意保留（上面 setState 同時支援物件與 updater 函式）。

- [ ] **Step 2: 寫 `render()`（template-literal 重畫，取代 `<x-dc>` 模板）**

把設計 `<x-dc>` 內的版面**逐區塊轉成字串模板**：`{{ x }}` → `${...}`、`<sc-if value>` → JS 三元/條件串接、`<sc-for list as=row>` → `.map().join("")`、`<x-import ...Button>` → `Button({...})` 等元件呼叫。`render()` 依 `state` 算出 `renderVals()`（移植自設計同名方法）再組 `#app` 的 innerHTML：top bar、body grid（AdBanner + 2 商品卡 + 購物車 rail）、結帳 sheet、致謝、待機、demo 切換器。組完呼叫 `bindEvents()` 與 `startAdAutoplay()`。

```js
App.render = function () {
  const v = this.renderVals();           // 移植自設計 renderVals()，回傳畫面所需值
  const app = document.getElementById("app");
  app.innerHTML = `
    <div class="bg-glows" aria-hidden="true"></div>
    ${TopBar(v)}
    <div class="body-grid">${Menu(v)}${CartRail(v)}</div>
    ${v.showCheckout ? CheckoutSheet(v) : ""}
    ${v.showThankyou ? ThankYou(v) : ""}
    ${v.standby ? Standby(v) : ""}
    ${v.showReview ? ReviewSwitcher(v) : ""}`;
  bindEvents(app);
  startAdAutoplay(app, v);
};
```
（`TopBar/Menu/CartRail/CheckoutSheet/ThankYou/Standby/ReviewSwitcher` 為本 step 內定義的字串模板函式，markup 一對一搬自設計對應 `data-screen-label` 區塊；QR 用 `v.qrCells.map(c => '<span style="background:'+c.bg+'"></span>').join("")` 鋪 21×21 grid。）

- [ ] **Step 3: 寫 `bindEvents()` 事件委派 + `startAdAutoplay()`**

```js
function bindEvents(root) {
  root.onclick = (e) => {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act, id = t.dataset.id;
    const cur = App.state.cart[id] || 0;
    switch (act) {
      case "add":      App.setQty(id, 1); break;
      case "inc":      App.setQty(id, cur + 1); break;
      case "dec":      App.setQty(id, cur - 1); break;
      case "checkout": App.openCheckout(); break;
      case "close":    App.closeOverlay(); break;
      case "place":    App.placeOrder(); break;
      case "finish":   App.finishOrder(); break;
      case "exitStandby": App.exitStandby(); break;
      case "toggleReview": App.setState(s => ({ reviewOpen: !s.reviewOpen })); break;
      case "setView":  App.setView(t.dataset.view); App.setState({ reviewOpen: false }); break;
    }
  };
}
let _adTimer = null;
function startAdAutoplay(root, v) {
  if (_adTimer) clearInterval(_adTimer);
  if (!v.ads || v.ads.length < 2) return;
  let i = 0;
  _adTimer = setInterval(() => {
    i = (i + 1) % v.ads.length;
    const el = root.querySelector("[data-ad]");
    if (el) el.outerHTML = AdBanner({ slides: v.ads, index: i });
  }, 5000);
}
document.addEventListener("DOMContentLoaded", () => App.render());
```
（結帳 sheet 的遮罩點擊關閉、`stopPropagation` 等以 `data-act="close"` 掛在遮罩、sheet 本體 `onclick` 擋冒泡實作。）

- [ ] **Step 4: 換正式 `index.html`**

把 Task 1 的 `<body>` 內容換成：
```html
<body>
  <div id="app"></div>
  <link rel="stylesheet" href="app.css">
  <script src="app.js"></script>
</body>
```
（其餘 `<head>` 載入鏈不變。）

- [ ] **Step 5: 手動驗證（瀏覽器，全狀態走查）**

```powershell
python -m http.server 8000 --directory myProgram/webui
```
開 `http://localhost:8000`，用左下「預覽狀態 · DEMO」切換器逐一驗證 5 態：
1. **含商品**：2 商品卡 + 購物車 2 列（冰紅茶×2、刮刮樂×1）、總計 NT$234、海藍結帳鈕
2. **空購物車**：「您的購物車是空的」
3. **結帳**：玻璃 sheet 升起、21×21 QR、「請掃碼付款」、總計
4. **完成**：「謝謝惠顧」+ 勾 + 已付款金額
5. **待機**：「歡迎光臨」全屏漸層
互動驗證：商品卡 +/− 改數量、總計跟著變；「結帳」開 sheet；「我已完成付款」→ 致謝；「完成」→ 清空回含商品態起點。**全程繁中、玻璃質感正常**。

- [ ] **Step 6: 刪 probe 頁 + Commit**

```powershell
Remove-Item myProgram/webui/_components_probe.html
git add myProgram/webui/app.js myProgram/webui/index.html
git rm myProgram/webui/_components_probe.html
git commit -m "feat(webui): ordering page + ported state logic + 5-state demo switcher"
```

---

## Task 4: 更新 code_map + Pi 部署 + fps 量測（去風險裁決）

**Files:**
- Modify: `myProgram/.claude/code_map.md`（登錄新 `webui/` 子目錄）

**Interfaces:**
- Consumes: Task 1-3 的完整 `webui/`。
- Produces: go/no-go 裁決（玻璃效果在 Pi 上是否流暢）+ 若不足的降規清單。

- [ ] **Step 1: 更新 `myProgram/.claude/code_map.md` 子目錄段**

在「## 子目錄」加一行：
```markdown
- `webui/` — 點餐網頁前端（buildless 靜態：`index.html`+`app.js`+`tokens/`+`assets/`；Glaze Liquid Glass 玻璃 UI；Phase 0 顯示鏡像，Pi 上 `python3.11 -m http.server` 服務）。
```

- [ ] **Step 2: Commit code_map + 收尾 merge（主 agent 收尾，見執行 handoff）**

```powershell
git add myProgram/.claude/code_map.md
git commit -m "docs(code_map): register myProgram/webui/ (Phase 0 ordering UI)"
```
（worktree 收尾 ff-merge + push 由主 agent 依 worktree.md 階段 4-5 執行；push 後 Stop hook 自動 sync 到 Pi。）

- [ ] **Step 3: Pi 端啟動服務（使用者操作）**

push+sync 完成後，請使用者在 Pi 終端執行（單行、絕對路徑）：
```bash
cd /home/pi/Desktop/project_jiqiren && python3.11 -m http.server 8000 --directory myProgram/webui
```
然後在 **Pi 接的 HDMI 螢幕**上用 Pi 桌面 Chromium 開 `http://localhost:8000`，全螢幕（F11）。
> 零新依賴：`http.server` 是 Python stdlib，故**不需 pineedtodo**。

- [ ] **Step 4: fps 量測（去風險核心驗證）**

在 Pi Chromium 開 DevTools（F12）→ ⋮ → More tools → Rendering → 勾「Frame Rendering Stats」（或 Performance 錄一段）。逐一操作：切待機↔點餐（漸層動畫）、開/關結帳 sheet（玻璃升起 + backdrop-blur）、按 +/− 數量。**記錄各操作 fps**。
- **預期判準**：互動與過場 **≥ 50 fps 順暢** → ✅ go，玻璃方向成立，進 Phase 1。
- **若 < 30 fps / 明顯卡頓** → 走 Step 5 降規再量。

- [ ] **Step 5（條件性）: 撐不住時的降規清單**

按成本/收益序試（每動一項重量 fps）：
1. 全站套 `prefers-reduced-motion` 等效：停 `.anim-drift` 與 `bg-glows` 動畫（保留靜態漸層）。
2. 結帳/致謝遮罩的 `backdrop-filter:blur()` 改為純不透明深色底（移除全屏二次模糊——最貴）。
3. 玻璃材質 blur 值調降：`--blur-thick 34→20`、`--blur-regular 20→14`。
4. 背景 `bg-glows` 三層 radial 減為一層、移除 `fixed` attachment。
逐項記錄 fps 與視覺取捨，產出「Pi 可接受的玻璃設定檔」結論。

- [ ] **Step 6: 裁決回報**

向使用者回報：(1) 各狀態/操作 fps 數據 (2) go / 需降規 / 降規後可接受 三選一裁決 (3) 若降規，列了哪些、視覺差異 (4) Phase 1 是否放行。**Iron Law 對應**：fps 數據是親自在 Pi 量到的真實輸出，非臆測。

---

## Self-Review

**1. Spec coverage（對照 Phase 0 範圍）**：
- buildless 靜態頁 → Task 2/3 ✅；落點 `myProgram/webui/` → 全 task ✅；token 沿用 + fonts 重寫 → Task 1 ✅；5 元件重寫 → Task 2 ✅；DCLogic 移植 + 五狀態 → Task 3 ✅；在地化字型/圖示（離線） → Task 1 ✅；http.server 服務 + Pi fps → Task 4 ✅；降規 fallback → Task 4 Step 5 ✅；code_map 更新 → Task 4 Step 1 ✅；worktree/git → 各 task commit + Task 4 收尾 ✅。無遺漏。

**2. Placeholder scan**：邏輯移植步驟（Task 3 Step 1）明列「逐字搬自設計 DCLogic」並附來源與初值，非 TBD；ported markup（Task 3 Step 2）給了明確轉換規則（`{{}}`→`${}`、`sc-if`→三元、`sc-for`→map）與來源區塊，非「similar to」。字型 URL 標了「以對應檔為準 + CDN fallback」因實際檔名依下載源而定，已給 fallback 路徑。

**3. Type consistency**：元件 API（`Button({label,icon,variant,size,block,act,data})`、`QuantityStepper({id,value,min,max,size})`、`Badge(text,variant)`、`AdBanner({slides,index,height})`、`IconButton({icon,label,act,data})`）在 Task 2 定義、Task 3 render 一致引用；事件 `data-act` 名（add/inc/dec/checkout/close/place/finish/exitStandby/toggleReview/setView）在 Task 2 元件與 Task 3 `bindEvents` 對齊；`App.setState` 同時支援物件與 updater，與移植邏輯內 `this.setState(s=>...)` 相容。

**4. 流程合規**：Phase 0 不改 `.py` → 不觸發 SDD（符 sdd.md 觸發表）；改 `myProgram/` → 走 worktree（符 worktree.md）；新增目錄 → 更新 myProgram code_map（符 pi-and-structure.md）；無新依賴 → 無 pineedtodo；`git add` 全程明列、無 `-A`。
