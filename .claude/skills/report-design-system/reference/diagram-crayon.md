# 系統圖手繪蠟筆風（淺色換膚）

> **🎯 何時讀本檔**：把深色霓虹系統圖**換膚**成 Anthropic 淺色編輯＋手繪蠟筆風的簡報圖（圖①②③風格）、調蠟筆濾鏡 / Rough.js 填色 / 塗鴉標題 / 強度旋鈕時。色票 / 字型 / 元件底層 → [report-pdf.md](report-pdf.md) §2/§3/§5；渲染 / 截圖 / 自檢 → [render-and-qa.md](render-and-qa.md)。
>
> **本檔＝系統圖蠟筆風單一事實來源**（原 `resources/report/design-system.md` §9，已搬入本 skill）。

範圍：報告內的**系統架構圖**（圖①Process/Thread、圖②L0–L5 狀態機、圖③Web phase 狀態機），由 `resources/architecture/diagrams/` 深色霓虹版**換膚**成本設計系統的淺色＋手繪蠟筆風,存 gitignored `resources/presentation/`。**自足單檔**（樣式內聯,不外連 `theme/diagram.css`）。**三張定版成品＝本 skill `assets/benchmarks/`**（HTML+PNG+SVG，gold standard，做圖前對照；見其 `README.md`）。vendored 依賴 `assets/rough.js`（填色 lib）+ `assets/fonts/jason8.ttf`（塗鴉標題字）已隨 skill 自帶。

## 9.1 淺色版面慣例
- 底：ivory `#faf9f5` + 40px 格線 `#ece6da`（`.stage` 雙 linear-gradient）。
- 標題：置中 Fraunces 31 + **珊瑚 `#d97757` 的 FIG.NN 牌**（mono 21/600、珊瑚框）。
- 卡片：ivory/白填底 + 細彩邊 + 圓角 + 極淺陰影；**無純白卡**（legend/chip/閘卡一律 ivory `#faf9f5`）。
- **珊瑚只給「主角環 / hero」**（emit 閉環、input queue inject）；其餘節點用 palette 章節色分類（同類同色）。色票見 [report-pdf.md](report-pdf.md) §2。
- **不畫 process 外框**（背景留乾淨格線,比照各圖一致）。
- **z-index 分層**：背景面板（`.frame`/`.group`）`1` < 箭頭 `.edges` `2` < 內容（卡/標籤）`3` —— 否則不透明面板會蓋掉 SVG 箭頭（圖1 踩過）。
- 多線接同一卡邊 → **接點等距平均分配**（例：machine._emit 右緣 4 線 y434/464/494/524,卡 y404–554 對稱）。

## 9.2 手繪蠟筆技法（核心）
原理（Rough.js／CSS-Tricks「Pencil Effect」）：**低頻位移＝手繪抖動不直；高頻噪聲侵蝕 alpha＝蠟筆紙面顆粒「粉感」**；筆畫要**夠粗**顆粒才不會把線打斷。單純位移（無顆粒）只會像波浪細線、不像蠟筆。

**兩個濾鏡**（放各圖 `.edges <defs>` 內）：
```svg
<!-- 線條/箭頭：userSpaceOnUse 大區域,避免細線位移被裁 -->
<filter id="crayon" filterUnits="userSpaceOnUse" x="-40" y="-40" width="2040" height="1410" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="2" seed="5" result="wob"/>
  <feDisplacementMap in="SourceGraphic" in2="wob" scale="5" xChannelSelector="R" yChannelSelector="G" result="line"/>
  <feTurbulence type="fractalNoise" baseFrequency="0.5 0.62" numOctaves="2" seed="9" result="grain"/>
  <feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.9 -0.1" result="grainMask"/>
  <feComposite in="line" in2="grainMask" operator="in"/>
</filter>
<!-- 卡片外框：objectBoundingBox 區域隨卡縮放（效率高,不必每卡都開大 buffer）-->
<filter id="crayonEdge" x="-12%" y="-15%" width="124%" height="130%" color-interpolation-filters="sRGB">
  <feTurbulence type="fractalNoise" baseFrequency="0.014" numOctaves="2" seed="4" result="wob"/>
  <feDisplacementMap in="SourceGraphic" in2="wob" scale="4" result="ln"/>
  <feTurbulence type="fractalNoise" baseFrequency="0.5 0.6" numOctaves="2" seed="8" result="gr"/>
  <feColorMatrix in="gr" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.95 -0.05" result="grm"/>
  <feComposite in="ln" in2="grm" operator="in"/>
</filter>
```

