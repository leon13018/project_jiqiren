---
name: architecture-diagram
description: 畫 / 重畫 Project_01（Raspberry Pi 人形銷售機器人）報告用的任何系統視覺圖 —— 架構圖 / 流程圖 / L0–L5 狀態機 / 時序圖 / 部署 / 網路拓樸 / 模組依賴 / 類別圖 / STT / TTS 管線圖 / 並行模型圖等。只要使用者想把主程式某部分視覺化、弄成一張圖、或放進報告，即使沒明說「畫圖」（如「弄成一張圖」「視覺化」「重畫那張」「報告要一張…」「draw a … diagram」）都要載入本 skill。**視覺風格＝ Anthropic 淺色編輯＋手繪蠟筆風，風格權威與自檢基準全來自 `report-design-system` skill**（本 skill 只負責「嚴謹做出正確的一張圖」的流程：讀實際碼 → SDD → opus 實作 → 多方 QA panel 對照基準）。產出純 HTML/CSS（自足單檔 + 內聯淺色 tokens + 蠟筆濾鏡 + Rough.js）→ 本機 Chromium 截圖成 2× PNG + SVG。不觸發：報告 PDF 內文排版本身（→ report-design-system 產線 A）/ 改 webui 點餐頁前端 / 改寫 architecture 文字文件(.md) / 讀文件 / 口頭解釋邏輯 / 截產品 UI 存報告 / 跟 Project_01 無關的圖（別科作業 ER 圖、generic mermaid）。

---

# 架構圖製作工作流（Project_01 報告用 · 淺色蠟筆風）

把「主程式架構」畫成報告等級的系統圖。**棄 Mermaid**（自定義度低、佈局 dagre 搶方向盤）→ 純 **HTML/CSS 絕對定位 + SVG 箭頭層 + 無頭 Chromium 截圖**。

> **視覺風格不在本檔定義** —— 設計系統權威 ＝ `report-design-system` skill（淺色編輯＋手繪蠟筆風）。本檔＝入口 + **強制流程 checklist** + router；風格 / 色票 / 濾鏡 / 元件 / 自檢基準一律讀 `../report-design-system/`。
> （舊深色霓虹主題 `resources/architecture/diagrams/theme/` 與已交付的深色圖 ①–⑤ 為 **legacy** 保留、本 skill 不再產出深色；新圖一律淺色蠟筆風。）

## 🎨 風格來源（動手前讀 — 全在 report-design-system skill）

| 要什麼 | 讀 |
|---|---|
| 淺色蠟筆風視覺系統（版面慣例 / 蠟筆濾鏡 / Rough.js 填色 / 塗鴉標題 / 強度旋鈕） | `../report-design-system/reference/diagram-crayon.md` |
| 色票 / 字型底層（§2 色彩 tokens、§3 字型） | `../report-design-system/reference/report-pdf.md` |
| 三張定版**對照基準**（圖①②③ HTML+PNG+SVG，gold standard） | `../report-design-system/assets/benchmarks/`（先讀 `README.md`） |
| 渲染 / 截圖 / SVG 匯出 / **視覺 critical gotchas** | `../report-design-system/reference/render-and-qa.md` |
| vendored 依賴（新圖要 render 須把這兩個複製到圖檔旁、相對引用） | `../report-design-system/assets/rough.js` · `assets/fonts/jason8.ttf` |

> **起手式**：複製一張 `../report-design-system/assets/benchmarks/NN-*.html`（自足單檔、已含完整淺色 tokens / `#crayon`·`#crayonEdge`·`#crayonText` 濾鏡 / Rough.js loader / marker 箭頭頭）當骨架改；把 `rough.js` + `fonts/jason8.ttf` 複製到新圖檔旁、引用相對路徑。本 skill 另附 `assets/skeleton.html`（最小淺色起手骨架）。

## ⛔ 三條鐵則（違反就返工）

