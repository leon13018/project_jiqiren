# live 商品卡補回剩餘數量標籤 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** live 點餐頁商品卡補回「還可加 N 瓶 / 已達單筆上限」剩餘數量標籤（Phase 2 重寫時漏掉）。

**Architecture:** 純前端——`app.js` 的 `ActionArea(row)` live 分支由單行改 flex-column，剩餘標籤獨立一行在 stepper+加入 上方；標籤資料 `row.remainingLabel` 既有（`renderVals` 已算），沿用 demo `rest` 的字級/色。

**Tech Stack:** buildless JS（無測試框架）；Pi 視覺驗收。

## Global Constraints

- **繁體中文**：新增註解 / commit 繁中。
- **純前端**：只動 `myProgram/webui/app.js` 的 `ActionArea` live 分支；不動 demo 分支、不動 morph、不動 pending 邏輯。
- **不 clamp pending 到 remaining**（YAGNI；超量交既有 invalid_qty_reask）。
- **無 JS 單元框架** → 驗證 = `node --check` + Pi 視覺驗收。
- **worktree**：`app.js` 在 `myProgram/` 下 → 走 worktree（純 git + `git -C` 收尾）；**不用 `git add -A`**。

---

## Task 1: live `ActionArea` 補剩餘標籤（app.js 一處改）

**Files:**
- Modify: `myProgram/webui/app.js`（`ActionArea` 的 `if (App._live) { ... }` 分支，現 ~90-96 行）

**Interfaces:**
- Consumes（既有）：`row.remainingLabel`（`renderVals` 算）、`esc`、`QuantityStepper`、`Button`、`row.pending` / `row.id`。

- [ ] **Step 1: 改 live 分支為 flex-column + 剩餘標籤行**

把 `app.js` 的 `ActionArea` live 分支：
```js
  if (App._live) {
    // live：本地預選數量 stepper（inc/dec 改 pending，不動 cart）+ 加入鈕（送 order）。
    // 無 morph 動畫（demo 限定）；購物車真實數量由右側欄鏡像。
    return `<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
      ${QuantityStepper({ id: row.id, value: row.pending, size: "lg" })}
      ${Button({ label: "加入購物車", icon: "ph-bold ph-plus", variant: "primary", size: "lg", act: "add", data: { id: row.id } })}
    </div>`;
  }
```
改為：
```js
  if (App._live) {
    // live：剩餘數量標籤 + 本地預選數量 stepper（inc/dec 改 pending，不動 cart）+ 加入鈕（送 order）。
    // 無 morph 動畫（demo 限定）；購物車真實數量由右側欄鏡像。剩餘標籤沿用 demo rest 字級/色。
    return `<div style="display:flex;flex-direction:column;gap:8px;">
      <span style="font-size:13px;color:var(--text-tertiary);font-variant-numeric:tabular-nums;white-space:nowrap;">${esc(row.remainingLabel)}</span>
      <div style="display:flex;align-items:center;justify-content:space-between;gap:8px;">
        ${QuantityStepper({ id: row.id, value: row.pending, size: "lg" })}
        ${Button({ label: "加入購物車", icon: "ph-bold ph-plus", variant: "primary", size: "lg", act: "add", data: { id: row.id } })}
      </div>
    </div>`;
  }
```

- [ ] **Step 2: 語法驗證**

Run（在 worktree）：`node --check myProgram/webui/app.js`
Expected: 無輸出（語法 OK）。

- [ ] **Step 3: 程式碼自檢**

人工核對：
1. 只改 live 分支（`if (App._live)` 那段）；demo 分支（`const id = esc(row.id); const rest = ...` 起）原樣不動。
2. 剩餘標籤用 `esc(row.remainingLabel)`（既有欄位），字級/色與 demo `rest` 一致。
3. stepper + 加入鈕 那行內容不變，只是被包進下層 div。

- [ ] **Step 4: Commit**

```bash
git add myProgram/webui/app.js
git commit -m "fix(webui): live 商品卡補回剩餘數量標籤（還可加 N / 已達單筆上限）"
```

---

## Pi 視覺驗收（收尾）

worktree 收尾後，Pi `--web` + 筆電硬重整（首次載新 app.js）：
- live 商品卡顯示「還可加 N 瓶 / 已達單筆上限」在 stepper+加入 上方。
- 加入後購物車數量變動 → 標籤的「還可加 N」隨機器人 cart 更新（N = 50 − cart 數量）。

---

## Self-Review

**1. Spec coverage：** spec「live 分支補 remainingLabel、flex-column、上方一行」→ Task 1 Step 1 ✓；「沿用 demo rest 字級/色」→ Step 1 span style ✓；「不動 demo/morph/pending」→ Global Constraints + Step 3.1 ✓；「Pi 視覺驗收」→ 收尾段 ✓。
**2. Placeholder scan：** 無 TBD；改前/改後完整 code。
**3. Type consistency：** `row.remainingLabel` / `esc` / `QuantityStepper` / `Button` 皆既有（Phase 0/2 已存在），用法與 demo 分支一致。
