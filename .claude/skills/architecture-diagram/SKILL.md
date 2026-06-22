---
name: architecture-diagram
description: 畫 / 重畫 Project_01（Raspberry Pi 人形銷售機器人）報告用的任何系統視覺圖 —— 架構圖 / 流程圖 / L0–L5 狀態機 / 時序圖 / 部署 / 網路拓樸 / 模組依賴 / 類別圖 / STT / TTS 管線圖 / 並行模型圖等。只要使用者想把主程式某部分視覺化、弄成一張圖、或放進報告，即使沒明說「畫圖」（如「弄成一張圖」「視覺化」「重畫那張」「報告要一張…」「draw a … diagram」）都要載入本 skill。產出純 HTML/CSS（深色霓虹毛玻璃 + IBM Plex + OKLCH）→ 本機 Chromium 截圖成 2× PNG + SVG，嚴格照內附流程（讀實際碼 → SDD → opus 實作 → 多方自檢）。不觸發：改 webui 點餐頁前端 / 改寫 architecture 文字文件(.md) / 微調 theme CSS / 讀文件 / 口頭解釋邏輯 / 截產品 UI 存報告 / 跟 Project_01 無關的圖（別科作業 ER 圖、generic mermaid）。
---

# 架構圖製作工作流（Project_01 報告用）

把「主程式架構」畫成報告等級的系統圖。已用圖①(Process/Thread)、圖②(狀態機)驗證定版。**棄 Mermaid**（自定義度低、佈局 dagre 搶方向盤、OKLCH/毛玻璃只能 hack）→ 改純 **HTML/CSS 絕對定位 + SVG 箭頭層 + 無頭 Chromium 截圖**。

> 本檔＝入口 + **強制流程 checklist** + router。技術細節在 `reference/`，動手前讀。

## ⛔ 三條鐵則（違反就返工）

1. **嚴格依實際碼，嚴禁憑空捏造** —— 畫圖 / 寫對應碼**一律嚴格依照從主程式實際讀到的完整內容**。digest（`resources/architecture/NN-*.md`）只當索引、可能漂移；**畫什麼一定回去讀對應 `.py` 原始碼逐項核對**（狀態 / 轉移條件 / 計時常數 / 欄位 / 邊界 / 行為）。**任何不確定 → 立刻回去讀主程式，讀到確定才動筆。千萬不可畫 / 寫出主程式裡不存在的東西**（編造的狀態 / 轉移 / 計時 / 欄位 / 行為一旦進報告就是事實錯誤，會誤導讀者又極難事後抓出）。**不確定就再讀，別猜、別腦補**。
2. **寫 HTML = 走標準 SDD、不 free-hand** —— HTML 也是 code，每張圖動手前依序走：`invoke` `/frontend-design`（設計 lens）→ `invoke` `/superpowers:brainstorming`（腦力激盪設計方向）→ `invoke` `/superpowers:writing-plans`（寫實作計畫）→ **派一個 opus subagent（`model: opus`）照計畫實作 HTML**（對齊專案「中小以上改動派 subagent」；寫 code 走 SDD + 交 coder）。每張圖都走，session 早期載過不算。
3. **截圖自檢到完美才給使用者**，不給半成品。**先看「整張全圖」掃一遍 —— 整個畫布範圍都要看，絕不只看某一小區域**（只抽查局部會漏掉別處的問題；圖① 只裁短卡、漏了右側線亂 + 長文字溢出，被使用者抓包），全圖掃完再針對箭頭匯聚區 + 每張卡逐塊放大細看。**此深度自檢由「每張圖平行派 3 個 opus QA subagent」執行（見流程 step 6）—— 影像 token 全留在 QA subagent，不塞爆主對話；orchestrator 只收文字裁決、不自己裁切看圖。**

## 🔴 視覺 critical gotchas（生圖必守，違反返工 —— 使用者抓過包）

