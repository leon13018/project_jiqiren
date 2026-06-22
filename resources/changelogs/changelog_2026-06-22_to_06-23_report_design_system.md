# 報告設計系統 + 雙生 skill 重構弧（2026-06-22 ~ 06-23）

> 不改產品碼。承接上一弧（深色霓虹圖工具化 `architecture-diagram`），本弧把報告視覺**改宗 Anthropic 淺色編輯 + 手繪蠟筆風**，並把製作工具重構成「**風格權威 + production 產線**」雙生 skill。全程走 worktree；commit/push/codemap-health 全綠。
> commits：`c06eb1f`（report-design-system 誕生）→ `eaf4273`（architecture-diagram 改宗）→ `626b2a5`（QA 迴圈硬化）→ `28b98c4`（蠟筆 render caveat）→ `e795664`（diagrams 重組）→ `4ad3649`（共用 deps 預放）。

## 1. `report-design-system` skill 誕生（`c06eb1f`）

把 `resources/report/design-system.md`（Anthropic 淺色編輯風：報告 PDF §0–8,10 + 系統圖手繪蠟筆 §9）做成**完全自足、可打包帶走**的 skill：
- spec 搬進 `reference/{report-pdf.md, diagram-crayon.md}`，**原 `design-system.md` 改薄 pointer**（單一事實來源移入 skill）。
- `reference/render-and-qa.md`：蒸餾 render / 截圖 / SVG 匯出 / 視覺 critical gotchas（自足、不依賴 architecture-diagram）。
- vendored `assets/rough.js`（Rough.js hachure 填色）+ `assets/fonts/jason8.ttf`（清松手寫⑧塗鴉標題字）。
- `assets/benchmarks/`：圖①②③ 三張**定版對照基準**（HTML+PNG+SVG，淺色蠟筆 gold standard；HTML 引用 skill 內 `../rough.js`/`../fonts/jason8.ttf`、可就地 render；PNG=1× 給 `Read` 看、SVG=內嵌 2×PNG 供報告引用）。
- 唯一外部依賴＝ web font 走 Google Fonts CDN（render 需網路；可離線化但本 session 定 CDN）。
- skill-creator 流程：使用者選 **author-only**（視覺主觀 skill、不跑量化 eval）；PNG/SVG 格式經兩輪確認。

## 2. `architecture-diagram` 改宗淺色（`eaf4273`）

- **刪深色霓虹預設主題**，視覺風格**完全指向 `report-design-system`**；保留嚴謹流程（讀實際碼鐵則 / SDD / opus 實作 / 3-QA-panel）。
- `reference/visual-system.md` 挖空成 pointer；`assets/skeleton.html` 改**淺色自足起手式**（內聯 tokens + 3 蠟筆濾鏡 + Rough.js loader、平放依賴引用）；`render-pipeline.md` 保留 render 機制、風格/gotchas 指向 report-design-system。
- **雙生 skill 分工**（雙向 cross-ref）：`report-design-system` = 風格權威（+ 報告 PDF + 三基準）；`architecture-diagram` = 從頭畫圖的嚴謹 production（單向吃前者風格、不反向依賴）。深色 `theme/` + 深色圖 ①–⑤ 標 legacy。

## 3. QA 迴圈硬化（處理 pending 反思的真 bug，`626b2a5` + `28b98c4`）

反思揪出 architecture-diagram 的 QA 迴圈指令**其實跑不起來**，全修：
- 具名 implementer `impl-NN` + 缺陷用 `SendMessage(to: impl-NN)` 回送（不再 `Agent()` 開新 subagent 丟 context）。
- **render 全歸 orchestrator 序列獨占**（新增 step 5.5），implementer 只寫 HTML 不 render（解多圖並行撞單一共享瀏覽器）。
- QA 只讀靜態檔、不 render/不 GetPixel；**QA-B 比 dump `arrowSamples[]` 像素**（解「GetPixel ⊥ no-render」矛盾）；`render-pipeline.md §5.5` 加 dump schema 欄位 + §5.5b orchestrator render 後補像素取樣。
- QA loop **N=3 收斂上限**；**QA-C 讀對應 `.py` 稽核**（非只 spec、防 spec 本身已錯）；**step8 從 snapshots 搬已驗 PNG、禁重 render**；backlog/code_map 索引只在三式 commit 後改。
- 蠟筆 render caveat（`28b98c4`）：`file://` 自足只對 rough.js/jason8.ttf 成立、**web font 仍需網路**（離線 fallback）；`#crayon` 用 userSpaceOnUse、region 綁 `.stage` 尺寸 → 放大畫布要同步加大。

