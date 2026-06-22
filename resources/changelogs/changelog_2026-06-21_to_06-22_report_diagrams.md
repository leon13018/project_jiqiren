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

## 7. Wave A ①②③ 實際重畫交付 + skill 大幅硬化（2026-06-22）
- **①②③ 全交付**（三式同名 html/png/svg，opus subagent 照 SDD + 鐵則 1 讀實際碼核對畫成；版面隨使用者 mockup 反覆微調定版）：
  - ① Process/Thread：左脊 MAIN→TTS/Action queue+EventBus→TtsWorker/ActionWorker/webui-server→灰 chip；右欄 STT session(右上)→input queue(金 hero 右中)→InputReader(右下)；**3 producer→1 input queue 金扇入主角**；下方緊湊（bootstrap+note 上移）。
  - ② L0–L5 狀態機：4 運行層 L1→dialog→L4→L5（cart 驅動）+ **enter_hawk 金回流主角** + confirm 閘 cluster（cancel6s/service24s/checkout12s/C-2 6s/qty12s）+ L0 共通 NLU 基座；底排 enter_hawk 圖例(左)/L0 內容小卡(右)。
  - ③ web phase：emit 源(左)/5 phase 縱列(中，**checkout_confirm 縮排=dialog 內子 phase**)/上行回路 6 觸控命令→to_token→inject(右)/**phase 驅動金弧閉環主角**；白 emit 走平行 bus、machine._emit 帶白上分開/金下。
- **skill 視覺 critical gotchas 增至 9 條**（使用者實時驗收逐項抓包 → 固化）：圓角留白·字別貼邊 / 卡內垂直置中 / 零卡片覆蓋(legend·note 也算) / 文字不溢出 / 不做空蕩大卡 / 箭頭線↔文字零交疊 / 箭頭線↔頭同色 / 無大片死空白 / **箭頭走線整齊流暢（+ 兩端連接點逐一裁切自檢）**。
- **theme 修**：① marker `<path>` 被 `.edges path{fill:none;stroke}` 劫持 → 箭頭頭變空心淡藍（≥3 次跨 session 抓）→ `.edges marker#id path` ID-specificity 蓋掉、durable（全圖自動實心同色）；② 色彩 token 化 `--arrow-hawk`(線+頭) + `--arrow-hawk-label`(標籤)、金弧柔化（L 85→79、α .96→.75、width 3.8→3.0）；③ `.group-label` 清開圓角彎角（top:14/left:22）。
- **render-pipeline 修**：① 背景填 `--bg-base`（非 transparent）解 dpr 浮點邊角 1px 灰；② 箭頭頭色用 **GetPixel 取線中段+頭實體比**、別信 marker `getComputedStyle().fill`（回 none/未解析 var 誤判）；③ navigate 帶 cache-buster（server 快取會給舊版誤判）。
- **平行派工規則固化**（SKILL「⚡ 平行加速」，使用者指定）：**獨立的圖一次平行派 ≥2 opus subagent 各自 render**（各自瀏覽器 instance）；唯 orchestrator 別跟某圖 subagent 搶同檔/同瀏覽器。
- 反思 ~30 條逐條 `status: adopted`（多為同議題重報 + 數新 nuance：GetPixel 驗色 / 色 token / 連接點自檢 / 平行衝突）。

## 8. Wave B ④⑤ 交付 + 自檢協議升級（2026-06-22）
- **④ 端到端時序圖**：6 泳道（前端/WS/主線程/STT/TTS/Action）+ 5 phase 帶 + 21 發訊息序列；主角＝下行 `display(phase)` 金 emit（phase-driven）；**checkout_confirm★ 標為 dialog 內子 phase**（非 machine 平行 phase）。
- **⑤ 部署/網路拓樸**：雲（Deepgram WSS / edge-tts HTTPS）/ Pi server `0.0.0.0:8137` / 本地硬體（ReSpeaker USB·喇叭 ALSA·TonyPi serial）/ 渲染端 client 四區；主角＝**render-offload 金鏈**（Pi serves, client renders — Pi 自身瀏覽器 GPU+Chromium<111 無 OKLCH 跑不動前端）。
- **① 連帶重出**：因動了共用 theme `.frame-label`。
- **自檢協議升級（使用者指定）**：自檢從「implementer 自己反覆截圖」改成「**每張圖平行派 3 個 opus QA subagent**」——lens A 版面/空間、B 箭頭/連線、C 文字/內容真實性（鐵則 1 內容稽核）；QA **只讀靜態產出物（PNG + bbox dump）、不開瀏覽器**→ 影像 token 不進主對話、可大量平行。實證價值：QA panel 抓到 implementer 自報漏掉的 race 污染（04 PNG 內容變 FIG.05）+ band 標籤 overlap 盲點。
- **render 必序列化（修正 Wave A 誤判）**：Playwright MCP 是**單一共享瀏覽器**（非每 subagent 一個）→ 兩 subagent 同時 render 會互相把頁面導走、截到對方的圖。**HTML 撰寫可平行、render 必一次一張獨占**（orchestrator 居中發 GO）。Wave A changelog §6 的「各自瀏覽器 instance」說法**作廢**。
- **`render-pipeline §5.5` canonical bbox dump**：絕對路徑寫死（修「dump 誤落 root 觸發 code_map hook」反覆踩坑）、selector 含 `.node/.screen` + band/group/frame 標籤、內建 `overlaps`（含標籤 vs 節點，排除 band/frame/lane/lifeline/group 容器自身）+ `textOverflow`（scrollWidth>clientWidth）自檢。
- **theme `.frame-label` 改浮框內側**（`transform: translate(22,7)` 小 pill）：原「掛框頂虛線的 tab」會蓋掉頂邊虛線、虛線框不完整（使用者抓）→ 改浮內側使虛線圓角矩形完整；①⑤ 共用、連帶重出。
- **CSS 快取坑**：no-cache server 送 `no-store` 仍救不了「**瀏覽器層**已快取同 origin 舊 CSS」→ theme 改了 render 仍出舊值；**正解＝換沒用過的新埠 origin** 強制重抓（耗多輪才查出）。
- **使用者多輪逐項視覺 QA 抓包修正**：band 標籤被首節點壓（b1/b2/b5 clearance≥60）/ 文字溢框（⑧ `read_customer_input()` timeout 移 desc、⑲ `_emit("l5")·paid=27`）/ do_action 派工線斜鉤→垂直插底緣 / 旁註浮空→補虛線連 ⑨「替代輸入」/ ⑤ frame-label·死空白·硬體卡間距 34px / **圖身整體下移 + legend·note 移頂排**（`.shift` 容器 translateY 180 一次下移、免改 60+ 座標）/ **phase 標籤左緣對齊下方卡片**（`.pband left 72→66`）。
- **踩坑**：① concurrent-edit（orchestrator 接手編 04 + subagent 未停同編 → HTML 混入兩標籤/兩 path，已清；教訓＝接手前先確認 subagent 完全停，skill 早有此規）；② named/mailbox subagent 不穩（多次 idle 不執行指派任務 / 重複多餘 render）→ **小修改由 orchestrator 自編 HTML + 自己 render-verify 更可靠**（瀏覽器空閒、無編檔衝突時）。
- commit 鏈（main）：`692c7b7` Wave B ④⑤ 交付 → `dff0a7b` ④ 旁註虛線 → `4340566` ④ HTML 去重 → `c00e1de` ④ 圖身下移+legend/note頂排 → `b2f6c51` ④ phase 標籤對齊。

## 關鍵踩坑（都已固化進 skill）
DPR 非固定要每次量｜`body` flex-center 視窗矮會裁頂不可捲（改 block + `margin:auto`）｜縮放 + 視窗截圖對不齊產黑邊（改「device viewport 反推 + 畫布 scale 填滿 + margin:0」、四角驗）｜SVG marker 箭頭頭 theme 沒給｜PowerShell 字串拼變數成空｜自檢只裁局部會漏｜**render 單一共享瀏覽器必序列化（平行只能 HTML 撰寫 + QA 讀靜態檔）**｜**CSS 改了瀏覽器層快取舊值 → 換新埠 origin**｜**bbox dump 寫絕對路徑（誤落 root 觸發 hook）**。

## 狀態
**Wave A ①②③ + Wave B ④⑤ 全交付 ✅**（2026-06-22，三式同名 html/png/svg；① 因 theme frame-label 改動重出）。skill 經兩波實戰大幅硬化（9 視覺 gotcha + 3-opus QA panel 自檢協議 + render 序列化鐵則 + §5.5 canonical bbox dump + theme/render-pipeline 多修 + CSS 快取坑）。**下一步＝新 session 載 architecture-diagram skill、照 backlog 接 Wave C（⑥ STT 管線、⑦ TTS 管線）→ D（⑧⑨）→ E（⑩⑪）**；HTML 撰寫可平行、render 一次一張獨占、自檢派 3-opus QA panel。
