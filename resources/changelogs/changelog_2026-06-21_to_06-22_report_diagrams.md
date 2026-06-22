# 2026-06-21 ~ 06-22 · 報告系統圖製作工具化弧（棄 Mermaid → HTML/CSS 管線 + architecture-diagram skill 固化）

> 目標:為期末報告畫一整套系統架構圖。本弧**不改 myProgram 產品碼**,是**製作工具 + 工作流的固化**。產出 = `architecture-diagram` skill + backlog spec;圖①②③ 試畫後全 reset,待新 session 照 backlog 從零重畫。

## 1. 工具路線:棄 Mermaid，自建 HTML/CSS + Chromium 截圖管線
- Mermaid（含官方 mermaid-cli）**自定義度低**:dagre 佈局搶方向盤無法精確擺位、`style/classDef` parser 不認 `oklch()`、毛玻璃只能 hack → 使用者裁決放棄。
- 改 **純 HTML/CSS 絕對定位卡片 + SVG overlay 箭頭 + 無頭 Chromium（Playwright MCP）截圖**:OKLCH / `backdrop-filter` 毛玻璃 / web 字 / 立體陰影全原生;無 Mermaid「測量字寬≠渲染字寬」截字 bug。
- 嘗試過 `/design-sync`(claude.ai/design)——**不適用**:本 repo 非元件庫(零 package.json)、且會 `npm install` 撞「Windows 不裝依賴」紅線。

## 2. 視覺系統（共用 theme，全圖一致）
- 深色霓虹毛玻璃 + **OKLCH 全程** + **IBM Plex 超級字族**（Mono=code 識別字 / Sans=英文 / Sans TC=繁中,刻意配對）+ 圓角 + 反色光 sheen + 立體投影 + 霓虹 glow + 2 池柔光 + 極淡儀表格線。
- **簽名元素**:等寬大寫 **eyebrow 分類標**（編碼真實分類,如 thread 生命週期 / state 用途）+ `FIG.NN` 徽章;每張圖再挑一個「主角」(如圖② 把 `enter_hawk` 回流弧做成暖金高亮,點明「循環非直線」)。
- 色彩語意**每圖專用 + 配 legend**;卡內容垂直置中、組件 ≥30px 不相碰、箭頭標籤壓線中段。
- canonical theme = `diagrams/theme/{tokens.css,diagram.css}`。

## 3. 三張試畫（後全 reset）
- 圖① Process/Thread 並行模型、圖② L0–L5 銷售狀態機、圖③ web phase 狀態機,皆逐檔讀實際碼核對後畫成、使用者驗收過。
- 後使用者決定**從零全新重畫**(含背景樣式)→ 圖①②③ 成品(html/png/svg)全刪;**theme + 各圖 spec(`specs/01,02,03.md`)保留**供重畫複用。

## 4. 固化成 architecture-diagram skill（`.claude/skills/architecture-diagram/`）
- `SKILL.md`:**強制流程**(主題 spec → 讀實際碼 → 設計 SDD → writing-plans → 派 opus subagent 實作 → orchestrator 復檢 → 驗收 → 2×PNG/SVG commit) + **3 鐵則**:① **嚴格依實際碼、嚴禁憑空捏造**(不確定回去讀到確定) ② **寫 HTML = 走 SDD**(`/frontend-design` + `/superpowers:brainstorming` + `/superpowers:writing-plans` + 派 `model:opus` subagent) ③ **私下自檢到完美**(先全圖再局部)。
- `reference/render-pipeline.md`:no-cache server（plain `http.server` 快取 CSS）、Playwright quirks、**DPR 反推填滿匯出配方**(零黑邊)、自檢清單、SVG 內嵌、gitignore。
- `reference/visual-system.md`:theme / 字體角色 / 色彩語意 / eyebrow / 版面鐵則 / frontend-design 落地。
- `scripts/nocache_server.py`、`assets/skeleton.html`(含 SVG `<marker>` 箭頭頭)。
- memory `diagram-authoring-style` 改成**薄指標**指向 skill。

## 5. skill 驗證 + 硬化（subagent 乾跑）
- 派 subagent **只拿 skill 獨立乾跑圖③** → 驗證:**生手靠鐵則 1 讀碼,自己發現 `checkout_confirm` 不在 `machine.py:29 _PHASE_BY_STATE`、是 dialog 內子 phase**(digest 平表會誤導,照畫失真)——鐵則 1 + 反捏造的價值實證。
- 據摩擦日誌**硬化 6 項**:skeleton 含 marker（theme 無 marker → 生手畫出有線沒頭）/ **DPR 去寫死**(實測有 0.667 也有 1.0、隨環境變 → 必量) / SVG 組檔尺寸寫死進字串(變數拼接拿到空值產壞 SVG) / 大 SVG 別用 browser 開驗(timeout) / System.Drawing 踩坑 / 自檢清單加「箭頭有沒有頭」「跨 band y 不重疊」/ **自檢先全圖再局部**(只裁局部會漏別處,圖① 被抓包根因)。

## 6. description 觸發優化 + 反思 + backlog
- skill-creator `run_loop` 在 Windows 上每 query 都 `WinError 10038`(async 叫 `claude -p` 機制不通)→ 改**手動**(自設 20 條 trigger eval 判別邊界),description 改 pushy、列舉圖種、涵蓋口語、明列不觸發 near-miss。
- `proposals.md` 3 條 pending(svg-marker / powershell-svg-empty / dpr-must-measure)**採納+落實於 commit `9e5748d`+歸檔**(`archive/proposals_archived_2026-06-22.md`);皆 skill 內容修正、不轉 eval。
- **backlog spec `specs/00-diagram-backlog.md`**:11 張清單(①②③ + ④時序 ⑤部署 ⑥STT ⑦TTS ⑧模組依賴 ⑨類別 ⑩資料契約[原資料模型改框,無真 DB] ⑪啟動分流[新增])+ 每張「畫前必讀實際碼」+ 波次 A–E + 待辦,給新 session 從零重畫的索引。

## 關鍵踩坑（都已固化進 skill）
DPR 非固定要每次量｜`body` flex-center 視窗矮會裁頂不可捲（改 block + `margin:auto`）｜縮放 + 視窗截圖對不齊產黑邊（改「device viewport 反推 + 畫布 scale 填滿 + margin:0」、四角驗）｜SVG marker 箭頭頭 theme 沒給｜PowerShell 字串拼變數成空｜自檢只裁局部會漏。

## 狀態
skill 完整(固化 + 乾跑驗證 + 6 硬化 + description 優化)、backlog spec 就緒。**下一步＝新 session 載 architecture-diagram skill、照 backlog 從零重畫 11 張圖**（Wave A 核心 ①②③ 先）。