## 4. 反思全處理 + 歸檔（gitignored ledger）

- 20 條 pending（含 session 中反思機制新 append 的 2 條）→ **17 採納 + 3 否決**；連同上批 14 條已 adopted+落實 = **34 條歸檔** `reflections/archive/proposals_archived_2026-06-23.md`，`proposals.md` 收乾淨。轉 eval 一律否（皆 skill 指令/協議文字修正，非 navigator transcript 可客觀判定）。

## 5. `resources/architecture/diagrams/` 重組（`e795664` + `4ad3649`）

為「之後淺色圖生成不跟深色混亂」整理：
- **深色歸檔 `_legacy-dark/`**：深色 `theme/` + 深色圖 ①–⑤ 三式（保留為淺色重畫的來源素材，尤其無淺色版的 ④⑤；相對 theme link 完整）。
- **淺色交付主層**：①②③ png+svg（從基準複製；**html 源留基準**、零依賴/字型重複）。
- **共用 render 依賴預放**：`diagrams/rough.js` + `diagrams/jason8.ttf`（同層平放）→ 未來 ⑥–⑪ 淺色 html 落主層直接同層引用、不必再複製。
- `specs/00-diagram-backlog` + `01` spec 去過時（改宗淺色 pivot）；resources code_map + skill 路徑（theme→`_legacy-dark/theme/`）同步。
- `_archive/` 舊願景保留（使用者選）；5 個架構 .md（README/00/10/20/30）未動（本就整齊）。

## 6. 圖④⑤ 淺色蠟筆換膚 + 使用者視覺精修（2026-06-23）

承「下一步」，把 ④⑤ 從 `_legacy-dark/` **換膚**成淺色蠟筆（產線 B：copy 深色 → 外科改 `<head>` 內聯淺色 tokens + `<defs>` 注入 3 蠟筆濾鏡 + 兩處 inline OKLCH 換淺 + 補 rough.js loader，**body 座標逐字保留＝零漂移**）：
- **6-opus QA panel**（每圖 3 lens：版面 / 箭頭 / 風格+內容稽核）只讀靜態 PNG + 回讀 `.py`：**0 內容事實錯誤**（`_PHASE_BY_STATE` / checkout_confirm ★ 直發 `l2_l3_dialog.py:734` / 6 token 映射 / 冰紅茶 27 元九折 / l4 36s·12s / arecord -c6 ch0 / host 0.0.0.0:8137 三路由 / `_run_wiring` 防呆 / Pi 純 uvicorn 依賴 ── 全對碼命中）、風格 8/8、箭頭方向正確。few flags 皆 orchestrator 裁切複核為 over-flag 或 preserved-from-dark。
- **使用者多輪像素級視覺精修**（orchestrator 自跑 render→裁切迴圈、每修即交，非全外包 QA 文字裁決）：
  - **④**：5 個 phase 帶加 Rough 蠟筆 hachure 填（細密淡透，定 gap 4 / opacity 0.12 / 提亮色 / z-index 0）；6 條時序線從實線→**蠟筆外框膠囊**（`<rect>` 圓角 + `#crayon` 濾鏡：飽和深色外框 stroke + 淡填底 fill）、壓到**最底層 z-index -1**（不蓋任何東西）、原向下淡出漸層改實色**完整延伸到底 y2482**。
  - **⑤**：Pi 4 裝置框 + frame-label 加蠟筆 hachure 填；frame-label 移除外框、下移 ~5px 在框頂↔卡片間上下置中。
- 交付三式 `04/05-*.{html,png,svg}` 進 `diagrams/` 主層（**html 源在此**，∵ ④⑤ 無對照基準）、四角驗無黑邊、SVG 內嵌 2×。

> ⚠️ **本 session 偵測到並行 actor**：另一 session 同時做 Wave C（⑥⑦ html+spec 已草、未交付/未 commit）+ 改 4 個 skill 檔（architecture-diagram `SKILL.md`/`skeleton.html`/`render-pipeline.md`、report-design-system `render-and-qa.md`）+ `code_map.md`。**全程未碰其改動**；本批 commit 只明列 ④⑤ 六檔 + 乾淨 doc（backlog/changelog/roadmap/spec），`code_map.md` 的 ④⑤ 狀態更新留工作區**不 commit**（避免綁進並行 actor 的改動，留它收尾）。