- **圓角留白 · 字別貼邊**：圓角卡 / group / pill / chip 的文字一律離邊 ≥ 圓角半徑（card r≈18 / group r≈20 → 文字內縮 ≥ ~22px），**絕不把字放在剛好最邊邊** —— 會被圓角切到 / 卡在彎角看起來溢出、不好看（圖① STT `group-label` `left:16px` < r 貼邊被使用者抓；theme `.group-label` 已修，但自訂絕對定位文字要自己守，group-label 起點尤其要清開頂左彎角）。
- **卡內容垂直置中**：卡片內容上下留白對稱（topGap = botGap），**不准偏靠上 / 靠下**（theme `.card` 已 `justify-content:center`；group-label / 其他絕對定位文字要自己確保）。`browser_evaluate` 量每卡 top/bot gap 驗證 —— 自檢必看項。
- **零卡片覆蓋 · legend/note/band·group 標籤 也不例外**：任何元素都**不准與任何卡片重疊** —— 即使只壓到一點點、即使文字內容沒互相干擾，任何卡片被覆蓋都傷視覺美觀、**絕對不允許**（圖② 左上 legend 壓到 EXIT 卡被使用者抓）。**band / group 的標籤（眉標）也是「文字元素」、同樣不准被節點卡壓**：band/group 標籤落在框頂，該帶/該框的**首個節點要清開標籤（首節點 top ≥ 框頂 + ~60px）**（圖④ band 標籤被首節點圓角壓穿、`overlaps=[]` 卻漏抓、被使用者肉眼抓包 —— 因 dump selector 沒納入 band 標籤,見 `render-pipeline.md §5.5`）。legend / note 雖收「角」,仍受 ≥30px 不相碰約束。自檢用 §5.5 canonical dump 量**所有** bbox 兩兩不交疊（含 legend / note / **band·group 標籤** vs 每張卡）。
- **文字不溢出卡片**：任何卡 / group / pill / chip 的文字一律收在邊框內（留圓角 padding），**不可長到溢出邊框或頂破圓角**；標籤太長就縮短 / 斷行 / 拆成多個元素（如把長語意拆進卡身或 note），**不可硬撐一行頂出框**（圖② confirm 群組長標籤溢出被使用者抓）。
- **卡片大小取決於內容多寡 · 不做空蕩大卡**：卡 / group / pill / chip 尺寸由**內容多寡**決定 —— 內容少就做小卡，**絕不為佔位 / 對齊 / 撐滿某邊而做一個一堆空白的大卡**（右半 / 下半幾乎沒字 = 浪費空間、鬆散難看）。內容少的卡縮到剛好包住內容（留正常 padding + 圓角留白），再**找合適空角 / 縫隙塞進去**，別硬攤成全幅大卡（圖② L0 共通 NLU 全幅基座帶只兩短行、右側大片空白被使用者抓）。自檢：`browser_evaluate` 量卡內容實際 bbox vs 卡框，**右 / 下大片空白（>~25%）非刻意對齊 → 縮卡**。「畫大沒關係」只指**畫布**，**非單卡可空蕩攤大**。
- **箭頭線 ↔ 文字零交疊**：SVG 箭頭線及箭頭頭**絕不可穿過 / 蓋住任何文字**（卡內文字、eyebrow、邊標籤、group-label 都算），文字也不可壓在不相關的線上 —— 線走清空 gutter 繞開所有字、邊標籤落在線中段的清空處且自帶深色 halo（圖② 連接箭頭橫穿 confirm 長標籤被使用者抓，**決不能再犯**）。自檢逐條線追視：每條線全程有沒有壓到任何字。
- 🔴🔴 **線↔三角箭頭頭同色（改線色必連頭一起改）**：改任何箭頭線的顏色，**必須連它的三角形箭頭頭 marker 一起改、兩者同色**。線是 gold、頭卻是別色 = 不搭嘎、絕不允許（使用者**講過很多次、≥3 次抓包**）。
  - **真正坑（記死）**：marker 的 `<path>` 也是 `.edges path`,會被 theme `.edges path { fill:none; stroke:var(--arrow) }` **劫持** → 三角形變成「無填色 + 淡藍 `--arrow` 描邊」,跟 gold 線完全不同色。**光在 HTML marker 上寫 `fill="var(--arrow-hawk)"` 沒用**（presentation attr specificity 0 < CSS rule，被蓋掉）—— 這就是「明明設了同 token 卻還是不同色」反覆發生的原因。
  - **正解（已修進 theme `diagram.css`）**：用 ID 提 specificity 蓋過劫持 —— `.edges marker path { stroke:none } / .edges marker#ah path { fill:var(--arrow) } / .edges marker#ah-hawk path { fill:var(--arrow-hawk) }`。新圖 marker 沿用 `id=ah`(白) / `id=ah-hawk`(金) 即自動同色,毋須在 HTML 寫死。
  - **和諧**：有色箭頭（尤其金弧）配暗背景要柔、不突兀（token `--arrow-hawk` = `oklch(79% 0.12 82 / .75)` width 3.0；別還原成舊亮粗版）。
  - **自檢必做（不可只看 computed style，會騙人）**：marker `<path>` 的 `getComputedStyle().fill` 在 marker context 會回誤值 → **一定 render 後裁切放大、GetPixel 取「線中段」與「箭頭頭實體」兩處像素 RGB 比對**，色相 / 明度相近才算過。曾出現頭 render 成淡藍 (196,216,240) 而線是金 (170,143,78) —— 必抓出。
