# 對照基準 — 淺色蠟筆風 gold standard

`report-design-system` skill 的定版視覺基準：三張系統圖從深色霓虹版**換膚**成 Anthropic 淺色編輯＋手繪蠟筆風的成品。做新圖 / 改報告視覺前，拿這三張當「對的長相」核對。

## 三種格式各自的角色

| 檔 | 是什麼 | 怎麼用 |
|---|---|---|
| `*.html` | 換膚成品原始碼（self-contained 單檔，淺色 tokens / 蠟筆濾鏡 / Rough.js 全內聯；依賴引用 skill 內 `../rough.js` + `../fonts/jason8.ttf`，可就地 render） | **Read 它**學精確結構：色票怎麼內聯、`#crayon`/`#crayonEdge`/`#crayonText` 濾鏡參數、Rough.js hachure 填色腳本、卡 `::before` 蠟筆框、珊瑚 hero。要照抄某 pattern 看這裡。 |
| `*.png` | 1× native 截圖（1960×H） | **Read 它「看」風格**——字級層次、珊瑚 hero、蠟筆顆粒、Rough 斜線填色該長什麼樣。`Read` 工具會把 PNG 視覺化呈現，**比對風格一律用這個**。 |
| `*.svg` | SVG 容器內嵌 2× PNG（比照三式同名交付慣例） | 報告 / 投影片**引用**用（可縮放容器、2× 密度）。⚠️ 內含 base64 PNG，`Read` 會當純文字、**看不到圖**——要看長相請讀 `.png`。 |

> 為何 PNG 才是「給 Claude 看」的基準：`Read` 只把 PNG/JPG 視覺化；`.svg`（內嵌 base64）會被讀成文字。SVG 純為報告引用的格式一致性而存在。

## 三張各示範什麼

- **`01-process-thread`**（圖① Process/Thread 並行模型，stage 1960×1188）
  示範：**珊瑚 hero 環**（input queue 3-producer 扇入焦點）、`.group` 子框（STT session）、`.chip` 砂色掛件、6 色語意 legend、`note`「所以呢」三鐵則、**無 process 外框**。
- **`02-sales-state-machine`**（圖② L0–L5 銷售對話狀態機，stage 1960×1150）
  示範：**`.hawk` 回流弧**（enter_hawk 3 條 nested 珊瑚弧繞回 L1）、`.gate` cluster 子框（5 confirm 閘）、自迴圈小 loop、`.async` 虛線連接、底部 enter_hawk 圖例（①②③）。
- **`03-web-phase-state-machine`**（圖③ Web phase 交互狀態機，stage 1960×1320）
  示範：**5 phase 縱列階梯**、右欄上行回路（6 觸控 `.cmd` chip → to_token → inject 珊瑚 hero）、`.misalign` 虛框標註、`.subphase-tag`、**phase 驅動閉環**（粗珊瑚 `.hawk` 三段串一圈）。

## 共用 signature（三張一致，新圖照守）

FIG.NN 珊瑚牌（手寫字 + `#crayonText`）· eyebrow 等寬大寫分類標 + 短色條 · 6 色語意（章節色 fill/edge/tone）· `note`「所以呢 · 三鐵則」· 蠟筆 `::before` 框 + Rough hachure 填色 · **珊瑚只給主角 hero**、其餘節點章節色分類 · ivory 底 + 40px 格線 · **無純白卡**。

## 重渲染配方（依賴全在 skill 內、就地可跑）

HTML 相對引用 skill 內 vendored 依賴：`<script src="../rough.js">`（Rough.js hachure 填色）、`@font-face url('../fonts/jason8.ttf')`（清松手寫⑧標題字）。兩者已隨 skill 自帶於 `assets/rough.js` / `assets/fonts/jason8.ttf`，**從本目錄直接 render 即解析**（web font 走 Google Fonts CDN，render 時需網路）。

```bash
# 1× PNG（本目錄 .png 即此產出；2× 加 --force-device-scale-factor=2 供 .svg 內嵌）
chrome --headless --disable-gpu --window-size=1960,1188 --virtual-time-budget=15000 \
  "--screenshot=01-process-thread.png" "file:///…/assets/benchmarks/01-process-thread.html"
```

⚠️ 用舊 `--headless`（`--headless=new` + `--screenshot` 本機不寫檔）；濾鏡重，`--virtual-time-budget` 給足（≥12000）。SVG 組法見 `../../reference/render-and-qa.md §4`。stage 尺寸：01=1960×1188 / 02=1960×1150 / 03=1960×1320。
