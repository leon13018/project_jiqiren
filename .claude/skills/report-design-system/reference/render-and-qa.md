# 渲染 / 截圖 / SVG 匯出 / 視覺自檢

> **🎯 何時讀本檔**：把 HTML 圖 / 報告 render 成 PNG / PDF / SVG、做像素級視覺自檢時。本檔是**自足蒸餾**（淺色蠟筆圖 + 報告 PDF 通用部分）——深色霓虹架構圖的完整管線在 `architecture-diagram` skill，本 skill 不依賴它。

## 1. 渲染配方（本機 Chromium，免 server）

`file://` + 相對依賴（`../rough.js` / `../fonts/jason8.ttf`）直接解析，**不需起 http server**。Chrome 在 `C:\Program Files\Google\Chrome\Application\chrome.exe`。

**系統圖出 PNG**（路徑空白用 `%20`；2× 加 `--force-device-scale-factor=2`）：
```bash
chrome --headless --disable-gpu --force-device-scale-factor=2 \
  --window-size=W,H --virtual-time-budget=15000 --hide-scrollbars \
  --user-data-dir=/tmp/cr-NN \
  "--screenshot=OUT.png" "file:///C:/…/NN.html"
```
- `--window-size` = `.stage` 尺寸（如 1960×1188）→ 滿版無黑邊。`--force-device-scale-factor=2` → 輸出 2× 像素。
- 🔴 **用舊 `--headless`**：`--headless=new` + `--screenshot` 本機不寫檔（踩過）。
- 蠟筆/Rough 濾鏡重 + Rough.js 在 `window load` 跑 → `--virtual-time-budget` 給足（**≥12000**）。
- 各 stage 尺寸：圖①1960×1188 / 圖②1960×1150 / 圖③1960×1320。

**報告出 PDF**（可走 `--headless=new`）：
```bash
chrome --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="report.pdf" "file:///C:/…/report.html"
```
尺寸由 `@page{size:11in 8.5in}` 決定；滿版色靠 `print-color-adjust:exact`；字型未就緒風險先 `await window.READY`（見 [report-pdf.md](report-pdf.md) §7）。

## 2. 視覺 critical gotchas（生圖必守，違反返工）

> 使用者逐輪像素級 QA、每修都 render-verify。下列是反覆抓過的包：

- **零卡片覆蓋**：任何元素都不准與任何卡片重疊，即使只壓一點點 / 文字沒互相干擾也不行（legend / note / band·group 標籤同樣不准被節點壓）。元件間 ≥30px 不相碰。
- **文字不溢框 · 字別貼邊**：卡 / group / pill / chip 文字一律收在框內留圓角 padding（card r≈18 / group r≈20 → 文字內縮 ≥ ~22px）；太長就縮短 / 斷行 / 拆元素,不硬撐一行頂出框。
- **卡內容垂直置中**：上下留白對稱（topGap = botGap），不偏靠上/下。
- **卡片大小取決於內容**：內容少做小卡塞合適空角,**絕不為佔位/對齊做空蕩大卡**（右/下大片空白 >~25% 非刻意對齊 → 縮卡）。「畫大」只指畫布、非單卡可攤大。
- **無大片死空白**：上方有明顯空白就往上挪填滿,整體垂直分布均衡緊湊。
- **箭頭走線整齊流暢**：正交對齊同一 lane、轉折一致圓角、平行線等距、最少化彎折/交叉/斜穿；收束點對齊。必要時連走法都改,反覆截圖到舒服。
- **箭頭線 ↔ 文字零交疊**：SVG 線 / 箭頭頭絕不穿過任何文字（卡內文字、eyebrow、邊標籤、group-label）;邊標籤落線中段清空處且自帶深色 halo。
- 🔴🔴 **線↔三角箭頭頭同色**：改箭頭線色必連 marker 三角頭一起改、兩者同色（使用者 ≥3 次抓包）。
  - **坑**：marker `<path>` 會被 `.edges path { stroke:var(--arrow) }` 劫持 → 三角形變淡色描邊。光在 HTML marker 寫 `fill=` 沒用（specificity 低被蓋）。
  - **正解**：用 ID 提 specificity —— `.edges marker path{stroke:none} / .edges marker#ah path{fill:var(--arrow)} / .edges marker#ah-hawk path{fill:var(--arrow-hawk)}`。新圖 marker 沿用 `id=ah`(墨) / `id=ah-hawk`(珊瑚) 即自動同色。
  - **驗**：不可只看 `getComputedStyle(markerPath).fill`（marker context 回誤值）→ render 後 GetPixel 取「線中段」+「箭頭頭三角實體」兩點比色。

## 3. 自檢：先全圖、再局部

1. **先 `Read` 整張全圖**（可 downscale ~900px 寬）掃全局：黑邊 / 大片空白 / band 互撞 / 整體失衡。**絕不只截一小區就算自檢**。
2. **再 PowerShell `System.Drawing` 裁局部放大** `Read` 細看：箭頭匯聚區、每卡最長文字（有沒有 `overflow:hidden` 截字）、箭頭頭、標籤壓線。**每條線兩端連接點逐一裁**確認真觸目標 / 實接來源 / 無浮空線頭。

裁切範本（每個獨立 ps 腳本都要重下 `Add-Type`）：
```powershell
Add-Type -AssemblyName System.Drawing
$src=[System.Drawing.Image]::FromFile("IN.png")
$b=New-Object System.Drawing.Bitmap($w,$h);$g=[System.Drawing.Graphics]::FromImage($b)
$g.DrawImage($src,(New-Object Drawing.Rectangle(0,0,$w,$h)),(New-Object Drawing.Rectangle($x,$y,$w,$h)),'Pixel')
$b.Save("CROP.png");$g.Dispose();$b.Dispose();$src.Dispose()
```
GetPixel 取樣關鍵點色值（確認接點 / 底色 / 線↔箭頭頭同色）：
```powershell
Add-Type -AssemblyName System.Drawing
$bmp=New-Object System.Drawing.Bitmap("IN.png"); $p=$bmp.GetPixel($x,$y)
"{0},{1},{2}" -f $p.R,$p.G,$p.B; $bmp.Dispose()
```

## 4. SVG 匯出（容器內嵌 2× PNG）

毛玻璃 / 蠟筆濾鏡本質點陣、無法真向量化 → `.svg` = 邏輯 native 尺寸容器內嵌 2× PNG（可縮放、副檔名 .svg，比照三式同名交付慣例）。PowerShell（**尺寸數字直接寫死進字串,別引變數** —— 拼接會拿到空值）：
```powershell
$b64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($png2x))
# 下例 native=1960×1188；改尺寸時直接改字串裡的數字
$svg='<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1960" height="1188" viewBox="0 0 1960 1188"><image width="1960" height="1188" preserveAspectRatio="xMidYMid meet" xlink:href="data:image/png;base64,'+$b64+'"/></svg>'
[IO.File]::WriteAllText("NN.svg",$svg,(New-Object Text.UTF8Encoding($false)))
```
**驗**：① SVG 前 200 字 `width`/`viewBox` 非空；② `[xml]` 解析不報錯。大 SVG（內嵌幾 MB PNG）別用瀏覽器開驗（會 timeout），靠這兩步即可。

> ⚠️ PowerShell `Remove-Item` 含路徑刪除可能被 sandbox 預掃 block（連同批 Copy/Write 一起沒跑）→ 刪 scratch 用 Bash `rm -f`，建檔命令裡別混 Remove-Item。