- **無大片死空白 · 有空間就往上擠**：版面不可留大片無意義空白；若某元素 / 某段上方有明顯空白，**往上挪填滿**、整體垂直分布均衡緊湊（圖② L0 基座帶上方留大空白被使用者抓）。下半截空蕩 → 元素上移 / 或縮短畫布高度。（仍守 ≥30px 不相碰 + 不溢出 frame；「畫大沒關係」是為了不相碰，**不是**容許留死空白。）
- **箭頭走線整齊流暢**（使用者特別強調、非常重要）：箭頭線的走線要**非常整齊、流暢、舒服、整潔**——不是「連到就好」。正交走線對齊同一 lane、轉折用一致圓角、平行線等距、**最少化彎折 / 交叉 / 斜穿不相關區**、收束點對齊。**必要時反覆截圖檢視走線、調整走線方式（不只調座標、連走法都改），直到整體看起來流暢舒服才算過**——箭頭層是一張圖乾不乾淨的關鍵。**自檢必做：每條線的「兩端連接點」逐一裁切放大確認**——箭頭頭真的觸到目標卡邊、起點實接來源卡、中途無浮空線頭 / 怪鉤 / 小迴圈 / 與別線糾纏重疊（**不只看走線中段與交叉**；本 session 漏看 ③ ConfirmSheet 左緣連接、被使用者抓「你真的有每次截圖看嗎」）。

## 📋 每張圖的強制流程（逐步、不可跳）

依使用者定的標準流程，每張圖一個循環：

1. **寫主題 spec（查找內容）** → 存 `resources/architecture/diagrams/specs/NN-<topic>.md`：這張要表達什麼、涵蓋哪些事實、來源檔。
2. **完整讀實際代碼庫**（鐵則 1）→ 把每個要畫的事實（狀態 / 轉移 / 計時 / 邊界 / 通訊）回去讀 `myProgram/` 對應 `.py` 逐項核對、寫進 spec。**任何不確定回去讀到確定，絕不捏造。**
3. **設計 SDD（鐵則 2）** → `invoke` `/frontend-design`（定本圖 thesis / signature）→ `invoke` `/superpowers:brainstorming`（在已釘死共用 theme 上腦力激盪版面 / 主角 / 取捨；自由軸只花在 layout + 主角元素）。
4. **寫實作計畫** → `invoke` `/superpowers:writing-plans`，把設計定案寫成計畫＝詳細畫圖 spec（色彩語意+legend / 節點 / 邊 / 座標 / 群組 / 本圖 signature），存進 `specs/NN-<topic>.md`。
5. **派 opus subagent 實作 → 產出物** → 把「計畫 + 主題 spec + 核對過的碼事實 + 共用 theme + 三鐵則 + `reference/`」交給一個 **opus** subagent（`model: opus`）：照計畫寫 `NN-*.html`（先卡片層→截圖修版面→再 SVG 箭頭層），render 並**產出 QA 用產出物**存 `resources/snapshots/`（**一律絕對路徑、絕不寫 CWD/root**，否則觸發 code_map hook）：①四角驗過的 `NN-2x.png`、②native 解析 `NN-native.png`、③bbox JSON dump `NN-bbox.json` —— **dump 用 `render-pipeline.md §5.5` 的 canonical 配方**（已含絕對路徑 + selector 納入 band/group 標籤 + 內建 overlaps 檢查；別自己臨時拼 selector，會漏標籤盲點）。implementer 自己只做**基本 sanity 自檢**（render OK、無明顯破版），深度多方自檢交 QA panel。回報產出物路徑 + dump + 不確定處後**保持 idle 待命**（接 QA 缺陷清單回來修）。
   > 你本身已是 subagent、無法再派 sub-subagent → 自己實作 + 自檢（仍走全圖先再局部），但仍守 step 3–4 設計紀律。
6. **質檢 QA panel（每張圖平行派 3 個 opus QA subagent）** → orchestrator **一次平行派 3 個 opus QA subagent**（`model: opus`）檢同一張圖，各持一個**互補 lens**、各自讀 spec + 視覺 gotchas + `render-pipeline.md §5` + step 5 產出物（PNG + JSON dump），**先全圖再裁切放大 + GetPixel + 對 dump**，回**結構化裁決**（逐項 PASS / FAIL + 具體缺陷座標 + 修法）：
   - **QA-A 版面 / 空間**：卡片 / 元素零覆蓋（含 legend·note，≥30px）、垂直置中（top=bot gap）、無空蕩大卡、無大片死空白、整體平衡、四角無黑邊、跨 band y 不重疊。
   - **QA-B 箭頭 / 連線**：走線整齊流暢、線↔三角箭頭頭同色（GetPixel 線中段 vs 箭頭頭實體）、箭頭頭真觸目標 + 起點實接 + 無浮空線頭 / 怪鉤 / 迴圈 / 糾纏（**每條線兩端都裁**）、線↔文字零交疊、邊標籤落線中段 + halo。
   - **QA-C 文字 / 內容真實性**：文字不溢框 / 不截斷、圓角留白（字別貼邊）、字體已載入（非 fallback）、**＋鐵則 1 內容稽核**：逐一比對節點 / 邊 / 標籤 / 數字＝ spec 核對過的事實，揪出任何**捏造 / 漏 / 錯**的狀態 / phase / token / 計時 / 欄位。
   **影像 token 全留在 QA subagent、不進主對話**；orchestrator 只聚合 3 份文字裁決。有缺陷 → 整併缺陷清單送回 step 5 的 implementer subagent 修 → 它重 render + 重 dump → **重派 QA panel**。loop 到 **3 個 QA 全 PASS** 才進 step 7（N 輪仍不收斂則 surface 給使用者裁定）。