1. **嚴格依實際碼，嚴禁憑空捏造** —— 畫圖 / 寫對應碼**一律嚴格依照從主程式實際讀到的完整內容**。digest（`resources/architecture/NN-*.md`）只當索引、可能漂移；**畫什麼一定回去讀對應 `.py` 原始碼逐項核對**（狀態 / 轉移條件 / 計時常數 / 欄位 / 邊界 / 行為）。**任何不確定 → 立刻回去讀主程式，讀到確定才動筆。千萬不可畫 / 寫出主程式裡不存在的東西**（編造的狀態 / 轉移 / 計時 / 欄位一旦進報告就是事實錯誤，會誤導讀者又極難事後抓出）。**不確定就再讀，別猜、別腦補**。
2. **寫 HTML = 走標準 SDD、不 free-hand** —— HTML 也是 code，每張圖動手前依序走：`invoke` `/frontend-design`（設計 lens）→ `invoke` `/superpowers:brainstorming`（在**已釘死的淺色蠟筆風**上腦力激盪版面 / 主角 / 取捨；自由軸只花在 layout + 主角元素，**別重訂風格**）→ `invoke` `/superpowers:writing-plans`（寫實作計畫）→ **派一個 opus subagent（`model: opus`）照計畫實作 HTML**。每張圖都走，session 早期載過不算。
3. **截圖自檢到完美才給使用者**，不給半成品。**先看「整張全圖」掃一遍 —— 整個畫布範圍都要看，絕不只看某一小區域**（只抽查局部會漏掉別處的問題），全圖掃完再針對箭頭匯聚區 + 每張卡逐塊放大細看。**此深度自檢由「每張圖平行派 3 個 opus QA subagent」執行（見流程 step 6）—— 影像 token 全留在 QA subagent，不塞爆主對話；orchestrator 只收文字裁決。QA 一律對照 `report-design-system` 的三張基準 + `diagram-crayon.md` + `render-and-qa.md §2` gotchas。**

## 🔴 視覺 critical gotchas

**完整清單在 `../report-design-system/reference/render-and-qa.md §2`**（零卡片覆蓋 · 文字不溢框 · 字別貼邊 · 卡內容垂直置中 · 卡片大小取決於內容 · 無大片死空白 · 箭頭走線整齊流暢 · **線↔三角箭頭頭同色**（marker `#ah`/`#ah-hawk` 提 specificity，GetPixel 驗）· 箭頭↔文字零交疊）。蠟筆風特有（`diagram-crayon.md`）：蠟筆框走 `::before` + `overflow:visible`、Rough 填色 `isolation:isolate`+`z-index:-1`、標題別雙重扭形、清松手寫缺字驗證。**這些是使用者逐輪像素級抓過的包 —— QA panel 逐項對照。**

## 📋 每張圖的強制流程（逐步、不可跳）

1. **寫主題 spec** → 存 `resources/architecture/diagrams/specs/NN-<topic>.md`：這張要表達什麼、涵蓋哪些事實、來源檔。
2. **完整讀實際代碼庫**（鐵則 1）→ 每個要畫的事實回去讀 `myProgram/` 對應 `.py` 逐項核對、寫進 spec。**不確定讀到確定，絕不捏造。**
3. **設計 SDD（鐵則 2）** → `invoke` `/frontend-design`（定本圖 thesis / 主角）→ `invoke` `/superpowers:brainstorming`（在淺色蠟筆風上腦力激盪 layout / 主角 / 取捨）。
4. **寫實作計畫** → `invoke` `/superpowers:writing-plans`，把設計定案寫成計畫＝詳細畫圖 spec（色彩語意+legend / 節點 / 邊 / 座標 / 群組 / 本圖 signature），存進 `specs/NN-<topic>.md`。
5. **派具名 opus subagent 實作 HTML（只寫、不 render）** → 把「計畫 + 主題 spec + 核對過的碼事實 + **report-design-system 風格（diagram-crayon.md + 一張基準當骨架）** + 三鐵則 + `render-and-qa.md`」交給一個 opus subagent（`model: opus`，**派時帶固定 name 如 `impl-NN`**，之後一律用 `SendMessage(to: impl-NN)` 續派、保住其實作 context 與已寫的 HTML）：照計畫寫 `NN-*.html`（自足單檔、內聯淺色 tokens + 蠟筆濾鏡 + Rough.js）。**implementer 只寫 HTML + 基本 sanity（不自己 render、不產 dump）**，回報 HTML 絕對路徑 + 不確定處後 **idle 待命**（接 orchestrator 的版面回饋 / QA 缺陷清單，用 SendMessage 續修；需看版面時請 orchestrator render 一版回傳，別自己開瀏覽器）。
   > **為何 implementer 不 render**：render / 截圖是單一共享瀏覽器（見 ⚡），多圖並行各自 render 會互撞、A 截到 B 的圖。render 全歸 orchestrator 序列獨占執行（step 5.5）。
   > 你本身已是 subagent、無法再派 sub-subagent → 自己實作 + 自己 render + 自檢（仍走全圖先再局部），但仍守 step 3–4 設計紀律。
