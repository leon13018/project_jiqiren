/* ============================================================
   Glaze 點餐前端 — buildless（無打包 / 無框架 runtime）
   Phase 0：顯示鏡像 UI + demo 狀態切換器（假資料）。
   本檔分兩段：
     [元件層] 回傳 HTML 字串的小函式（取代 Glaze _ds_bundle 元件）
     [狀態層] App 物件（Task 3 補）—— 移植自設計 DCLogic
   事件一律用 data-act 委派（template-literal innerHTML 無法直接綁 onClick）。
   ============================================================ */

// ---- helpers ----
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dataAttrs = (data) => Object.entries(data || {}).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");

// ===== Glaze 元件（HTML 字串）=====

// 膠囊按鈕。variant: primary（海藍實心漸層）/ glass（玻璃）。children 以 icon+label 表示。
function Button({ label = "", icon = "", variant = "primary", size = "lg", block = false, act = "noop", data = {} }) {
  const h = size === "lg" ? 50 : 38;
  const bg = variant === "primary" ? "var(--brand-solid)" : "var(--glass-tint)";
  const fg = variant === "primary" ? "var(--text-on-brand)" : "var(--text-primary)";
  const border = variant === "primary" ? "none" : "0.5px solid var(--glass-border)";
  return `<button class="g-btn" data-act="${esc(act)}" ${dataAttrs(data)}
    style="display:inline-flex;align-items:center;justify-content:center;gap:8px;
    ${block ? "width:100%;" : ""}min-height:${h}px;padding:0 22px;border:${border};
    border-radius:var(--radius-capsule);background:${bg};color:${fg};font-family:var(--font-text);
    font-size:16px;font-weight:600;cursor:pointer;box-shadow:var(--glass-shadow);">
    ${icon ? `<i class="${esc(icon)}" style="font-size:18px;"></i>` : ""}${esc(label)}</button>`;
}

// 圓形玻璃圖示鈕（結帳 sheet 關閉用）。
function IconButton({ icon = "ph ph-x", label = "", act = "noop", data = {} }) {
  return `<button class="g-iconbtn" aria-label="${esc(label)}" data-act="${esc(act)}" ${dataAttrs(data)}
    style="width:40px;height:40px;flex:none;display:grid;place-items:center;border:0.5px solid var(--glass-border);
    border-radius:var(--radius-capsule);background:var(--glass-tint);color:var(--text-primary);cursor:pointer;">
    <i class="${esc(icon)}" style="font-size:18px;"></i></button>`;
}

// 計數徽章（購物車數量）。
function Badge(text, variant = "accent") {
  const bg = variant === "accent" ? "var(--accent)" : "var(--fill-2)";
  const fg = variant === "accent" ? "var(--text-on-brand)" : "var(--text-primary)";
  return `<span style="min-width:22px;height:22px;padding:0 7px;display:inline-grid;place-items:center;
    border-radius:999px;background:${bg};color:${fg};font-size:12px;font-weight:700;
    font-variant-numeric:tabular-nums;">${esc(text)}</span>`;
}

// 數量加減器。id 用來在委派層辨識是哪個商品列；size lg=44 / sm=32。
function QuantityStepper({ id, value = 0, size = "lg" }) {
  const h = size === "lg" ? 44 : 32;
  const ic = size === "lg" ? 18 : 14;
  const btn = (sym, act) => `<button class="g-step" data-act="${act}" data-id="${esc(id)}"
    style="width:${h}px;height:${h}px;flex:none;display:grid;place-items:center;border:none;
    border-radius:var(--radius-capsule);background:var(--fill-2);color:var(--text-primary);cursor:pointer;">
    <i class="ph-bold ph-${sym}" style="font-size:${ic}px;"></i></button>`;
  return `<div style="display:inline-flex;align-items:center;gap:8px;">
    ${btn("minus", "dec")}
    <span style="min-width:28px;text-align:center;font-family:var(--font-display);font-weight:700;
      font-variant-numeric:tabular-nums;">${value}</span>
    ${btn("plus", "inc")}</div>`;
}

// 廣告輪播卡。只渲染目前 index（計時推進由 startAdAutoplay 換 outerHTML）。
function AdBanner({ slides, index = 0, height = 240 }) {
  const s = slides[index % slides.length];
  return `<div class="g-ad anim-drift" data-ad
    style="position:relative;height:${height}px;border-radius:var(--radius-2xl);overflow:hidden;
    background:${s.tone};background-size:220% 220%;display:flex;flex-direction:column;justify-content:flex-end;
    padding:28px;color:#fff;box-shadow:var(--glass-shadow);">
    <span aria-hidden="true" style="position:absolute;inset:0;background:var(--droplet-sheen);"></span>
    <span style="position:relative;font-size:12px;font-weight:700;letter-spacing:1.5px;opacity:.9;">${esc(s.eyebrow)}</span>
    <h3 style="position:relative;margin:6px 0 4px;font-family:var(--font-display);font-size:30px;font-weight:800;">${esc(s.title)}</h3>
    <p style="position:relative;margin:0;font-size:15px;opacity:.92;max-width:70%;">${esc(s.subtitle)}</p></div>`;
}