7. **給使用者驗收** → 送自檢版 PNG + 說明設計決策 + 三問（風格 / 內容 / 版面）。*（若被指派為 autonomous / 無人乾跑模式 → 此步改為自審到位即收、不阻塞等驗收。）*
8. **通過才收尾** → 匯出 **2× PNG + SVG** 進 `resources/architecture/diagrams/`、更新 `specs/`、commit（`docs(diagrams): …`）。未過則回 step 5–6 修。

> 規劃階段（還沒定要畫什麼）不要先 commit。驗收 / BLOCKED 等「等使用者」節點按 memory `push-notify-at-review-gates` 推手機。

> **⚡ 平行加速（使用者指定、固化；2026-06-22 修正「瀏覽器共享」真相）**：
> - **可平行**：(1) 多張獨立圖的 **HTML 撰寫**（不碰瀏覽器）；(2) **QA panel** —— 每張圖 3 個 QA opus，**只讀靜態產出物（PNG + JSON dump）、不 render** → 零瀏覽器爭用、可大量平行，且影像 token 不進主對話（使用者指定：自檢移出主上下文窗）。
> - 🔴 **不可平行（硬限制）**：**render / 截圖**。Playwright MCP 是**單一共享瀏覽器實例**（非每 subagent 一個）—— 兩個 subagent 同時 `navigate`/截圖會互相把頁面導走、A 截到 B 的圖（2026-06-22 圖④⑤ 實證踩過；舊「各自瀏覽器 instance、互不干擾」說法**錯誤**已刪）。故 **render 階段必須序列化**：orchestrator 居中調度，一次只給一張圖「**獨占瀏覽器**」跑完 render + 產出 3 檔（`NN-2x.png`/`NN-native.png`/`NN-bbox.json`），回報 + 停用瀏覽器後，才明確 `GO` 下一張進來。
> - **流程**：≥2 圖 → 平行派 implementer **各寫 HTML** → **輪流** render 產出物（orchestrator 發 GO、一次一張）→ 全部產出物就緒後 **平行** QA panel。⚠️ orchestrator 自己也別跟正在 render 的 implementer 同時開瀏覽器 / 編同一檔。

## 🗂️ Router：要做 X → 讀哪個 reference

| 要做… | Read |
|---|---|
| 渲染 / 截圖 / DPR 匯出 / 自檢 / SVG / gitignore | `reference/render-pipeline.md` |
| 共用 theme / 色彩語意 / 字體 / eyebrow / 版面慣例 / 標籤壓線 | `reference/visual-system.md` |

## 📦 固定資產（單一事實來源）

- **共用 theme**：`resources/architecture/diagrams/theme/{tokens.css,diagram.css}`（**canonical**，全圖 HTML 相對 `<link href="theme/diagram.css">` 引用；改 theme 全圖一起變，慎改）。
- **起手骨架**：`<skill>/assets/skeleton.html`（含 SVG `<marker>` 箭頭頭 + stage / frame / card / eyebrow / legend / edge 結構；複製成 `diagrams/NN-*.html` 改）。**⚠️ marker 箭頭頭 theme 沒給、一定要在 HTML `<defs>` 自己放（用 skeleton 的），否則畫出有線沒箭頭。已交付的圖（如 `01-process-thread.html`）即風格基準 —— 新圖實作前 Read 它學成熟 layout / 金主角線 / chip·pill·group 結構；尚未畫的圖只有 `specs/NN-*.md` + theme + 本骨架可參。**
- **no-cache server**：`<skill>/scripts/nocache_server.py`（plain `http.server` 會被 Chromium 快取 CSS）。
- **render 暫存 / 自檢截圖**（自檢圖 + 裁切放大一律存 `resources/snapshots/`、MCP 自輸出 `.playwright-mcp/`）已 gitignore，非交付。
- 交付物：`diagrams/NN-<topic>.{html,png,svg}` + `specs/NN-<topic>.md`，**三式同名並存**。

## 🧰 維護原則

- 新踩坑 / 新慣例 → 寫進對應 `reference/`；資產動了 → 更新本檔「固定資產」段。
- memory `diagram-authoring-style` 是薄指標,指向本 skill,別在 memory 重述協議。
