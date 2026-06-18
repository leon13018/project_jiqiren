/* ============================================================
   Glaze 點餐前端 — buildless（無打包 / 無框架 runtime）
   Phase 0：顯示鏡像 UI + demo 狀態切換器（假資料）。
   結構：
     [元件層]  回傳 HTML 字串的小函式（取代 Glaze _ds_bundle 元件）
     [狀態層]  App 物件 —— 邏輯逐字移植自設計 DCLogic（行為不變）
     [版面層]  TopBar/Menu/CartRail/... template 函式（搬自設計 <x-dc> 標記）
   事件一律用 data-act 委派（template-literal innerHTML 無法直接綁 onClick）。
   ============================================================ */

// ---- helpers ----
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const dataAttrs = (data) => Object.entries(data || {}).map(([k, v]) => `data-${k}="${esc(v)}"`).join(" ");

// ===== 元件層（HTML 字串）=====

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

function IconButton({ icon = "ph ph-x", label = "", act = "noop", data = {} }) {
  return `<button class="g-iconbtn" aria-label="${esc(label)}" data-act="${esc(act)}" ${dataAttrs(data)}
    style="width:40px;height:40px;flex:none;display:grid;place-items:center;border:0.5px solid var(--glass-border);
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

// 廣告輪播卡（對齊設計 AdBanner.jsx）：漂移漸層 + droplet sheen + 左側暗化漸層（文字可讀）
// + 內容（eyebrow/title/subtitle/CTA glass 鈕）+ 右下進度 pills（可點跳）。
// animate=true → 漸層 + 內容套 glaze-pop-in 過場（只在切換時，不在整頁 render 時）。
function AdBanner({ slides, index = 0, height = 240, animate = false }) {
  const n = slides.length || 1;
  const s = slides[index % n] || {};
  const tone = s.tone || "var(--fluid-spectrum)";
  const gradAnim = animate
    ? "glaze-drift 16s var(--ease-standard) infinite, glaze-pop-in var(--dur-slow) var(--ease-fluid)"
    : "glaze-drift 16s var(--ease-standard) infinite";
  const pills = n > 1
    ? `<div style="position:absolute;bottom:16px;right:20px;display:flex;gap:6px;z-index:2;">${slides.map((_, k) => `<button data-act="adGoto" data-idx="${k}" aria-label="廣告 ${k + 1}" style="width:${k === index ? 26 : 8}px;height:8px;padding:0;border:none;cursor:pointer;border-radius:var(--radius-capsule);background:${k === index ? "rgba(255,255,255,.95)" : "rgba(255,255,255,.45)"};transition:width var(--dur-base) var(--ease-fluid),background var(--dur-base) var(--ease-fluid);"></button>`).join("")}</div>`
    : "";
  return `<div class="g-ad" data-ad style="position:relative;height:${height}px;border-radius:var(--radius-2xl);overflow:hidden;border:0.5px solid var(--glass-border);box-shadow:var(--glass-shadow-raised);color:#fff;isolation:isolate;">
    <div class="anim-drift" style="position:absolute;inset:0;background:${tone};background-size:240% 240%;animation:${gradAnim};"></div>
    <span aria-hidden="true" style="position:absolute;inset:0;background:var(--droplet-sheen);"></span>
    <span aria-hidden="true" style="position:absolute;inset:0;background:linear-gradient(90deg,rgba(0,0,0,.42),rgba(0,0,0,0) 60%);"></span>
    <div class="${animate ? "anim-pop-in" : ""}" style="position:relative;z-index:1;height:100%;display:flex;flex-direction:column;justify-content:center;gap:10px;padding:0 clamp(24px,5%,56px);max-width:620px;">
      ${s.eyebrow ? `<span style="font-size:13px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;opacity:.85;">${esc(s.eyebrow)}</span>` : ""}
      <span style="font-family:var(--font-display);font-size:clamp(28px,4vw,44px);font-weight:800;line-height:1.04;letter-spacing:-0.8px;">${esc(s.title)}</span>
      ${s.subtitle ? `<span style="font-size:16px;opacity:.92;max-width:440px;">${esc(s.subtitle)}</span>` : ""}
      ${s.cta ? `<div style="margin-top:6px;">${Button({ label: s.cta, variant: "glass", size: "lg", act: "noop" })}</div>` : ""}
    </div>
    ${pills}
  </div>`;
}

// ===== 狀態層（移植自設計 DCLogic；setState 改為直接重畫）=====

const App = {
  state: { cart: { bingcha: 2, guagua: 1 }, overlay: null, standby: false, paidTotal: 0, reviewOpen: false, adIndex: 0 },

  setState(patch) {
    const next = typeof patch === "function" ? patch(this.state) : patch;
    Object.assign(this.state, next);
    this.render();
  },

  // ---- 以下 products/ads/fmt/totalOf/setQty/overlay handlers/setView/qrCells 逐字移植自設計 DCLogic ----
  products() {
    return [
      { id: "bingcha", name: "冰紅茶", priceNow: 27, priceOrig: 30, unit: "瓶", icon: "ph-drop", tone: "linear-gradient(140deg, oklch(0.62 0.13 52), oklch(0.43 0.10 35))" },
      { id: "guagua", name: "刮刮樂", priceNow: 180, priceOrig: 200, unit: "張", icon: "ph-ticket", tone: "linear-gradient(140deg, oklch(0.72 0.17 28), oklch(0.60 0.16 332))" },
    ];
  },

  ads() {
    return [
      { eyebrow: "限時優惠", title: "冰紅茶　全面 9 折", subtitle: "透心涼，現場掃碼即享優惠價。", cta: "立即點購", tone: "var(--fluid-warm)" },
      { eyebrow: "人氣推薦", title: "刮刮樂　刮出小確幸", subtitle: "張張有希望，試試今天的手氣。", cta: "加入購物車", tone: "var(--fluid-spectrum)" },
      { eyebrow: "現場限定", title: "機器人為您送上", subtitle: "點選商品、掃碼付款、輕鬆取貨。", cta: "開始點餐", tone: "var(--fluid-cool)" },
    ];
  },

  fmt(n) { return "NT$" + Math.round(n); },

  totalOf(cart) {
    const p = Object.fromEntries(this.products().map((x) => [x.id, x]));
    return Object.entries(cart).reduce((a, [id, q]) => a + (p[id] ? p[id].priceNow * q : 0), 0);
  },

  setQty(id, n) {
    this.setState((s) => {
      const cart = { ...s.cart };
      if (n <= 0) delete cart[id]; else cart[id] = Math.min(50, n);
      return { cart };
    });
  },

  openCheckout() { this.setState({ overlay: "checkout" }); },
  closeOverlay() { this.setState({ overlay: null }); },
  placeOrder() { this.setState((s) => ({ overlay: "thankyou", paidTotal: this.totalOf(s.cart) })); },
  finishOrder() { this.setState({ overlay: null, cart: {} }); },
  exitStandby() { this.setState({ standby: false }); },
  toggleReview() { this.setState((s) => ({ reviewOpen: !s.reviewOpen })); },

  // 廣告切換：只換 [data-ad] 元素（不整頁 render），animate=true 觸發 pop-in 過場
  showAd(k) {
    this.state.adIndex = k;
    const el = document.querySelector("[data-ad]");
    if (el) el.outerHTML = AdBanner({ slides: this.ads(), index: k, height: 240, animate: true });
  },

  setView(v) {
    if (v === "filled") this.setState({ cart: { bingcha: 2, guagua: 1 }, overlay: null, standby: false });
    else if (v === "empty") this.setState({ cart: {}, overlay: null, standby: false });
    else if (v === "checkout") this.setState((s) => ({ cart: Object.keys(s.cart).length ? s.cart : { bingcha: 2, guagua: 1 }, overlay: "checkout", standby: false }));
    else if (v === "placed") this.setState((s) => { const c = Object.keys(s.cart).length ? s.cart : { bingcha: 2, guagua: 1 }; return { overlay: "thankyou", standby: false, paidTotal: this.totalOf(c) }; });
    else if (v === "standby") this.setState({ overlay: null, standby: true });
  },

  qrCells(seed) {
    let h = 2166136261;
    for (let i = 0; i < seed.length; i++) { h ^= seed.charCodeAt(i); h = Math.imul(h, 16777619); }
    const rand = () => { h = Math.imul(h ^ (h >>> 15), 2246822519); h = Math.imul(h ^ (h >>> 13), 3266489917); h ^= h >>> 16; return (h >>> 0) / 4294967296; };
    const N = 21;
    const finder = (r, c) => {
      const g = (R, C) => (R === 0 || R === 6 || C === 0 || C === 6) ? true : (R >= 2 && R <= 4 && C >= 2 && C <= 4);
      if (r < 7 && c < 7) return { in: true, on: g(r, c) };
      if (r < 7 && c >= N - 7) return { in: true, on: g(r, c - (N - 7)) };
      if (r >= N - 7 && c < 7) return { in: true, on: g(r - (N - 7), c) };
      return { in: false, on: false };
    };
    const cells = [];
    for (let r = 0; r < N; r++) for (let c = 0; c < N; c++) {
      const f = finder(r, c);
      const on = f.in ? f.on : rand() > 0.52;
      cells.push({ bg: on ? "#0b0b0c" : "transparent" });
    }
    return cells;
  },

  // 移植自設計 renderVals（去掉 React 式 onClick 閉包欄位 —— 改用 data-act 委派）
  renderVals() {
    const cart = this.state.cart;
    const P = this.products();
    const byId = Object.fromEntries(P.map((x) => [x.id, x]));
    const count = Object.values(cart).reduce((a, b) => a + b, 0);
    const total = this.totalOf(cart);

    const products = P.map((it) => {
      const qty = cart[it.id] || 0;
      return { ...it, qty, isInCart: qty > 0, priceNowLabel: this.fmt(it.priceNow), priceOrigLabel: this.fmt(it.priceOrig) };
    });

    const cartRows = Object.entries(cart).map(([id, q]) => {
      const it = byId[id];
      return { id, name: it.name, unit: it.unit, qty: q, tone: it.tone, lineLabel: this.fmt(it.priceNow * q), unitLabel: this.fmt(it.priceNow) + " / " + it.unit };
    });

    const currentView = this.state.standby ? "standby" : this.state.overlay === "checkout" ? "checkout" : this.state.overlay === "thankyou" ? "placed" : (count === 0 ? "empty" : "filled");
    const reviewOptions = [["filled", "含商品"], ["empty", "空購物車"], ["checkout", "結帳"], ["placed", "完成"], ["standby", "待機"]].map(([v, label]) => {
      const active = v === currentView;
      return { v, label, bg: active ? "var(--accent)" : "var(--fill-2)", color: active ? "var(--text-on-brand)" : "var(--text-primary)", border: active ? "transparent" : "var(--glass-border)" };
    });

    return {
      ads: this.ads(),
      adIndex: this.state.adIndex,
      products, cartRows, count,
      hasItems: count > 0, isEmpty: count === 0,
      totalLabel: this.fmt(total),
      checkoutLabel: "結帳 · " + this.fmt(total),
      paidLabel: this.fmt(this.state.paidTotal),
      showCheckout: this.state.overlay === "checkout",
      showThankyou: this.state.overlay === "thankyou",
      standby: this.state.standby,
      reviewOptions,
      showReview: true,
      reviewOpen: this.state.reviewOpen,
      qrCells: this.qrCells("GLAZE|" + total + "|" + JSON.stringify(cart)),
    };
  },

  render() {
    const v = this.renderVals();
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
  },
};

// ===== 版面層（template 函式，搬自設計 <x-dc> 各 data-screen-label 區塊）=====

function TopBar(v) {
  return `<header style="position:sticky;top:0;z-index:30;display:flex;align-items:center;gap:16px;padding:14px 28px;
    background:var(--glass-tint-thin);backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));
    -webkit-backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));border-bottom:0.5px solid var(--glass-border);">
    <div style="display:flex;align-items:center;gap:12px;">
      <div class="anim-drift" style="position:relative;width:42px;height:42px;border-radius:13px;display:grid;place-items:center;
        overflow:hidden;background:var(--fluid-warm);background-size:200% 200%;
        box-shadow:var(--shadow-2),inset 0 1px 0 rgba(255,255,255,.55),inset 0 0 0 0.5px rgba(255,255,255,.18);color:#fff;">
        <span aria-hidden="true" style="position:absolute;inset:0;background:radial-gradient(120% 80% at 28% 0%,rgba(255,255,255,.45),transparent 60%);pointer-events:none;"></span>
        <i class="ph-fill ph-fork-knife" style="position:relative;font-size:23px;filter:drop-shadow(0 1px 2px rgba(0,0,0,.28));"></i>
      </div>
      <span style="font-family:var(--font-display);font-weight:800;font-size:24px;letter-spacing:-0.5px;">Leon</span>
      <span style="margin-left:6px;padding:5px 12px;border-radius:var(--radius-capsule);background:var(--fill-3);font-size:13px;color:var(--text-secondary);">現場點餐</span>
    </div>
    <div style="flex:1;"></div>
    <div style="display:flex;align-items:center;gap:14px;padding:7px 8px 7px 18px;border-radius:var(--radius-capsule);
      background:var(--glass-tint);border:0.5px solid var(--glass-border);box-shadow:var(--glass-shadow);">
      <span style="font-family:var(--font-display);font-weight:700;font-size:17px;font-variant-numeric:tabular-nums;">${v.totalLabel}</span>
      <div style="position:relative;width:42px;height:42px;border-radius:var(--radius-capsule);display:grid;place-items:center;background:var(--accent);color:var(--text-on-brand);">
        <i class="ph-fill ph-shopping-bag" style="font-size:20px;"></i>
        ${v.hasItems ? `<span style="position:absolute;top:-5px;right:-5px;min-width:20px;height:20px;padding:0 5px;border-radius:999px;
          background:var(--color-red);color:#fff;font-size:12px;font-weight:700;display:grid;place-items:center;
          box-shadow:0 0 0 2px var(--bg-base);font-variant-numeric:tabular-nums;">${v.count}</span>` : ""}
      </div>
    </div>
  </header>`;
}

function Menu(v) {
  const card = (row) => `
    <div style="position:relative;display:flex;flex-direction:column;background:var(--glass-tint);border-radius:var(--radius-xl);
      border:0.5px solid var(--glass-border);box-shadow:var(--glass-shadow);
      backdrop-filter:blur(var(--blur-regular)) saturate(var(--glass-saturate));
      -webkit-backdrop-filter:blur(var(--blur-regular)) saturate(var(--glass-saturate));overflow:hidden;color:var(--text-primary);">
      <div class="anim-drift" style="position:relative;aspect-ratio:5/3;margin:8px;border-radius:var(--radius-lg);overflow:hidden;
        background:${row.tone};background-size:180% 180%;display:grid;place-items:center;">
        <span aria-hidden="true" style="position:absolute;inset:0;background:var(--droplet-sheen);pointer-events:none;"></span>
        <i class="ph-fill ${row.icon}" style="font-size:56px;color:rgba(255,255,255,.92);filter:drop-shadow(0 3px 10px rgba(0,0,0,.35));"></i>
      </div>
      <div style="padding:8px 18px 18px;display:flex;flex-direction:column;gap:10px;flex:1;">
        <div style="display:flex;align-items:baseline;justify-content:space-between;gap:8px;">
          <span style="font-family:var(--font-display);font-size:22px;font-weight:700;letter-spacing:-0.3px;">${esc(row.name)}</span>
          <span style="font-size:14px;color:var(--text-secondary);flex:none;">${esc(row.unit)}</span>
        </div>
        <div style="display:flex;align-items:baseline;gap:10px;">
          <span style="font-family:var(--font-display);font-size:27px;font-weight:800;font-variant-numeric:tabular-nums;">${row.priceNowLabel}</span>
          <span style="font-size:15px;color:var(--text-tertiary);text-decoration:line-through;font-variant-numeric:tabular-nums;">原價 ${row.priceOrigLabel}</span>
        </div>
        <div style="margin-top:auto;padding-top:6px;">
          ${row.isInCart
            ? QuantityStepper({ id: row.id, value: row.qty, size: "lg" })
            : Button({ label: "加入購物車", icon: "ph-bold ph-plus", variant: "primary", size: "lg", block: true, act: "add", data: { id: row.id } })}
        </div>
      </div>
    </div>`;
  return `<main style="display:flex;flex-direction:column;gap:24px;min-width:0;">
    ${AdBanner({ slides: v.ads, index: v.adIndex, height: 240 })}
    <div style="display:flex;align-items:center;justify-content:space-between;gap:16px;">
      <h2 style="margin:0;font-family:var(--font-display);font-size:26px;font-weight:700;letter-spacing:-0.5px;">選購商品</h2>
      <span style="font-size:14px;color:var(--text-secondary);">現場取貨 · 每項最多 50</span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(2,minmax(260px,1fr));gap:20px;">${v.products.map(card).join("")}</div>
  </main>`;
}

function CartRail(v) {
  const line = (l) => `
    <div style="display:flex;align-items:center;gap:12px;padding:14px 2px;border-bottom:0.5px solid var(--separator);">
      <div class="anim-drift" style="width:52px;height:52px;flex:none;border-radius:var(--radius-md);background:${l.tone};background-size:180% 180%;box-shadow:inset 0 0 0 0.5px var(--glass-border);"></div>
      <div style="flex:1;min-width:0;">
        <div style="font-family:var(--font-display);font-size:16px;font-weight:600;letter-spacing:-0.2px;">${esc(l.name)}</div>
        <div style="font-size:13px;color:var(--text-secondary);margin-top:2px;font-variant-numeric:tabular-nums;">${l.unitLabel}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:8px;">
        <span style="font-size:12px;color:var(--text-tertiary);">小計</span>
        <span style="font-family:var(--font-display);font-size:16px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:-4px;">${l.lineLabel}</span>
        ${QuantityStepper({ id: l.id, value: l.qty, size: "sm" })}
      </div>
    </div>`;
  const body = v.hasItems
    ? `<div>
        <div style="display:flex;flex-direction:column;max-height:44vh;overflow:auto;margin:10px 0 0;border-top:0.5px solid var(--separator);">
          ${v.cartRows.map(line).join("")}
        </div>
        <div style="display:flex;align-items:baseline;justify-content:space-between;padding:16px 2px 18px;">
          <span style="font-family:var(--font-display);font-size:18px;font-weight:700;">總計</span>
          <span style="font-family:var(--font-display);font-size:27px;font-weight:800;font-variant-numeric:tabular-nums;">${v.totalLabel}</span>
        </div>
        ${Button({ label: v.checkoutLabel, icon: "ph-bold ph-qr-code", variant: "primary", size: "lg", block: true, act: "checkout" })}
        <p style="margin:12px 0 0;text-align:center;font-size:12px;color:var(--text-tertiary);display:flex;align-items:center;justify-content:center;gap:6px;"><i class="ph ph-storefront"></i> 現場取貨 · 掃碼付款</p>
      </div>`
    : `<div style="display:flex;flex-direction:column;align-items:center;gap:12px;padding:50px 12px;text-align:center;">
        <div style="width:64px;height:64px;border-radius:var(--radius-lg);display:grid;place-items:center;background:var(--fill-2);color:var(--text-tertiary);">
          <i class="ph ph-shopping-bag" style="font-size:30px;"></i>
        </div>
        <p style="margin:0;font-size:16px;color:var(--text-secondary);max-width:200px;text-wrap:pretty;">您的購物車是空的</p>
        <p style="margin:0;font-size:13px;color:var(--text-tertiary);">點選商品加入購物車</p>
      </div>`;
  return `<aside style="position:sticky;top:88px;align-self:start;height:fit-content;display:flex;flex-direction:column;padding:22px;
    border-radius:var(--radius-xl);background:var(--glass-tint-thick);backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));
    -webkit-backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));border:0.5px solid var(--glass-border);box-shadow:var(--glass-shadow-raised);">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
      <i class="ph-fill ph-shopping-bag" style="font-size:20px;color:var(--accent);"></i>
      <h3 style="margin:0;flex:1;font-family:var(--font-display);font-size:20px;font-weight:700;letter-spacing:-0.3px;">您的購物車</h3>
      ${Badge(v.count)}
    </div>
    ${body}
  </aside>`;
}

function CheckoutSheet(v) {
  const line = (l) => `<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:13px 0;border-bottom:0.5px solid var(--separator);">
    <span style="font-size:15px;">${esc(l.name)} <span style="color:var(--text-secondary);font-variant-numeric:tabular-nums;">× ${l.qty}</span></span>
    <span style="font-family:var(--font-display);font-weight:700;font-variant-numeric:tabular-nums;">${l.lineLabel}</span></div>`;
  const qr = v.qrCells.map((c) => `<span style="background:${c.bg};"></span>`).join("");
  return `<div class="wf-fade" data-act="close" style="position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;
    padding:24px;background:rgba(0,0,0,.5);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);">
    <div class="wf-sheet" data-act="stop" style="width:min(560px,100%);max-height:90vh;overflow:auto;background:var(--glass-tint-thick);
      backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));-webkit-backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));
      border:0.5px solid var(--glass-border);border-radius:var(--radius-2xl);box-shadow:var(--glass-shadow-raised);padding:22px 26px 30px;color:var(--text-primary);">
      <div style="width:40px;height:5px;border-radius:999px;background:var(--text-quaternary);margin:0 auto 18px;"></div>
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
        <h3 style="margin:0;font-family:var(--font-display);font-size:24px;font-weight:700;letter-spacing:-0.3px;">結帳</h3>
        ${IconButton({ icon: "ph ph-x", label: "關閉", act: "close" })}
      </div>
      <div style="display:flex;flex-direction:column;margin:8px 0 2px;border-top:0.5px solid var(--separator);">${v.cartRows.map(line).join("")}</div>
      <div style="display:flex;align-items:baseline;justify-content:space-between;padding:14px 0 18px;">
        <span style="font-family:var(--font-display);font-size:18px;font-weight:700;">總計</span>
        <span style="font-family:var(--font-display);font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;">${v.totalLabel}</span>
      </div>
      <div style="display:flex;flex-direction:column;align-items:center;gap:14px;padding:20px;border-radius:var(--radius-xl);background:var(--fill-3);border:0.5px solid var(--glass-border);">
        <div style="padding:14px;background:#fff;border-radius:16px;box-shadow:0 8px 24px rgba(0,0,0,.3);">
          <div style="width:204px;height:204px;display:grid;grid-template-columns:repeat(21,1fr);grid-template-rows:repeat(21,1fr);">${qr}</div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;font-family:var(--font-display);font-size:18px;font-weight:700;"><i class="ph ph-qr-code" style="font-size:20px;color:var(--accent);"></i>請掃碼付款</div>
        <p style="margin:0;font-size:13px;color:var(--text-secondary);text-align:center;">掃描上方 QR 條碼，付款完成後即可取貨</p>
      </div>
      <div style="margin-top:18px;">${Button({ label: "我已完成付款", icon: "ph-bold ph-check", variant: "primary", size: "lg", block: true, act: "place" })}</div>
    </div>
  </div>`;
}

function ThankYou(v) {
  return `<div class="wf-fade" style="position:fixed;inset:0;z-index:70;display:flex;align-items:center;justify-content:center;
    background:rgba(0,0,0,.62);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);padding:24px;">
    <div class="wf-sheet" style="width:min(460px,100%);text-align:center;background:var(--glass-tint-thick);
      backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));-webkit-backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));
      border:0.5px solid var(--glass-border);border-radius:var(--radius-2xl);box-shadow:var(--glass-shadow-raised);padding:48px 36px;color:var(--text-primary);">
      <div class="anim-drift" style="width:96px;height:96px;border-radius:var(--radius-capsule);margin:0 auto 22px;display:grid;place-items:center;
        background:var(--fluid-cool);background-size:200% 200%;box-shadow:var(--glass-shadow-raised),inset 0 1px 0 rgba(255,255,255,.5);">
        <i class="ph-bold ph-check" style="font-size:48px;color:#fff;"></i>
      </div>
      <h2 style="margin:0 0 10px;font-family:var(--font-display);font-size:34px;font-weight:800;letter-spacing:-0.5px;">謝謝惠顧</h2>
      <p style="margin:0 0 6px;font-size:16px;color:var(--text-secondary);">付款成功，餐點製作中</p>
      <p style="margin:0 0 26px;font-size:15px;color:var(--text-secondary);">已付款 <span style="font-family:var(--font-display);font-weight:700;color:var(--text-primary);font-variant-numeric:tabular-nums;">${v.paidLabel}</span> · 請至取餐口領取</p>
      ${Button({ label: "完成", variant: "glass", size: "lg", block: true, act: "finish" })}
    </div>
  </div>`;
}

function Standby() {
  return `<div class="wf-fade" data-act="exitStandby" style="position:fixed;inset:0;z-index:80;cursor:pointer;overflow:hidden;display:flex;
    flex-direction:column;align-items:center;justify-content:center;text-align:center;color:#fff;background:var(--bg-base);">
    <div class="anim-drift" style="position:absolute;inset:0;background:var(--fluid-spectrum);background-size:240% 240%;"></div>
    <span aria-hidden="true" style="position:absolute;inset:0;background:var(--droplet-sheen);"></span>
    <span aria-hidden="true" style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(0,0,0,.2),rgba(0,0,0,.52));"></span>
    <div style="position:relative;display:flex;flex-direction:column;align-items:center;gap:18px;padding:40px;">
      <div style="width:76px;height:76px;border-radius:22px;display:grid;place-items:center;background:rgba(255,255,255,.16);
        backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border:0.5px solid rgba(255,255,255,.4);"><i class="ph-fill ph-fork-knife" style="font-size:40px;"></i></div>
      <h1 style="margin:0;font-family:var(--font-display);font-size:66px;font-weight:800;letter-spacing:-1px;text-shadow:0 4px 24px rgba(0,0,0,.4);">歡迎光臨</h1>
      <p style="margin:0;font-size:22px;opacity:.92;text-shadow:0 2px 12px rgba(0,0,0,.4);">輕觸螢幕，開始點餐</p>
      <div style="margin-top:10px;display:inline-flex;align-items:center;gap:10px;padding:15px 30px;border-radius:var(--radius-capsule);
        background:rgba(255,255,255,.18);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border:0.5px solid rgba(255,255,255,.4);font-size:18px;font-weight:600;"><i class="ph-bold ph-hand-tap" style="font-size:20px;"></i>開始點餐</div>
    </div>
  </div>`;
}

function ReviewSwitcher(v) {
  const panel = `<div class="wf-fade" style="display:flex;flex-direction:column;gap:10px;padding:13px;border-radius:var(--radius-lg);
    background:var(--glass-tint-thick);backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));
    -webkit-backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));border:0.5px solid var(--glass-border);box-shadow:var(--glass-shadow-raised);">
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="flex:1;font-size:11px;font-weight:700;letter-spacing:1px;color:var(--text-tertiary);padding:0 2px;">預覽狀態 · DEMO</span>
      <button data-act="toggleReview" aria-label="收合" style="width:28px;height:28px;flex:none;display:grid;place-items:center;border-radius:var(--radius-capsule);border:0.5px solid var(--glass-border);background:var(--fill-2);color:var(--text-secondary);cursor:pointer;"><i class="ph-bold ph-caret-down" style="font-size:14px;"></i></button>
    </div>
    <div style="display:flex;gap:6px;flex-wrap:wrap;max-width:268px;">
      ${v.reviewOptions.map((o) => `<button data-act="setView" data-view="${o.v}" style="padding:8px 14px;min-height:38px;border-radius:var(--radius-capsule);border:0.5px solid ${o.border};background:${o.bg};color:${o.color};font-size:13px;font-weight:600;font-family:var(--font-text);cursor:pointer;">${esc(o.label)}</button>`).join("")}
    </div>
  </div>`;
  const collapsed = `<button data-act="toggleReview" aria-label="開啟預覽狀態" style="display:inline-flex;align-items:center;gap:8px;height:44px;padding:0 16px;
    border-radius:var(--radius-capsule);background:var(--glass-tint-thick);backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));
    -webkit-backdrop-filter:blur(var(--blur-thick)) saturate(var(--glass-saturate));border:0.5px solid var(--glass-border);box-shadow:var(--glass-shadow-raised);
    color:var(--text-secondary);cursor:pointer;font-family:var(--font-text);font-size:12px;font-weight:600;"><i class="ph-bold ph-sliders-horizontal" style="font-size:16px;"></i>預覽</button>`;
  return `<div style="position:fixed;left:20px;bottom:20px;z-index:90;display:flex;flex-direction:column;align-items:flex-start;">
    ${v.reviewOpen ? panel : collapsed}</div>`;
}