## 7. 圖⑥⑦ STT/TTS 管線交付（Wave C，2026-06-23）+ 視覺 QA 教訓 + skill 硬化（`196f7be`）

承 §6「⑥⑦ 並行 session 進行中」——本 session 即該 actor，現 ⑥⑦ 交付定版。
- **產線**：讀 `stt.py`/`tts.py`/`tts_prewarm.py`/`queue_worker.py` 逐項核對 → 寫 spec → 平行 2 opus implementer 各寫 HTML（不 render）→ orchestrator 序列獨占 render + §5.5 bbox dump → 平行 6 opus QA panel（每圖 3 lens、讀靜態 PNG+dump、QA-C 回讀 `.py` 稽核）。
- **QA round-1**：兩張內容真實性 + 箭頭皆 PASS（無捏造、1-deep 沒誤畫成多深、8 邊逐端裁），各一版面 FAIL（死空白分布）→ 迭代（⑥ 改 **3-band 縱向蛇行**＋Deepgram 寬橫帶滿寬；⑦ 右欄 mpg123 上提加大 + 鏈攤到底）→ **正式 QA panel 複核全 3/3 PASS**。
- 🔴 **核心教訓**：QA panel 文字裁決可「線↔頭同色 / overlaps=[] / 內容無捏造」全 PASS，**卻漏掉「整體看起來亂」**（三扇入線糾纏、長線怪繞、attribute 偏左、文字溢框）——使用者一眼抓到。**視覺收斂不可外包給 QA 文字裁決；orchestrator 必親自跑 render→截圖→改 迴圈到肉眼乾淨，使用者眼睛是最終裁判**（已寫進 memory `diagram-qa-cadence`）。
- **使用者逐輪像素級精修定版**：⑦ 箭頭**全部重拉** + 長標籤拆兩行（q.get/取一句、1-deep prefetch/播放時預取下一句、預先 seed/灌快取）+ 三扇入→單一 `mp3_path`（語意：三層 fallback 都解析成一個 cache 檔）+ seed 從 prewarm 左緣中心→HERO（使用者建議）+ FIFO→① 連接修（原浮空在 frame 邊）+ prewarm/FIFO 文字溢框修（加高貼內容置中）；⑥ ch0 HERO / normalize / input-queue 移到左右鄰**置中** + ws.recv 對齊 SttReceiver 頂中心（與 ws.send 同線）+ prearm 改短連 SttReceiver（原 400px 長虛線穿 speech_final）。
- **skill 硬化**（治本「死空白每次中」＋ DPR 陷阱）：① bbox dump 加 `fill`（內容垂直 extent + `bottomDeadRatio`）+ `occupancy`（6×5 占用網格、**排除容器 frame** 露 frame 內空洞）+ **ink-ratio 抽查**（<~5% 視同空，補 binary occupancy 盲點）；`render-and-qa` 把「畫大」澄清成**只指寬度、height 貼內容**、死空白改可量 FAIL 閘；`skeleton.html` 註解修；`SKILL.md` QA-A 判準。② **DPR 陷阱**：Playwright `scale:'css'` 截圖內容隨 session DPR 浮動（1.0/0.8/0.5）→ native×dpr 座標錯位、裁圖一直裁錯 → 視覺迭代改 `chrome --headless --force-device-scale-factor=2`（確定性 2×、免 server、crops 用 native×2）。（skill 檔在 `.claude/skills/`、本地生效不入 git。）
- 交付三式 `06/07-*.{html,png,svg}` 進 `diagrams/` 主層（html 源在此）、四角驗無黑邊、SVG 內嵌 2×。本 session 一併收 §6 遺留的 `code_map.md` ④⑤ 狀態進 commit（並行 actor 已 idle/shutdown）。

## 狀態 / 下一步

- 雙生 skill 定版 + 死空白量測 / ink-ratio / 確定性 chrome render 硬化；report-design-system 弧 commits 全 push。
- **圖**：淺色 **①–⑦ 已交付**（`diagrams/` html/png/svg）；**⑧⑨ 另一並行 session 進行中**（模組依賴 / 類別，html+spec 已草、未交付）；⑩⑪ 待畫（淺色）。
- **下一步＝⑧–⑪ 淺色 → 報告 PDF（`report.html`/`tokens.css` 待建）/ PPT。**
