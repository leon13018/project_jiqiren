---
name: architecture-diagram
description: 畫 Project_01 報告用系統架構圖 / 流程圖 / 狀態機 —— 純 HTML/CSS（深色霓虹毛玻璃 + IBM Plex + OKLCH）經本機 Chromium 截圖成 2× PNG + SVG。新增或修改 resources/architecture/diagrams/ 任何圖時載入本 skill 並嚴格照流程走。
---

# 架構圖製作工作流（Project_01 報告用）

把「主程式架構」畫成報告等級的系統圖。已用圖①(Process/Thread)、圖②(狀態機)驗證定版。**棄 Mermaid**（自定義度低、佈局 dagre 搶方向盤、OKLCH/毛玻璃只能 hack）→ 改純 **HTML/CSS 絕對定位 + SVG 箭頭層 + 無頭 Chromium 截圖**。

> 本檔＝入口 + **強制流程 checklist** + router。技術細節在 `reference/`，動手前讀。

## ⛔ 三條鐵則（違反就返工）

1. **嚴格依實際碼，嚴禁憑空捏造** —— 畫圖 / 寫對應碼**一律嚴格依照從主程式實際讀到的完整內容**。digest（`resources/architecture/NN-*.md`）只當索引、可能漂移；**畫什麼一定回去讀對應 `.py` 原始碼逐項核對**（狀態 / 轉移條件 / 計時常數 / 欄位 / 邊界 / 行為）。**任何不確定 → 立刻回去讀主程式，讀到確定才動筆。千萬不可畫 / 寫出主程式裡不存在的東西**（編造的狀態 / 轉移 / 計時 / 欄位 / 行為一旦進報告就是事實錯誤，會誤導讀者又極難事後抓出）。**不確定就再讀，別猜、別腦補**。
2. **動手寫 HTML 前一定先 `invoke` `/frontend-design`**（每張圖都要，session 早期載過不算 —— 設計原則要在腦中新鮮）。
3. **私下截圖自檢到完美才給使用者**，不給半成品。自檢**必裁箭頭匯聚區 + 每張卡**（不能只抽查；圖①漏裁右側被抓包）。

## 📋 每張圖的強制流程（逐步、不可跳）

依使用者定的標準流程，每張圖一個循環：

1. **寫主題 spec（查找內容）** → 存 `resources/architecture/diagrams/specs/NN-<topic>.md`：這張要表達什麼、涵蓋哪些事實、來源檔。
2. **完整讀實際代碼庫** → 把 spec 要畫的每個事實（狀態 / 轉移 / 計時 / 邊界 / 通訊）回去讀 `myProgram/` 對應 `.py` 逐項核對，寫進 spec。（鐵則 1）
3. **寫詳細畫圖 spec** → 同檔補上：色彩語意（每圖專用 + legend）、版面（節點 / 邊 / 群組座標規劃）、本圖 signature。
4. **`invoke` `/frontend-design`**（鐵則 2）→ 用它的 lens 定本圖 thesis / signature（在已釘死的共用 theme 上，只花「自由軸」在 layout + 主角元素）。
5. **動手實作 HTML** → 見 `reference/visual-system.md`（共用 theme + 慣例）。先畫卡片層(無箭頭)→ 截圖修版面 → 再加 SVG 箭頭層（分兩階段較穩）。
6. **多方截圖自檢，反覆修到完美**（鐵則 3）→ 見 `reference/render-pipeline.md`（渲染 + DPR 匯出 + 裁切自檢）。逐項核對清單見該檔。
7. **給使用者驗收** → 送自檢版 PNG + 說明設計決策 + 三問（風格 / 內容 / 版面）。
8. **通過才收尾** → 匯出 **2× PNG + SVG** 進 `resources/architecture/diagrams/`、更新 `specs/`、commit（`docs(diagrams): …`）。未過則回 step 5/6 修。

> 規劃階段（還沒定要畫什麼）不要先 commit。驗收 / BLOCKED 等「等使用者」節點按 memory `push-notify-at-review-gates` 推手機。

## 🗂️ Router：要做 X → 讀哪個 reference

| 要做… | Read |
|---|---|
| 渲染 / 截圖 / DPR 匯出 / 自檢 / SVG / gitignore | `reference/render-pipeline.md` |
| 共用 theme / 色彩語意 / 字體 / eyebrow / 版面慣例 / 標籤壓線 | `reference/visual-system.md` |

## 📦 固定資產（單一事實來源）

- **共用 theme**：`resources/architecture/diagrams/theme/{tokens.css,diagram.css}`（**canonical**，全圖 HTML 相對 `<link href="theme/diagram.css">` 引用；改 theme 全圖一起變，慎改）。
- **no-cache server**：`<skill>/scripts/nocache_server.py`（plain `http.server` 會被 Chromium 快取 CSS）。
- **render 暫存**（`.playwright-mcp/`、`_crops/`、根 `NN-*.png`）已 gitignore，非交付。
- 交付物：`diagrams/NN-<topic>.{html,png,svg}` + `specs/NN-<topic>.md`，**三式同名並存**。

## 🧰 維護原則

- 新踩坑 / 新慣例 → 寫進對應 `reference/`；資產動了 → 更新本檔「固定資產」段。
- memory `diagram-authoring-style` 是薄指標,指向本 skill,別在 memory 重述協議。
