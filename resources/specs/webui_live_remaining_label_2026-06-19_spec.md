# live 商品卡補回「剩餘數量」標籤 — Mini SDD spec

**日期：** 2026-06-19
**類型：** Phase 2 漏帶的 UI 元素補回（前端）

## 症狀（Pi 實測）
live 點餐頁的商品卡片不再顯示「還可加 N 瓶 / 已達單筆上限」剩餘數量標籤——**非被遮擋**，是 Phase 2 重寫 `ActionArea` live 分支時，把 demo 分支的 `rest`（剩餘標籤 span）漏掉了。資料仍在（`renderVals` 算 `remainingLabel`），只是 live 分支沒 render。

## 設計（Option A，已與使用者敲定）
`app.js` 的 `ActionArea(row)` **live 分支**（`App._live` 為 true 那段）改成 flex-column：剩餘標籤獨立一行在上、既有 `[− pending +] [加入購物車]` 那行在下。其餘（stepper / 加入鈕 / pending 邏輯）原樣不動。

- **檔**：`myProgram/webui/app.js`，`ActionArea` 的 `if (App._live) { ... }` 分支（現 ~90-96 行）。
- **改前**（單行）：
```js
  return `<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
    ${QuantityStepper({ id: row.id, value: row.pending, size: "lg" })}
    ${Button({ label: "加入購物車", icon: "ph-bold ph-plus", variant: "primary", size: "lg", act: "add", data: { id: row.id } })}
  </div>`;
```
- **改後**（上方加剩餘標籤行，沿用 demo `rest` 的字級/色）：
```js
  return `<div style="display:flex;flex-direction:column;gap:8px;">
    <span style="font-size:13px;color:var(--text-tertiary);font-variant-numeric:tabular-nums;white-space:nowrap;">${esc(row.remainingLabel)}</span>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
      ${QuantityStepper({ id: row.id, value: row.pending, size: "lg" })}
      ${Button({ label: "加入購物車", icon: "ph-bold ph-plus", variant: "primary", size: "lg", act: "add", data: { id: row.id } })}
    </div>
  </div>`;
```

## 語意（已與使用者確認接受）
- `remainingLabel` = `remaining > 0 ? "還可加 N {unit}" : "已達單筆上限"`，`remaining = MAX_QTY(50) − 機器人購物車 qty`（既有 `renderVals` 計算）。
- live 的 stepper 是**本地預選**數量，與「還可加 N」（購物車 headroom）是兩個不同的數字——使用者已知並接受（資訊性標籤）。

## Out of scope
- 不動 demo 分支（`?demo=1`，原本就有 morph + 剩餘標籤）。
- 不重做 morph 動畫（Option B 已否決）。
- 不把 pending stepper clamp 到 remaining（YAGNI；超量交由機器人既有 invalid_qty_reask 處理）。

## 驗證
- Windows：`node --check myProgram/webui/app.js`（無 JS 單元框架）。
- Pi 視覺驗收：live 商品卡顯示「還可加 N 瓶 / 已達單筆上限」，stepper + 加入 那行原樣。
