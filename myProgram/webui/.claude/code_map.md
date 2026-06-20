# myProgram/webui/ — code_map（本層索引）

> 顆粒：細。點餐網頁前端（buildless，無打包 / 無框架 runtime / 無測試框架）。live 連 `web/` FastAPI WS 鏡像、demo（`?demo=1`）走本機假資料切換器。**Pi 4 自瀏覽器跑不動（GPU + Chromium<111 無 OKLCH）→ 渲染在 client 筆電、Pi 只當 server。**

## 子目錄
- `tokens/` — Glaze Liquid Glass 設計語彙 CSS 變數（6 檔：`colors` / `typography` / `spacing` / `effects` / `motion` / `fonts`；`fonts.css` 內 `@import` 載 Inter + Noto Sans TC CDN）。`index.html` 逐檔 link。

## 檔案
- `index.html` — 殼：依序 link `tokens/*.css` + Phosphor 圖示（CDN）+ `app.css`；`<div id="app">` 由 `app.js` 渲染。
- `app.js` — 前端全部邏輯（無框架）。三層：**元件層**（回 HTML 字串的小函式 `Button`/`QuantityStepper`/`AdBanner`/`ActionArea`…）+ **狀態層**（`App` 物件，移植自設計 DCLogic；`render()` 整頁重畫 + `syncCart()` 局部更新避免重建玻璃 backdrop）+ **版面層**（`TopBar`/`Menu`/`CartRail`/`OrderSummary`/`ConfirmSheet`/`CheckoutSheet`/`ThankYou`/`Standby`）。事件用 `data-act` 委派。**live**（預設，`connectLive` fetch `/api/state` + WS `/ws/state`，`applyState` 依機器人 phase 驅動 overlay；觸控只送命令、狀態等 emit）/ **demo**（`?demo=1`，本機切換器 + 觸控直接改 state）雙模式。overlay 流：`null → confirm → checkout → thankyou`（`confirm` 在 live 由機器人 `checkout_confirm` phase 驅動）。
- `app.css` — 全域樣式（玻璃容器 / `wf-fade`·`wf-sheet` 過場 / morph / cart-row 進出場 keyframes）。
- `serve.py` — 零快取靜態伺服器（`python3.11 myProgram/webui/serve.py [port]`，預設 8137）：獨立 / 開發展示用；**live 模式改由 `web/app.py` FastAPI StaticFiles 出靜態檔**。

## 其他
- `CLAUDE.md` — 本層導引。
- `.claude/code_map.md` — 本檔。

## 測試
- 無 JS 單元框架（buildless，對齊 Phase 0/1/2）→ `node --check app.js` 語法 + 筆電 by-eye 驗收（live robot 路徑 Pi by-ear）。
