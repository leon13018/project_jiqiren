# Visual system — 共用 theme、字體 / 色彩 / 版面慣例

> 全圖共用一套視覺語言才有「系列感」。theme 已釘死(圖①②驗證),動手只在「自由軸」(layout + 本圖主角)花心思,別重訂風格。

## theme 在哪 / 怎麼用
- canonical：`resources/architecture/diagrams/theme/{tokens.css,diagram.css}`。
- 每張圖 HTML：`<link rel="stylesheet" href="theme/diagram.css">`(`diagram.css` 自己 `@import tokens.css` + Google Fonts IBM Plex)。
- 畫布：`<div class="stage" style="...">`,本圖 `<style>.stage{width:Wpx;height:Hpx}</style>` 設尺寸(圖① 1960×1280、圖② 1960×1360;**畫大沒關係,組件不相碰優先**)。

## 設計語言(釘死,別改)
- **背景**：近黑 OKLCH + 2 池柔光 radial-gradient + 極淡儀表格線(收斂 AI-default 的 glassmorphism 味、扣回「Raspberry Pi 嵌入式儀表」主題)。
- **卡片**：有色 iOS 毛玻璃 —— 半透 OKLCH fill(透得出背景光暈)+ 亮邊 + 頂緣反色光 sheen + 立體投影 + 霓虹 glow + 圓角。色由 modifier class 設 `--c-fill/--c-edge/--c-glow/--c-tone`。
- **色彩一律 OKLCH**(Chromium 原生;tokens.css 內)。

## 字體角色(IBM Plex 超族,刻意配對)
| 角色 | 字體 | 用在 |
|---|---|---|
| code 識別字 | **IBM Plex Mono** | 類別 / 函式 / state key / 變數 / `FIG.NN` / eyebrow(它們本來就是程式符號,等寬編碼「這是真 code」)|
| 英文標題 / 強調 | IBM Plex Sans | 圖標題、卡 name(非 code 時)|
| 繁中正文 | IBM Plex Sans TC | desc / note / tag(細一級、清楚)|

> web 字經 `@import` 載,**截圖前一定等 `document.fonts.ready`**(否則截到 fallback)。純 HTML/CSS 無 Mermaid 截字 bug。

## 色彩語意是「每圖專用 + 配 legend」
色票固定(藍/綠/青/紫/橘/灰 + tone),**但每張圖的「顏色代表什麼」自己定並畫 legend**:
- 圖①(thread):藍=主線程 / 綠=常駐 daemon / 青=每輪一生 / 橘=一次性 / 紫=queue·bus / 灰=子程序·外部。
- 圖②(state):藍=L1 / 綠=dialog / 橘=L4 / 紫=L5 / 青=confirm 閘 / 灰=L0·終止·外部。
> 顏色要**編碼內容真實分類**(thread 生命週期、state 用途),不是裝飾。

## 簽名元素(signature)
1. **等寬大寫 eyebrow 分類標**(全系列辨識 + 編碼真實分類):每張主卡頂 `— DAEMON · 常駐` / `PHASE STANDBY · cart 空` 之類。`FIG.NN` 等寬描邊徽章。
2. **每張圖再挑一個「主角」**(frontend-design 的 thesis):用 `.hawk`(粗暖金高亮弧)或其他手法,把這張圖最核心的一件事做成視覺焦點 —— 例圖② 把 `enter_hawk` 回流弧做成主角(點明「這是循環不是直線」)。boldness 集中一處,其餘安靜。

## 元件 class(diagram.css 提供)
- `.stage` 固定畫布;`.frame` + `.frame-label` 系統邊界框;`.card` 毛玻璃卡 + 色 modifier(`.blue/.green/.cyan/.purple/.orange/.gray`);`.eyebrow` 分類標;`.group` + `.group-label` 子框;`.chip` 灰外部小掛件;`.note`/`.legend` 角落說明;`.edges` SVG 箭頭層(`.flow` 實線 / `.async` 虛線 / `.hawk` 主角弧 / `.elabel`·`.hawklabel` 標籤)。
- 卡內結構：`.eyebrow`→`.name`(mono)→`.meta`(mono 小)→`.desc`(cjk)。`.card` 已 `flex column + justify-center`(內容垂直置中、上下留白對稱)。

