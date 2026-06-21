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