**套用 — 箭頭線**（只套有 class 的邊：flow/hawk/async;**文字標籤不套**以保清晰;marker 隨 path 一起被濾、箭頭頭也手繪化）：
```css
.edges path, .edges line { stroke-width: 3.0; stroke-linecap: round; }
.edges .hawk { stroke-width: 3.8; }                      /* 主角環粗一階 */
.edges path[class] { filter: url(#crayon); stroke-opacity: 0.82; }
```

**套用 — 卡片外框**（`::before` 畫蠟筆框,**不動底色/文字**;`overflow:visible` 讓抖動外擴不被剪）：
```css
.card, .legend, .note, .chip, .group, .gate, .cmd { border-color: transparent; overflow: visible; }
.card::before, .legend::before, .note::before, .chip::before, .group::before, .gate::before, .cmd::before {
  content:""; position:absolute; inset:0; border-radius:inherit; pointer-events:none;
  border:2px solid var(--edge, var(--gray-edge));
  filter:url(#crayonEdge);
}
.card::before  { --edge: var(--c-edge, var(--gray-edge)); }
.legend::before,.note::before { --edge: var(--rule); }
.chip::before,.cmd::before    { --edge: var(--gray-edge); }
.group::before { --edge: var(--c-edge, var(--cyan-edge)); }
.gate::before  { --edge: var(--cyan-edge); }
```
- **內聯邊特殊卡（hero）**：把 inline `border:…solid <色>` 改 `border:…solid transparent; --c-edge:<色>`,讓 ::before 用該色畫蠟筆框、避免清邊＋蠟筆邊雙框。

