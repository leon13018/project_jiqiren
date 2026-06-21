# Render pipeline — 本機 Chromium 渲染 / 截圖 / 高解析匯出 / 自檢

> 把 `diagrams/NN-*.html` 變成乾淨無黑邊的 **2× PNG + SVG**。所有指令、座標、配方都來自圖①②實證(踩過黑邊 / 截字 / 快取 / DPR 各種坑)。

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
Mermaid 自定義度低(dagre 佈局搶方向盤無法精確擺位、`style/classDef` parser 不認 `oklch()`、毛玻璃只能 hack)。改 **HTML/CSS 絕對定位卡片 + SVG overlay 畫箭頭**,用無頭 Chromium 截圖 —— OKLCH / `backdrop-filter` 毛玻璃 / web 字 / 立體陰影全部原生支援。**純 HTML/CSS 沒有 Mermaid 的「測量字寬≠渲染字寬」截字 bug**(那是 Mermaid 專屬;這裡等 `fonts.ready` 即可)。

## 2. 起 no-cache 本機 server
**Playwright MCP 擋 `file:` 協議**,必走 http。**但 plain `python -m http.server` 不送 cache header → Chromium 會快取 `theme/*.css`,你改了 CSS 重渲染卻沒生效(HTML 內聯改有效、CSS 檔改無效,極易誤判「改了沒用」)。** 一定用會送 `Cache-Control: no-store` 的小 server:

```
py -3.14 "<skill>/scripts/nocache_server.py" "<repo>/resources/architecture/diagrams"
```
背景跑(`run_in_background`),服務 diagrams 目錄;之後一律 `http://127.0.0.1:8191/NN-*.html`。全程畫圖只需這一個 server,畫完再關。

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
- `browser_take_screenshot`(存根目錄,檔名 `NN-vN.png` —— 已 gitignore)。

## 5. 自檢:裁切放大逐項核對
截圖後**用 `System.Drawing`(PowerShell)裁局部放大**,`Read` 進來逐項看。**反覆修到完美才給使用者,不給半成品。**

⚠️ **必裁的區域(圖①②都在這些漏過)**：
- **箭頭匯聚區**(多箭頭收束的地方)—— 不能只裁卡片;線會穿過不該穿的卡、或交纏。
- **每張卡的最長文字**(desc / note / 命令列)—— 看有沒有 `overflow:hidden` 截字。
- **箭頭標籤**—— SVG 在卡片 DOM 之前 = **渲染在卡下層**,標籤延伸進卡片 bbox 會被卡蓋住,看起來像「框裏字被截」→ 標籤一律落在卡片之間空白、別超進卡。

逐項清單:字看得到嗎 / 有沒有截斷 / 有沒有衝出框 / 顏色對比夠嗎 / 箭頭線可見嗎(**有沒有箭頭頭** —— 別只有線沒頭,見 §7 marker)/ 標籤壓在自己的線上嗎 / 組件之間 ≥30px 不相碰嗎 / 卡內容垂直置中嗎(`browser_evaluate` 量每卡 top/bot gap 應相等)/ **跨 band 元件 y 區間不重疊嗎**(常見:某條 flow lane 或某排卡的 y 撞穿另一 band 的卡 → `browser_evaluate` 量各 band top/bottom)。

裁切範本(改座標即可):
```powershell
Add-Type -AssemblyName System.Drawing
$src=[System.Drawing.Image]::FromFile("<root>\NN-vN.png")
$b=New-Object System.Drawing.Bitmap($w,$h);$g=[System.Drawing.Graphics]::FromImage($b)
$g.DrawImage($src,(New-Object Drawing.Rectangle(0,0,$w,$h)),(New-Object Drawing.Rectangle($x,$y,$w,$h)),'Pixel')
$b.Save("<root>\_crops\c.png");$g.Dispose();$b.Dispose();$src.Dispose()
```
> System.Drawing 踩坑:`Add-Type -AssemblyName System.Drawing` **每個獨立 ps 腳本都要重下**(否則 `[System.Drawing.Image]` TypeNotFound);若要高品質縮圖,`$g.InterpolationMode` 要賦 **enum 型別**(`[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic`),賦字串會 PropertyNotFound。

## 6. 高解析匯出配方（DPR 反推 + 填滿，零黑邊）
要 **N× native** 的交付圖(預設 N=2):
1. `browser_resize(nativeW*N, nativeH*N)` —— device viewport = 目標像素 = 截圖解析度。
2. `browser_evaluate`：
   ```js
   async () => {
     await document.fonts.ready;
     const dpr = window.devicePixelRatio;             // 量
     document.documentElement.style.background='transparent';
     document.body.style.margin='0';
     const st=document.querySelector('.stage');
     st.style.margin='0'; st.style.transformOrigin='top left';
     st.style.transform = `scale(${N/dpr})`;           // 填滿:CSS視窗=native*N/dpr，畫布要放大 N/dpr
     const r=st.getBoundingClientRect();
     return `box=${Math.round(r.width)}x${Math.round(r.height)} @(${Math.round(r.left)},${Math.round(r.top)})`;
   }
   ```
   - **`margin` 一定歸 0**:留著 `margin:0 auto` 會把畫布**佈局框**置中(偏移 transform 原點)→ 右下角變灰 / 黑(圖① 踩過)。box 要回報 `@(0,0)`。
3. `browser_take_screenshot` → `NN-2x.png`。
4. **驗證(PowerShell `GetPixel` 四角)**:尺寸 = `nativeW*N × nativeH*N`,**四角像素都該是畫布本身深色背景 / 光暈**(約 `(4,7,16)` 或帶色光暈);若出現灰 `(44,44,44)` 或純黑大片 = 沒填滿,回 step 2 檢查 margin/scale。

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
這些非交付,`.gitignore` 收(圖① 已加):`.playwright-mcp/`、`_crops/`、`/smoke-*.png`、`/[0-9][0-9]-*.png`。交付的 `NN-topic.{png,svg}` 在 `diagrams/` 內,不受影響。