5.5. **orchestrator 獨占序列 render + 產 QA 產出物** → orchestrator（非 implementer）**一次一張獨占瀏覽器**跑：navigate → `await document.fonts.ready` → 截 ①四角驗過 `NN-2x.png` ②native 解析 `NN-native.png` → 跑 ③canonical dump `NN-bbox.json`（`render-pipeline.md §5.5` schema：bbox + 兩兩 overlap + textOverflow + 每卡 top/bot gap，**＋每條有色邊的「線中段 RGB」與「箭頭頭三角 RGB」GetPixel 取樣** `arrowSamples[]`，供 QA-B 比色免再開瀏覽器）。三檔**一律絕對路徑**存 `resources/snapshots/`。多圖序列化（單一共享瀏覽器），完成一張回報 + 停用瀏覽器才 `GO` 下一張。
6. **質檢 QA panel（每張圖平行派 3 個 opus QA subagent）** → 一次平行派 3 個 opus QA（`model: opus`）檢同一張圖，各持互補 lens，**只讀靜態產出物（PNG + dump）、不 render、不 GetPixel**（要比的像素已在 step 5.5 的 dump `arrowSamples[]`），各自讀 spec + `render-and-qa.md §2` gotchas + **report-design-system 三張基準** + step 5.5 三檔，**先看全圖 PNG 再裁切放大 + 對 dump + 對基準**，回結構化裁決（逐項 PASS / FAIL + 缺陷座標 + 修法）：
   - **QA-A 版面 / 空間**：零覆蓋（含 legend·note·band/group 標籤，≥30px；讀 dump `overlaps[]`）、垂直置中（dump top/bot gap）、無空蕩大卡、無大片死空白、四角無黑邊。
   - **QA-B 箭頭 / 連線**：走線整齊流暢、**線↔三角箭頭頭同色（比 dump `arrowSamples[]` 的「線中段 RGB」vs「箭頭頭 RGB」，色相明度相近才過 —— 不 live GetPixel）**、箭頭頭真觸 + 起點實接 + 無浮空線頭 / 怪鉤 / 迴圈（裁 PNG 看每條線兩端）、線↔文字零交疊。
   - **QA-C 風格 / 內容真實性**：**對照三張基準**確認蠟筆風到位（蠟筆框抖動 + Rough hachure 填色 + 珊瑚 hero + FIG 牌 + eyebrow + 6 色語意）、文字不溢框 / 不截斷（dump `textOverflow[]`）、圓角留白、字體已載入；**＋鐵則 1 內容稽核：讀「對應 `myProgram/*.py` 原始碼」逐項核對（非只讀 spec —— spec 本身可能已被寫錯）**，把圖上每個狀態 / 轉移 / 計時數字 / 欄位回比原始碼，揪出任何捏造 / 漏 / 錯（QA-C 的讀取清單必含該圖對應 `.py` 路徑）。
   **影像 token 全留在 QA subagent**；orchestrator 只聚合 3 份文字裁決。有缺陷 → orchestrator 用 **`SendMessage(to: impl-NN)`** 把整併缺陷清單送回 step 5 的**具名** implementer 修（保住其 context；**不可再 `Agent()` 開新 subagent** —— 那會丟失原實作脈絡）→ orchestrator 重跑 step 5.5（render + dump）→ **重派 QA panel**。**收斂上限：跑到 3 個 QA 全 PASS 進 step 7；第 3 輪仍有 FAIL → 直接 surface 使用者裁定，不再自動重派**（防無限耗 agent）。