## 9.2b 卡片填色 — Rough.js hachure 手繪上色
卡片**內部填色**用 **Rough.js**（vendored `assets/rough.js`，~28KB）重畫成 hachure 斜線手工塗色（Excalidraw 同款，業界/得獎手繪標準做法）；**外框仍用 §9.2 的蠟筆 `::before`**（填色與框分工，使用者定版偏好）。
- 載入：`<script src="rough.js"></script>`（本機檔,免 CDN/SRI;headless 可載。benchmark HTML 在 `assets/benchmarks/`，故引用 `../rough.js`）。
- JS（`window load` 後）：每張 `.card` 讀 `getComputedStyle().backgroundColor` 當填色 → 設 `background:transparent` → 卡內插一張 `z-index:-1` 的 SVG，`rough.svg().path(roundedRectPath, { fillStyle:'hachure', hachureGap, fillWeight, hachureAngle, roughness, bowing, stroke:'none' })` 畫填色,墊在蠟筆框與文字之下。
- **關鍵**：`.card { isolation: isolate; }` 讓卡自成 stacking context,`z-index:-1` 填色才會墊在框後、又在頁面之上 —— **少了它,填色會掉到整卡後面消失**（踩過）。
- 參數：`hachureGap` 5.5（疏密=塗色密度）、`fillWeight` 1.4（塗色筆觸粗細）、`hachureAngle` 每卡 `-41+i%3*8`（角度微變,不呆板）、`roughness` 1.4 / `bowing` 1.4（手抖）。
- **退場**：無 JS → 卡片保留實色 + 蠟筆 ::before 框（graceful fallback）。
- 變體：`fillStyle` 可換 `cross-hatch`（交叉影線）/`zigzag`/`dots`/`sunburst`；密度調 `hachureGap`。
- **範圍＝所有 attribute 框**：選擇器 `.card, .legend, .note, .chip, .cmd, .gate, .group, .misalign, .subphase-tag, .tok, .sw` 全納入（各自 `isolation:isolate`）。**中性淺色框**（ivory/gray,`r≈g≈b`）填色壓深 ×0.95 + `node.opacity 0.6`（否則與頁同色看不見）；**色票 `.sw`** 用其**邊色**填、`hachureGap` 加密(2.2)、inset 1.6 幾乎填滿；**所有框的外框一律走 §9.2 蠟筆 `::before`**（含 `.sw`/`.tok`,JS 把該元素邊色寫進 inline `--edge` 讓框用對色;虛線框 `.misalign::before { border-style:dashed }`）；**`.group` 容器**也填(內層卡浮其上)。
> 來源：[Rough.js fill styles](https://roughjs.com/)、[RoughJS 演算法](https://shihn.ca/posts/2020/roughjs-algorithms/)、[draw.io rough 模式](https://www.drawio.com/blog/rough-style)（Excalidraw 同源技法）。

## 9.2c 手繪塗鴉標題（FIG.NN · 主題）
標題用**手繪塗鴉字 + 輕蠟筆 filter**（字型管「形」、filter 管「質」,別雙重扭形＝會糊）。
- **字型**：拉丁/數字 **Shantell Sans**（麥克筆變體字,Google Fonts @import,wght 800）；繁中 **清松手寫體⑧隨性**（vendored `assets/fonts/jason8.ttf`,SIL OFL 可商用可嵌,Chromium 直吃 ttf 免轉 woff2,~8MB）；缺字 fallback **jf 粉圓 Huninn**（Google Fonts,圓潤、零缺字保底）。
  ```css
  @font-face { font-family:'Jason Scribble'; src:url('../fonts/jason8.ttf') format('truetype'); font-display:swap; }
  .title { font-family:"Shantell Sans","Jason Scribble","Huninn",var(--font-display);
           font-size:33px; font-weight:800; filter:url(#crayonText); }
  ```
- **`#crayonText` filter**（套 `.title`,連 FIG 牌一起吃）：輕位移(`feDisplacementMap scale 2.6` 邊抖)+ 顆粒**只咬邊**(`feColorMatrix` alpha 末兩值 `-2.4 2.0`＝咬少→字實偏深;往 `-1.2 1.06` 走＝更碎更淡)。scale 小保易讀,**比卡片邊框 filter 更克制**。
- **FIG.NN 牌**：`.num` 字型也用塗鴉字（Shantell）、色 **深珊瑚 `#c25e39`**、框加粗 `2.5px`。
- **副標 `.subtitle` 維持乾淨 mono**（`JetBrains Mono`）做層次,不套手繪。
- 缺字驗證：清松逐字手寫,生僻字可能缺 → 上線前用**實際標題字串**渲染檢查(缺字會 fallback Huninn,不會 tofu)。
> 來源：[Shantell Sans (ArrowType)](https://github.com/arrowtype/shantell-sans)、[清松手寫體](https://github.com/jasonhandwriting/JasonHandwriting)、[jf 粉圓 Huninn](https://github.com/justfont/open-huninn-font)、[Codrops feDisplacementMap on text](https://tympanus.net/codrops/2019/02/12/svg-filter-effects-conforming-text-to-surface-texture-with-fedisplacementmap/)。

## 9.3 渲染 / 校驗
> 完整渲染 / 截圖 / 自檢 / SVG 匯出管線見 [render-and-qa.md](render-and-qa.md)。本節只列蠟筆圖特有要點：
- 本機 Chrome 截圖：`chrome --headless --disable-gpu --force-device-scale-factor=2 --window-size=W,H --virtual-time-budget=15000 "--screenshot=out.png" "file:///…/NN.html"`（路徑空白用 `%20`）。
- ⚠ **`--headless=new` + `--screenshot` 本機不寫檔**（踩過）→ 用舊 `--headless`;濾鏡重,`--virtual-time-budget` 給足（≥12000）。
- 驗收：Read 截圖目視 + PowerShell `System.Drawing.Bitmap.GetPixel` 取樣關鍵點色值（如確認接點/底色 hex）。

## 9.4 強度旋鈕
- 更粉/顆粒重 → grain `feColorMatrix` alpha 末兩值更負（`0.9 -0.1` → `0.9 -0.15`）。
- 更彎/手繪重 → `feDisplacementMap scale`↑（線 5→8）。
- 更透 → `stroke-opacity`↓（0.82→0.65）。
- 更粗蠟筆桿 → `stroke-width` / 框 `border` ↑。
- 想要 Excalidraw「多筆 sketchy」而非「蠟筆顆粒」→ 改走 **Rough.js**（隨機化 bezier 控制點、每線多筆疊畫）。

> 來源：[Rough.js](https://roughjs.com/)、[CSS-Tricks: Pencil Effect](https://css-tricks.com/creating-a-pencil-effect-in-svg/)、[Here Dragons Abound](https://heredragonsabound.blogspot.com/2020/02/creating-pencil-effect-in-svg.html)、[Codrops feTurbulence](https://tympanus.net/codrops/2019/02/19/svg-filter-effects-creating-texture-with-feturbulence/)。