// ===== 事件委派 + 廣告輪播 =====

function bindEvents(root) {
  root.onclick = (e) => {
    const t = e.target.closest("[data-act]");
    if (!t) return;
    const act = t.dataset.act;
    const id = t.dataset.id;
    const cur = id ? (App.state.cart[id] || 0) : 0;
    switch (act) {
      case "add": App.setQty(id, 1); break;
      case "inc": App.setQty(id, cur + 1); break;
      case "dec": App.setQty(id, cur - 1); break;
      case "checkout": App.openCheckout(); break;
      case "close": App.closeOverlay(); break;
      case "place": App.placeOrder(); break;
      case "finish": App.finishOrder(); break;
      case "exitStandby": App.exitStandby(); break;
      case "toggleReview": App.toggleReview(); break;
      case "setView": App.setView(t.dataset.view); App.setState({ reviewOpen: false }); break;
      case "adGoto": App.showAd(parseInt(t.dataset.idx, 10)); restartAdTimer(); break;
      // "stop" / "noop" / 其他：no-op（"stop" 讓 sheet 內點擊不冒泡到 overlay 的 close）
    }
  };
}

// 廣告輪播：start-once（不在 render() 重設倒數，否則點餐互動會一直把倒數歸零——反思
// adbanner-timer-reset）。每次切換換 [data-ad] outerHTML（animate 觸發 glaze-pop-in 過場）；
// 手動點 pill（adGoto）則重啟倒數，避免剛點完馬上又自動跳。
const AD_INTERVAL = 5000;
let _adTimer = null;
function restartAdTimer() {
  const ads = App.ads();
  if (!ads || ads.length < 2) return;
  if (_adTimer) clearInterval(_adTimer);
  _adTimer = setInterval(() => App.showAd((App.state.adIndex + 1) % ads.length), AD_INTERVAL);
}

document.addEventListener("DOMContentLoaded", () => { App.render(); restartAdTimer(); });
