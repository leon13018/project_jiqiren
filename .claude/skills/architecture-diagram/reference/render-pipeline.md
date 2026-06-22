# Render pipeline — 本機 Chromium 渲染 / 截圖 / 高解析匯出 / 自檢

> 把 `diagrams/NN-*.html` 變成乾淨無黑邊的 **2× PNG + SVG**。所有指令、座標、配方都來自圖①②實證(踩過黑邊 / 截字 / 快取 / DPR 各種坑)。
>
> **本檔＝產線 render 機制**（DPR 匯出 / bbox dump / SVG 組裝 / 平行序列化）。**視覺風格 / 色票 / 蠟筆濾鏡 / 視覺 critical gotchas → `report-design-system` skill**（`diagram-crayon.md` + `render-and-qa.md`）；本 skill 已改宗淺色蠟筆風、不再產出深色霓虹。

## 目錄
1. 為何這套(不用 Mermaid / 不用 file://)
2. 起 no-cache 本機 server
3. Playwright MCP 的 4 個 quirk(每次都會遇到)
4. 渲染一張圖(navigate → fonts.ready → 截圖)
5. 自檢:裁切放大逐項核對(反覆修到完美)
6. 高解析匯出配方(DPR 反推 + 填滿,零黑邊)
7. 組 SVG(內嵌 2× PNG)
8. gitignore render 暫存

---

## 1. 為何這套
Mermaid 自定義度低(dagre 佈局搶方向盤無法精確擺位、parser 不認進階 CSS、濾鏡只能 hack)。改 **HTML/CSS 絕對定位卡片 + SVG overlay 畫箭頭**,用無頭 Chromium 截圖 —— SVG 蠟筆濾鏡(`feTurbulence`+`feDisplacementMap`) / Rough.js hachure 填色 / web 字全部原生支援。**純 HTML/CSS 沒有 Mermaid 的「測量字寬≠渲染字寬」截字 bug**(那是 Mermaid 專屬;這裡等 `fonts.ready` 即可)。

## 2. 起 no-cache 本機 server

> ⚡ **淺色蠟筆風是自足單檔**（樣式內聯、不外連 `theme/*.css`）→ **可直接 `chrome --headless --screenshot "file://…"` 截圖、免 server**（見 `report-design-system/reference/render-and-qa.md §1`：用舊 `--headless`、`--virtual-time-budget≥12000`；把 `rough.js`+`fonts/jason8.ttf` 複製到圖檔旁）。下面 no-cache server 只在**用 Playwright MCP**（它擋 `file:`）時才需要；自足單檔的截圖管線不必起。

**Playwright MCP 擋 `file:` 協議**,必走 http。**但 plain `python -m http.server` 不送 cache header → Chromium 會快取 `theme/*.css`,你改了 CSS 重渲染卻沒生效(HTML 內聯改有效、CSS 檔改無效,極易誤判「改了沒用」)。** 一定用會送 `Cache-Control: no-store` 的小 server:

```
py -3.14 "<skill>/scripts/nocache_server.py" "<repo>/resources/architecture/diagrams"
```
背景跑(`run_in_background`),服務 diagrams 目錄;之後一律 `http://127.0.0.1:8191/NN-*.html`。全程畫圖只需這一個 server,畫完再關。

> 🔴 **改了 theme/CSS 卻沒生效?（瀏覽器層快取,no-cache server 也救不了）**:no-cache server 送 `no-store`,但 **Chromium 本身可能已把同一 origin(同 host:port)的舊 CSS 快取在記憶體** —— 你在**同一個 server 已 serve 過舊版**後改 CSS,重 navigate 仍吃舊值(2026-06-22 圖⑤ theme `translate(22,16)→(22,7)` 改了卻反覆 render 出舊 offset=16、耗多輪才查出)。**正解 = 換全新 origin**:起一個**沒用過的新埠**(如 8193/8194)的 no-cache server,新 origin 強制重抓 CSS。驗證:`browser_evaluate` 量該元素的 `getComputedStyle().transform`(或實際值)＝新值才算 baked,別只看「我改了檔」。多 subagent 各自 render 不同圖時,各用**不同埠**(8191/8192/8193…)也順便避免共用 origin 快取互擾。

> 瀏覽器工具(`browser_navigate` / `browser_resize` / `browser_evaluate` / `browser_take_screenshot`)是 **Playwright MCP**,deferred → 先 `ToolSearch` 載入:`select:mcp__plugin_playwright_playwright__browser_navigate,mcp__plugin_playwright_playwright__browser_resize,mcp__plugin_playwright_playwright__browser_evaluate,mcp__plugin_playwright_playwright__browser_take_screenshot`。下文用短名指稱。

## 3. Playwright MCP 的 4 個 quirk
1. **`file:` 被擋** → 走上面的 http server。
2. **瀏覽器每輪 idle 會被關**:當輪「首次」`browser_navigate` 常 `Target page... closed` error → **再打一次同樣 navigate 就重啟**。重啟後 viewport 重置 → 要重 `browser_resize`。
3. **`browser_resize` 設的是 device px**;CSS 視窗 = device ÷ DPR。**DPR 隨環境 / 瀏覽器實例而異 —— 實測過 0.667 也測過 1.0,千萬別假設**。**每次一定先量再算**:`browser_evaluate` 回 `window.devicePixelRatio`,所有 scale 都用這個量到的值算,絕不寫死數字。
4. **`scale:'css'` 截圖 = device viewport 像素**(不是 CSS 像素)。所以截圖解析度 = 你設的 device viewport。要多大圖就把 device viewport 設多大(見 §6)。

## 4. 渲染一張圖（自檢用 1:1 原生解析）
要得到「= native 畫布尺寸(如 1960×1280)」的乾淨自檢圖:
- `browser_navigate` → `http://127.0.0.1:8191/NN-*.html`(失敗重打一次)
- `browser_resize(nativeW, nativeH)`(device viewport = native)
- `browser_evaluate`：等字 + 把畫布縮放填滿 CSS 視窗、原點歸位:
  ```js
  async () => {
    await document.fonts.ready;
    const dpr = window.devicePixelRatio;            // 量,不要假設
    document.body.style.margin = '0';
    const st = document.querySelector('.stage');
    st.style.margin='0'; st.style.transformOrigin='top left';
    st.style.transform = `scale(${1/dpr})`;          // 填滿:CSS視窗 = native/dpr，故縮 1/dpr
    return `dpr=${dpr} stage=${Math.round(st.getBoundingClientRect().width)}`;
  }
  ```
  > 不縮放 + 用 `flex/margin:auto` 置中 → device viewport 比畫布大時畫布只佔中間一塊、四周變黑邊(這就是圖① 黑邊的成因)。**填滿才無邊。**
- `browser_take_screenshot`(存進 `resources/snapshots/`,檔名 `NN-vN.png` —— gitignored)。

## 5. 自檢:裁切放大逐項核對
**自檢順序:先全圖、再局部 —— 兩者都要,缺一不可。**
1. **先 `Read` 整張全圖**(可 downscale 到 ~900px 寬)掃一遍 ——**整個畫布範圍都要看過**,抓全局問題(黑邊 / 大片空白 / 某 band 撞另一 band / 整體失衡)。**絕不能只截某一小區域就算自檢**(只抽查局部會漏掉別處的問題 —— 圖① 只裁短卡、漏了右側線亂 + 長文字溢出被抓包)。
2. **再用 `System.Drawing`(PowerShell)裁局部放大**,`Read` 逐塊細看(全圖看不清的小字 / 箭頭頭 / 標籤壓線)。
**反覆修到完美才給使用者,不給半成品。**

⚠️ **必裁的區域(圖①②都在這些漏過)**：
- **箭頭匯聚區**(多箭頭收束的地方)—— 不能只裁卡片;線會穿過不該穿的卡、或交纏。
- **每張卡的最長文字**(desc / note / 命令列)—— 看有沒有 `overflow:hidden` 截字。
- **箭頭標籤**—— SVG 在卡片 DOM 之前 = **渲染在卡下層**,標籤延伸進卡片 bbox 會被卡蓋住,看起來像「框裏字被截」→ 標籤一律落在卡片之間空白、別超進卡。

逐項清單:字看得到嗎 / 有沒有截斷 / 有沒有衝出框 / 顏色對比夠嗎 / 箭頭線可見嗎(**有沒有箭頭頭** —— 別只有線沒頭,見 §7 marker;**箭頭頭顏色與線同色嗎** —— theme `.edges marker#id path` 修後 by-construction 同色,若要驗一律 **GetPixel 取「線中段」+「箭頭頭三角形實體」各一點比色相明度**,別用 `getComputedStyle(markerPath).fill`,marker context 它會回 `none`/未解析 `var()` 誤判)/ 標籤壓在自己的線上嗎 / 組件之間 ≥30px 不相碰嗎 / 卡內容垂直置中嗎(`browser_evaluate` 量每卡 top/bot gap 應相等)/ **跨 band 元件 y 區間不重疊嗎**(常見:某條 flow lane 或某排卡的 y 撞穿另一 band 的卡 → `browser_evaluate` 量各 band top/bottom)。

裁切範本(改座標即可):
```powershell
Add-Type -AssemblyName System.Drawing
$src=[System.Drawing.Image]::FromFile("<repo>\resources\snapshots\NN-vN.png")
$b=New-Object System.Drawing.Bitmap($w,$h);$g=[System.Drawing.Graphics]::FromImage($b)
$g.DrawImage($src,(New-Object Drawing.Rectangle(0,0,$w,$h)),(New-Object Drawing.Rectangle($x,$y,$w,$h)),'Pixel')
$b.Save("<repo>\resources\snapshots\NN-crop.png");$g.Dispose();$b.Dispose();$src.Dispose()
```
> System.Drawing 踩坑:`Add-Type -AssemblyName System.Drawing` **每個獨立 ps 腳本都要重下**(否則 `[System.Drawing.Image]` TypeNotFound);若要高品質縮圖,`$g.InterpolationMode` 要賦 **enum 型別**(`[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic`),賦字串會 PropertyNotFound。

## 5.5 QA 產出物:bbox dump（canonical 配方,implementer 產給 QA panel 讀）

QA panel 只讀靜態產出物(PNG + 此 dump)、不 render → 影像 token 不進主對話。**由 orchestrator**（非 implementer，見 SKILL step 5.5）render 後跑下面 `browser_evaluate`、把回傳字串 **`Write` 到絕對路徑** `<repo>/resources/snapshots/NN-bbox.json`；再用 PowerShell 對 `NN-2x.png` 補 `arrowSamples[]` 像素取樣（見下「§5.5b」）併入同一 JSON。

> 🔴 **路徑寫死、絕不用相對路徑/CWD**：subagent 的 CWD **不保證在 repo root**,相對路徑會落到根目錄 → 觸發 code_map Stop hook(已踩 ≥3 次「`NN-bbox.json` 誤落 root」)。一律用上面**絕對路徑**寫進 `resources/snapshots/`(已 gitignore)。`NN-2x.png`/`NN-native.png` 截圖同理走絕對 snapshots 路徑。

> 🔴 **selector 必含「所有可見文字元素」,尤其 band/group 標籤**:overlap 掃描的盲點 = 漏掉沒被 selector 量到的標籤(2026-06-22 ④ 踩過 —— band 標籤 vs 首節點重疊、`overlaps=[]` 卻沒抓到,被使用者肉眼抓包)。**band/group 標籤若是 `::before`/pseudo 量不到 → 在 HTML 改成可量測真元素**(span),再納入 selector。dump 完**自己跑兩兩 overlap 檢查**(含標籤 vs 節點、標籤 vs 卡)。

```js
async () => {
  await document.fonts.ready;
  const stage=document.querySelector('.stage'); const sb=stage.getBoundingClientRect();
  const rel=r=>({left:Math.round(r.left-sb.left),top:Math.round(r.top-sb.top),right:Math.round(r.right-sb.left),bottom:Math.round(r.bottom-sb.top),w:Math.round(r.width),h:Math.round(r.height)});
  const out={stage:{w:Math.round(sb.width),h:Math.round(sb.height)},dpr:window.devicePixelRatio,elements:[],cards:[],overlaps:[]};
  // selector 納入所有卡 + 角落說明 + 所有「標籤」類(band/group/frame) + 時序節點(.node/.screen,曾漏致 ④ 節點不在掃描內)
  const sel='.card,.node,.screen,.group,.chip,.legend,.note,.title,.subtitle,.frame,.frame-label,.group-label,.band-label,.lane,.lifeline,.band';
  const els=[...document.querySelectorAll(sel)].map(el=>({cls:el.getAttribute('class'),label:(el.querySelector('.name,.eyebrow,.nf,h4')?.textContent||el.textContent||'').trim().slice(0,32),box:rel(el.getBoundingClientRect()),el}));
  out.elements=els.map(({el,...e})=>e);
  // 文字溢框檢查(scrollWidth>clientWidth)：卡/節點內任何文字行溢出容器即列入(圖④ node⑧ read_customer_input(timeout) 溢右框、被使用者抓包)
  out.textOverflow=[];
  document.querySelectorAll('.card,.node,.screen,.chip,.legend,.note').forEach(c=>c.querySelectorAll('.name,.nf,.nd,.meta,.desc,.eyebrow').forEach(t=>{if(t.scrollWidth>t.clientWidth+1)out.textOverflow.push({owner:(c.querySelector('.name,.nf')?.textContent||'').trim().slice(0,24),part:t.getAttribute('class'),scroll:t.scrollWidth,client:t.clientWidth});}));
  // 兩兩 overlap(排除背景/容器 band/frame/lane/lifeline/group 自身,但保留其「標籤」)
  // group 也是容器(像 STT session 子框)、by-design 包成員 → 排除,否則 group vs 內部卡誤報(2026-06-22 圖⑤ 踩過)
  const bg=/\b(band|frame|lane|lifeline|group)\b/; const isBg=c=>bg.test(c)&&!/label/.test(c);
  for(let i=0;i<els.length;i++)for(let j=i+1;j<els.length;j++){const a=els[i],b=els[j];if(isBg(a.cls)||isBg(b.cls))continue;const A=a.box,B=b.box;if(A.left<B.right&&B.left<A.right&&A.top<B.bottom&&B.top<A.bottom)out.overlaps.push([a.cls+'|'+a.label.slice(0,16),b.cls+'|'+b.label.slice(0,16)]);}
  // 每卡內容垂直置中
  document.querySelectorAll('.card').forEach(el=>{const cr=el.getBoundingClientRect();const kids=[...el.children];if(!kids.length)return;const tops=kids.map(k=>k.getBoundingClientRect().top),bots=kids.map(k=>k.getBoundingClientRect().bottom);out.cards.push({label:(el.querySelector('.name,.eyebrow')?.textContent||'').trim().slice(0,24),topGap:Math.round(Math.min(...tops)-cr.top),botGap:Math.round(cr.bottom-Math.max(...bots))});});
  // 死空白量測（治本「無大片死空白」gotcha → 可量的 FAIL 閘）：內容垂直 extent + 上下邊距 + 6×5 占用網格
  // 排除 title/subtitle 與任何 ~滿寬 band（只算真內容元素）
  const real=els.filter(e=>!/\b(title|subtitle)\b/.test(e.cls||'')&&e.box.w<sb.width*0.95);
  if(real.length){const cTop=Math.min(...real.map(e=>e.box.top)),cBot=Math.max(...real.map(e=>e.box.bottom)),H=Math.round(sb.height),W=Math.round(sb.width);
    out.fill={contentTop:cTop,contentBottom:cBot,stageH:H,topMargin:cTop,bottomMargin:H-cBot,bottomDeadRatio:+(((H-cBot)/H).toFixed(3))};
    // ⚠ occupancy 排除容器 frame（group/frame/band/lane/lifeline）——否則大 frame 把整片計為填充、
    //   掩蓋 frame 內部空洞（踩過：⑥ STT SESSION group 內左半中段 666×342 純背景卻 occupancy 全 1）。
    const realOcc=real.filter(e=>!/\b(group|frame|band|lane|lifeline)\b/.test(e.cls||''));
    const C=6,R=5,occ=[];for(let r=0;r<R;r++){const row=[];for(let c=0;c<C;c++){const cl=c*W/C,ct=r*H/R,cr=(c+1)*W/C,cb=(r+1)*H/R;row.push(realOcc.some(e=>e.box.left<cr&&cl<e.box.right&&e.box.top<cb&&ct<e.box.bottom)?1:0);}occ.push(row);}
    const empties=[];for(let r=0;r<R;r++)for(let c=0;c<C;c++)if(!occ[r][c])empties.push([r,c]);
    out.occupancy={cols:C,rows:R,grid:occ,emptyCells:empties,emptyCount:empties.length};}
  return JSON.stringify(out);
}
```
> `overlaps` 非空即版面 FAIL(含標籤撞節點)。「band/group 標籤 vs 該帶首節點」尤其要 clear ≥ 標籤高 + 留白(時序帶實測首節點 top 需 ≥ band_top + ~60px)。

**dump schema（QA panel 依此欄位讀；缺欄位＝dump 不合格、orchestrator 重產，否則 QA 靜默略過 = 假 PASS）**：
- `stage{w,h}` · `dpr` — 畫布尺寸 + 實測 DPR。
- `elements[]{cls,label,box{left,top,right,bottom,w,h}}` — 每個可見元素 bbox（相對 stage）。
- `overlaps[][2]` — 兩兩相交配對（**非空＝版面 FAIL**）。
- `textOverflow[]{owner,part,scroll,client}` — 文字溢框（**非空＝FAIL**）。
- `cards[]{label,topGap,botGap}` — 每卡內容上下留白（topGap≠botGap 即非垂直置中）。
- `arrowSamples[]{edge,lineMidRGB:[r,g,b],headTipRGB:[r,g,b]}` — 每條有色邊（`.hawk` / 任何非墨色線）的「線中段」與「箭頭頭三角實體」像素（**QA-B 比色用，免 live GetPixel**；兩者色相明度相近才算「線↔頭同色」過）。
- `fill{contentTop,contentBottom,stageH,topMargin,bottomMargin,bottomDeadRatio}` — 內容垂直 extent（排除 title/subtitle/滿寬 band）+ 上下死邊距。**畫布必須貼著內容**：`topMargin` 與 `bottomMargin` 應大致對稱（差距 >2× 即沒貼內容）；`bottomDeadRatio > 0.12`（底部留白 >12% 畫布高）＝**過高沒 trim ＝ FAIL**（治本「`.stage` height 寫死／『畫大』被誤讀成畫布開高」這個每次都中的病）。
- `occupancy{cols,rows,grid,emptyCells,emptyCount}` — 6×5 占用網格（真內容覆蓋哪些格，**已排除容器 frame**＝intra-frame 空洞會現形）。**任一整列全空 / 任一整行全空 / 任一 2×2 全空塊 ＝ 大片死空白 FAIL**（catch 任何方位的空塊：底帶／頂帶／某角，不只垂直邊距）。`emptyCells` 給座標 `[row,col]` 供回退定位。
  > ⚠ binary「碰到即 1」的盲點：被 frame 計入、或只靠單薄內容/一條線掃過的格仍記 1，但目視可能很空。**QA-A 對任何「只靠 frame 或稀疏內容佔住」的可疑格務必做 ink-ratio 抽查**（PowerShell System.Drawing 數該格非背景像素佔比，<~5% 視同空——踩過 ⑥ group 內空洞 occupancy 全 1、⑦ 右上角 ink 僅 2.66% 失衡，皆 binary 沒抓到、靠 ink-ratio 才現形）。

### 5.5b arrowSamples — orchestrator render 後補像素取樣
`browser_evaluate` 量不到 rendered 點陣 → orchestrator 在截完 `NN-2x.png` 後，兩步補進 dump：
1. `browser_evaluate` 回每條有色邊的取樣座標（stage 座標）：
   ```js
   async () => [...document.querySelectorAll('.edges path.hawk, .edges path[class]')].map(p=>{
     const L=p.getTotalLength(), m=p.getPointAtLength(L/2), e=p.getPointAtLength(L); // 中點 + 終點(≈箭頭頭)
     return {edge:p.getAttribute('class'), mid:[Math.round(m.x),Math.round(m.y)], tip:[Math.round(e.x),Math.round(e.y)]};
   })
   ```
2. PowerShell 對 `NN-2x.png` GetPixel（座標 ×2 = 2× PNG 像素；箭頭頭往線反方向內縮幾 px 取三角實體而非尖端空白），寫成 `arrowSamples[]` 併入 `NN-bbox.json`：
   ```powershell
   Add-Type -AssemblyName System.Drawing
   $bmp=New-Object System.Drawing.Bitmap("<repo>\resources\snapshots\NN-2x.png")
   $p=$bmp.GetPixel($x*2,$y*2); "{0},{1},{2}" -f $p.R,$p.G,$p.B; $bmp.Dispose()
   ```
> 為何不讓 QA 自己 GetPixel：QA panel 不 render（無活瀏覽器、且影像 token 要留在 QA 外），GetPixel 需對 render 後的 PNG 操作 → 由 orchestrator render 當下一次取樣寫進 dump，QA 比 dump 數值即可（解「GetPixel ⊥ no-render」矛盾）。

## 6. 高解析匯出配方（DPR 反推 + 填滿，零黑邊）
要 **N× native** 的交付圖(預設 N=2):
1. `browser_resize(nativeW*N, nativeH*N)` —— device viewport = 目標像素 = 截圖解析度。
2. `browser_evaluate`：
   ```js
   async () => {
     await document.fonts.ready;
     const dpr = window.devicePixelRatio;             // 量
     // html/body 背景填 --bg-base(別用 transparent):dpr 常是 1.0000000149 這種浮點,
     // scale=N/dpr 比理想小一丁點 → 畫布右/上邊角差 ~1px 沒蓋到 → 透出灰 (44,44,44)。
     // 填深底 → 那 1px 縫顯深色、四角驗得過(圖① 踩過,只 TR 角 (44,44,44))。
     const bg = getComputedStyle(document.documentElement).getPropertyValue('--bg-base').trim();
     document.documentElement.style.background = bg;
     document.body.style.background = bg;
     document.body.style.margin='0';
     const st=document.querySelector('.stage');
     st.style.margin='0'; st.style.transformOrigin='top left';
     st.style.transform = `scale(${N/dpr})`;           // 填滿:CSS視窗=native*N/dpr，畫布要放大 N/dpr
     const r=st.getBoundingClientRect();
     return `box=${Math.round(r.width)}x${Math.round(r.height)} @(${Math.round(r.left)},${Math.round(r.top)})`;
   }
   ```
   - **`margin` 一定歸 0**:留著 `margin:0 auto` 會把畫布**佈局框**置中(偏移 transform 原點)→ 右下角變灰 / 黑(圖① 踩過)。box 要回報 `@(0,0)`。
3. `browser_take_screenshot` → `resources/snapshots/NN-2x.png`(暫存;四角驗過再複製進 `diagrams/NN-topic.png` 交付)。
4. **驗證(PowerShell `GetPixel` 四角)**:尺寸 = `nativeW*N × nativeH*N`,**四角像素都該是畫布本身深色背景 / 光暈**(約 `(4,7,16)` 或帶色光暈);**大片**灰 `(44,44,44)` / 純黑 = margin/scale 真錯,回 step 2 查(`@(0,0)` 嗎、margin 歸 0 嗎)。**單一角 1px 灰** = dpr 浮點邊縫,step 2 的 `--bg-base` 底色已蓋掉,不再灰。

> 數學:截圖像素 = device viewport;CSS 視窗 = device ÷ dpr;畫布縮放 s 後 CSS 尺寸 = native×s,要 = CSS 視窗 → **`s = (device/dpr)/native = N/dpr`**。N=2 時:dpr=1 → s=2;dpr=0.667 → s=3。**務必用實測 dpr 算,別套這兩個例子。**

## 7. 組 SVG（內嵌 2× PNG）
毛玻璃(模糊/glow)本質點陣、無法真向量化 → SVG = 邏輯 native 尺寸的容器內嵌 2× PNG(可縮放、副檔名 .svg)。PowerShell(**尺寸數字直接寫死進字串,別用變數** —— 實測 `'width="'+$W+'"'` 這種拼接會拿到空值、產出 `width="" viewBox="0 0  "` 的壞 SVG):
```powershell
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($png2x))
# 下例 native=1960×1280;改尺寸時直接改字串裡的數字,別引變數
$svg='<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1960" height="1280" viewBox="0 0 1960 1280"><image width="1960" height="1280" preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,'+$b64+'"/></svg>'
[IO.File]::WriteAllText("$diag\NN-topic.svg",$svg,(New-Object Text.UTF8Encoding($false)))
```
native(如 1960×1280)為邏輯尺寸;內嵌的是 2× png → 顯示時 2× 密度、清晰。**驗證**:① SVG 前 200 字 `width`/`viewBox` **非空**(踩過拼接成空值);② `[xml]` 解析不報錯 + base64 decode 回 PNG byte 數相符。**大 SVG(內嵌幾 MB PNG)別用 `browser_navigate` 開驗 —— 會 30s timeout**;靠上面兩步即可(PNG 已單獨 render + 四角驗過)。
> ⚠️ PowerShell `Remove-Item` 對含路徑的刪除可能被 sandbox 擋(整條命令含 Remove-Item 會被預掃 block,連 Copy/Write 一起沒跑)→ 刪 scratch 用 Bash `rm -f`,建檔命令裡別混 Remove-Item。

## 8. gitignore render 暫存
**自檢截圖 / 裁切 / 2× 暫存一律存進 `resources/snapshots/`**(2026-06-22 統一;舊版散落根目錄 `NN-*.png` + `_crops/` 已棄)。`.gitignore` 以 `resources/snapshots/*` 收、只追蹤 `README.md` 讓資料夾常駐;另收 MCP 自輸出 `.playwright-mcp/`。交付的 `NN-topic.{png,svg}` 在 `diagrams/` 內、明確列檔 commit,不受影響。