7. **給使用者驗收** → 送自檢版 PNG + 設計決策 + 三問（風格 / 內容 / 版面）。*（autonomous / 無人模式 → 自審到位即收、不阻塞。）*
8. **通過才收尾** → **從 `resources/snapshots/` 搬已 QA 通過的 `NN-2x.png`（禁重新 render —— 確保交付物＝ QA 驗過的那張，否則三輪 QA 形同虛設）** + 組 SVG（`render-pipeline.md §7`）→ 三式 `NN-*.{html,png,svg}` 進 `resources/architecture/diagrams/`、更新 `specs/`、commit（`docs(diagrams): …`）。**`00-diagram-backlog.md` 的 ✅ 與 `code_map.md` 的圖索引，只在三式 commit 後才改**（先標完成、後續 agent 讀 backlog 會誤判任務已做完）。未過回 step 5–5.5–6。

> 規劃階段（還沒定要畫什麼）不要先 commit。驗收 / BLOCKED 等「等使用者」節點按 memory `push-notify-at-review-gates` 推手機。

> **⚡ 平行加速（固化）**：
> - **可平行**：(1) 多張獨立圖的 **HTML 撰寫**（不碰瀏覽器）；(2) **QA panel** —— 每張圖 3 個 QA opus，**只讀靜態產出物（PNG + JSON dump）、不 render** → 零瀏覽器爭用、影像 token 不進主對話。
> - 🔴 **不可平行**：**render / 截圖**。Playwright MCP 是**單一共享瀏覽器實例** —— 兩 subagent 同時 navigate/截圖會互相把頁面導走。故 **render 全歸 orchestrator、implementer 一律不 render**，且 render 階段序列化：orchestrator 一次只給一張圖「獨占瀏覽器」跑完 render + 產出 3 檔（step 5.5），回報 + 停用後才 `GO` 下一張。（自足單檔走 `chrome --headless --screenshot file://` 直接 render、免 server，見 `render-and-qa.md §1`。）

## 🗂️ Router

| 要做… | 讀 |
|---|---|
| 渲染 / 截圖 / DPR 匯出 / bbox dump / SVG 組裝 / gitignore | `reference/render-pipeline.md`（本 skill：產線 render 機制）|
| 淺色蠟筆視覺系統 / 色票 / 字型 / 元件 / 自檢 gotchas / 對照基準 | `../report-design-system/`（風格權威：`diagram-crayon.md` / `report-pdf.md` / `render-and-qa.md` / `assets/benchmarks/`）|

## 📦 固定資產

- **風格權威（單一事實來源）**：`report-design-system` skill —— 色票 / 濾鏡 / 元件 / 三張對照基準 / 渲染 + QA gotchas 全在那；本 skill **不重述風格**。
- **起手骨架**：`assets/skeleton.html`（最小淺色自足起手式）；成熟結構直接複製一張 report-design-system 基準 HTML 改（含完整濾鏡 + Rough.js loader）。
- **render 機制**：`reference/render-pipeline.md` + `scripts/nocache_server.py`（Playwright 走 http 才需；自足單檔可直接 `file://` 截圖免 server）。
- **render 暫存 / 自檢截圖**存 `resources/snapshots/`（gitignored）、MCP 自輸出 `.playwright-mcp/`。
- 交付物：`resources/architecture/diagrams/NN-<topic>.{html,png,svg}` + `specs/NN-<topic>.md`，三式同名並存。
- **legacy（不再產出）**：`resources/architecture/diagrams/theme/{tokens.css,diagram.css}`（深色霓虹）+ 深色圖 ①–⑤ 保留供舊交付 render，新圖一律走淺色。

## 🧰 維護原則

- 本 skill＝**產線**（讀碼 → SDD → opus → QA），`report-design-system`＝**風格權威**（淺色蠟筆風 + 報告 PDF + 三基準）。本 skill 吃前者的風格、單向依賴；風格演進改 `report-design-system`，本檔不複製風格細節。
- 新踩坑 / 新流程慣例 → 寫進本檔或 `reference/render-pipeline.md`；**風格 / gotchas 的新發現 → 寫進 `report-design-system`**（SSOT）。
- memory `diagram-authoring-style` 是薄指標，指向本 skill。