## 版面鐵則
- **緊湊但不相碰**:組件之間 ≥30px,誰都不碰誰、不碰 frame;畫大沒關係(`browser_evaluate` 量座標驗證)。
- 🔴 **圓角留白 · 字別貼邊**:圓角卡 / group / pill / chip 的文字一律離邊 ≥ 圓角半徑(card r≈18 / group r≈20 → 文字內縮 ≥ ~22px),**絕不把字放在剛好最邊邊** —— 會被圓角切到 / 卡在彎角看起來溢出、不好看(圖① STT `group-label` `left:16px` < r 貼邊被使用者抓;theme `.group-label` 已調至清開彎角,但 HTML 內任何自訂絕對定位文字要自己守)。
- 🔴 **卡內容垂直置中**:卡片內容上下留白對稱(topGap = botGap),**不准偏靠上 / 靠下**(theme `.card` 已 `justify-content:center`;group-label / 其他絕對定位文字要自己確保)。`browser_evaluate` 量每卡 top/bot gap 驗證 —— 自檢必看項。
- 🔴 **零卡片覆蓋(legend/note 也算)**:任何元素**不准與任何卡片重疊**,哪怕只壓一點、哪怕文字沒互相干擾 —— 卡片被覆蓋就傷美觀、**絕對不允許**(圖② legend 壓 EXIT 卡被抓)。legend/note 收角仍受 ≥30px 不相碰約束;`browser_evaluate` 量**所有** bbox 兩兩不交疊(含 legend/note vs 每張卡)。
- 🔴 **文字不溢出卡片**:任何卡 / group / pill / chip 的文字一律收在邊框內(留圓角 padding),**不可溢出邊框或頂破圓角**;標籤太長就縮短 / 斷行 / 拆元素(長語意拆進卡身或 note),不可硬撐一行頂出框(圖② confirm 長 group-label 溢出被抓)。
- 🔴 **卡片大小取決於內容多寡 · 不做空蕩大卡**:卡 / group / pill / chip 的尺寸由**內容多寡**決定 —— 內容少就做小卡,**絕不為了佔位 / 對齊 / 撐滿某條邊而做一個一堆空白的大卡**(尤其右半 / 下半幾乎沒字 = 浪費空間、視覺鬆散難看)。內容少的卡縮到剛好包住內容(留正常 padding + 圓角留白),再**找合適的空角 / 縫隙塞進去**(像 chip / 小卡靠邊收),別硬攤成全幅大卡(圖② L0 共通 NLU 全幅基座帶內容只兩短行、右側大片空白被抓)。判準:`browser_evaluate` 量卡的內容實際 bbox vs 卡框,**右 / 下若有大片(>~25%)空白且非刻意對齊 → 縮卡**。「畫大沒關係」只指**畫布**可大以求不相碰,**不是指單卡可空蕩攤大**。
- 🔴 **箭頭線 ↔ 文字零交疊**:SVG 箭頭線及箭頭頭**絕不穿過 / 蓋住任何文字**(卡內文字 / eyebrow / 邊標籤 / group-label),文字也不壓在不相關的線上 —— 線走清空 gutter 繞開所有字,邊標籤落線中段清空處 + 深色 halo(圖② 連接箭頭橫穿 confirm 長標籤被抓,**決不能再犯**)。自檢逐條線追視全程有無壓字。
- 🔴🔴 **線↔三角箭頭頭同色（改線色必連頭一起改）**:改任何箭頭線顏色,**必連其三角形 marker 一起改、兩者同色**(線 gold 頭別色 = 不搭嘎,使用者≥3 次抓包)。
  - **真正坑**:marker `<path>` 也吃 `.edges path { fill:none; stroke:var(--arrow) }` → 三角形被劫持成「無填 + 淡藍描邊」,跟線不同色;**光在 HTML marker 寫 `fill="var(--arrow-hawk)"` 無效**(presentation attr 輸給 CSS rule)。這是「設了同 token 卻仍不同色」反覆發生主因。
  - **正解(已進 theme)**:`.edges marker path { stroke:none } / .edges marker#ah path { fill:var(--arrow) } / .edges marker#ah-hawk path { fill:var(--arrow-hawk) }`(ID 提 specificity 蓋劫持);新圖 marker 用 `id=ah`/`id=ah-hawk` 自動同色。
  - **和諧**:金弧配暗背景要柔(`--arrow-hawk` = `oklch(79% 0.12 82 / .75)` width 3.0)。
  - **自檢**:`getComputedStyle().fill` 在 marker context 會回誤值、不可信 → **render 後 GetPixel 取「線中段」vs「箭頭頭實體」兩處 RGB 比對**,相近才過(曾頭=淡藍 (196,216,240)、線=金 (170,143,78))。
- 🔴 **無大片死空白 · 有空間就往上擠**:不留大片無意義空白;元素上方有明顯空白就往上挪填滿、垂直分布均衡緊湊(圖② L0 基座帶上方留空被抓)。下半截空蕩 → 上移元素 / 縮畫布高;「畫大」只為不相碰、非留死空白(仍守 ≥30px + 不溢框)。
- 🔴 **箭頭走線整齊流暢**(使用者特別強調):走線**非常整齊 / 流暢 / 舒服 / 整潔**,不是連到就好——正交對齊同 lane、一致圓角轉折、平行線等距、最少彎折/交叉/斜穿、收束對齊;**必要時反覆截圖看走線、改走法**(連走線方式都改、不只調座標)直到順眼。箭頭層是圖乾不乾淨的關鍵。**自檢必裁切放大每條線「兩端連接點」**:箭頭頭真觸卡邊、起點實接、無浮空線頭/怪鉤/迴圈/與別線糾纏(不只看中段與交叉;③ ConfirmSheet 左緣連接被漏看抓包)。
- **箭頭標籤壓在自己的線中段**(`text-anchor=middle` 放路徑中點,深色 halo 蓋住線)—— 不要飄在線旁邊。
- **箭頭走清空 lane**,不擦過不相關的卡;同 x 垂直堆疊的卡之間別讓別的箭頭穿過(繞最外側 gutter)。
- **先畫卡片層(無箭頭)→ 截圖修版面 → 再加 SVG 箭頭層**(分兩階段較穩)。
- legend 收一角、note 補空白角落(填「所以呢」+ 避免大片空白)。
- `body` 用 block flow + `.stage{margin:0 auto}`(別 flex 置中 → 視窗矮時裁頂不可捲;見 render-pipeline §4)。

## frontend-design 落地(動手前 invoke /frontend-design)
- **grounded in subject**:Project_01 = Raspberry Pi 人形銷售機器人。距離感、語彙從主題世界來(嵌入式儀表、攤位連續叫賣…)。
- **structure is information**:eyebrow / 編號 / 分組只在「編碼真實內容」時用;L1–L5 是真層序(非裝飾編號)。
- **spend boldness in one place**:玻璃只當載體,主角元素是唯一記憶點,其餘安靜;「離家前拿掉一個配件」。
- **copy**:站在讀者角度、具體、主動語態;標籤=標籤、一物一職。
