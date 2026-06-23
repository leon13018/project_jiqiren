# 期末報告內容設計（content-design）

> **本檔＝報告「內容」單一事實來源**（章節結構 / 敘事 / 配圖對映 / 素材來源）。
> **視覺**權威在 `report-design-system` skill（Anthropic 淺色編輯風、排版 / 色票 / 元件 / PDF 配方）；本檔不重述視覺，只定「報告講什麼、怎麼編排」。
> 技術內容**指向** `resources/architecture/00–30` 四份文件（code-grounded SSOT），本檔不複製其細節，只做「章節 ↔ 素材 ↔ 配圖」對映。
> 建立：2026-06-23。狀態：設計定案，待寫 `report.html`。

---

## 1. 定位與約束

| 項目 | 決定 |
|---|---|
| 敘事骨架 | **方案 A 經典學術框架** + 各技術章內嵌「設計取捨」小節（問題→解法敘事）|
| 主軸 | **體驗 + 工程並重**（前段建立 demo 直覺、後段挖工程深度）|
| 篇幅 | **~15–20 橫式頁**（`@page{size:11in 8.5in}`）|
| 語言 | 繁體中文（產出物鐵則）|
| 視覺 | Anthropic 淺色編輯風，產線 A，做法見 `report-design-system` skill `reference/report-pdf.md`|
| 配圖 | **9 張系統圖 ①–⑨ 全用上**（`resources/architecture/diagrams/NN-*.png` / `.svg`）|
| 程式碼 | **精選 2–4 段短碼**（每段 <15 行），用 report-design-system 程式碼塊元件 |
| 真機素材 | demo 照片 / webui 截圖**由使用者提供**（版面預留佔位框）|
| 取材 | `architecture/00–30` + `changelog*` + 實際 `myProgram/` 碼；**不編造**主程式不存在的狀態 / 欄位 / 計時 |
| 截止 | 還有門時間 → **逐章製作、逐章驗收**，不趕稿 |

**不在本設計範圍**：PPT 簡報（`resources/presentation/`，之後另案）；報告視覺製作流程本身（→ `report-design-system` skill）；新畫系統圖（畫圖階段已收官 ⑨ 止）。

---

## 2. 9 張系統圖一覽（配圖素材）

| 圖 | 檔名（`architecture/diagrams/`）| 內容 | 落章 |
|---|---|---|---|
| ① | `01-process-thread` | 進程 / 三 worker 並行模型 | 第 4 章 |
| ② | `02-sales-state-machine` | L0–L5 銷售對話狀態機 | 第 5 章 |
| ③ | `03-web-phase-state-machine` | 後端 phase → 前端畫面 | 第 7 章 |
| ④ | `04-end-to-end-sequence` | 一輪互動端到端時序 | 第 2 章 |
| ⑤ | `05-deployment-topology` | 部署拓樸（Pi / 筆電 / ReSpeaker / 雲）| 第 3 章 |
| ⑥ | `06-stt-pipeline` | STT 管線（Deepgram / ch0 / arm-disarm）| 第 6 章 |
| ⑦ | `07-tts-pipeline` | TTS 管線（edge-tts / 內容定址快取）| 第 6 章 |
| ⑧ | `08-module-dependency` | 模組依賴 = Hexagonal 注入邊界 | 第 3 章 |
| ⑨ | `09-class-diagram` | 類別圖 State pattern UML | 第 5 章 |

---

## 3. 章節骨架（含頁數預算 / 配圖 / 素材來源 / 取捨小節）

> 各章頁數為**目標上界**；前置（封面 / 目錄 / 摘要）可併壓至 ~1.5 頁，逐章驗收時向 **15–20 頁總量**收斂（必要時第 3 / 6 / 8 章各壓 0.5 頁）。
> 「素材」欄＝該章主要取材的架構文件；技術細節以該文件為準，本表不複製。

### 前置（~2 頁）
- **封面**：報告標題 + **自家專題標記**（⛔ 不用 Anthropic 星芒商標）+ 課程 / 姓名學號 / 日期。
- **目錄**：章節 + 頁碼。
- **摘要**：~200 字 —— 一句話定義系統 + 規則匹配(非 LLM) + L1–L5 + 雙模態 + 成果（711 測試 / Pi 實機驗收）。
- 配一張章節塗鴉（report-design-system §6）。

### 第 1 章 · 緒論：動機與目標（1–1.5 頁）
- **內容**：擺攤銷售情境 → 互動式銷售輔助機器人（Hiwonder TonyPi 站攤）；規則匹配、兩商品（冰紅茶 / 刮刮樂）、L1–L5 範圍界定；成果速覽。
- **素材**：`00-system-overview §1`。
- **配圖**：無（純文字 + 小塗鴉）。

### 第 2 章 · 系統概觀：一杯飲料的旅程（2 頁）
- **內容**（B 手法故事化）：以「觸控 / 語音點一瓶冰紅茶 → 結帳 → 致謝」一輪互動串起全局，先建立讀者直覺再進技術。喚醒→點餐→結帳→致謝五步資料流。
- **素材**：`00-system-overview §5`（端到端資料流）。
- **配圖**：**④ 端到端時序圖**。
- **真機素材**：demo 照片佔位（攤位 + 機器人 + 平板畫面）。

### 第 3 章 · 系統架構與部署（2–2.5 頁）
- **內容**：整體形狀（單 process、業務邏輯嚴格不碰硬體、callback 注入）；硬體拓樸（Pi 4 / ReSpeaker / TonyPi SDK / client 筆電渲染）；六層模組地圖概覽。
- **素材**：`00 §3–4`、`30 §8`（Pi 渲染限制）。
- **配圖**：**⑤ 部署拓樸** + **⑧ 模組依賴（Hexagonal 注入邊界）**。
- **設計取捨**：為何 callback 注入 = sales/ 可在 Windows 跑 pytest；為何 Pi 只當 server、畫面由筆電渲染（OKLCH / GPU / Chromium<111）。

### 第 4 章 · 執行期與並行模型（2 頁）
- **內容**：主線程單線程狀態機 + 四 worker（TtsWorker / ActionWorker / InputReader / SttWorker）+ queue / EventBus 解耦；QueueWorker 消費者骨架；lazy import seam。
- **素材**：`10-runtime-and-workers §1–4`。
- **配圖**：**① 進程 / thread 並行圖**。
- **設計取捨**：全 daemon + `os._exit(0)` 強退；單 queue 單消費者（避免旗號分流 race）。
- **程式碼候選**：`QueueWorker._loop` 骨架（`SalesMachine.run` 留給第 5 章，見 §4）。

### 第 5 章 · 核心對話引擎：L0–L5 狀態機 ★（3 頁，最重）
- **內容**：cart 唯一驅動狀態（L2/L3 由 cart 空 / 非空即時推導）；L1 → dialog → L4 → L5 轉移；跨層流程（cancel 6s / service 24s / checkout confirm / C-2 自動結帳 / qty followup）；State pattern 調度（Transition / State ABC / 4 個 *State）。
- **素材**：`20-sales-state-machine §1–6`。
- **配圖**：**② 銷售狀態機** + **⑨ 類別圖（State pattern UML）**（同章互補：② 看行為、⑨ 看結構）。
- **設計取捨**：cart 是唯一驅動狀態（非動作歷史）；錢包保守原則（confirm silent/timeout → 保守 default）；TimedConfirm Template Method 收斂三種 confirm。
- **程式碼候選**：`SalesMachine.run` 主迴圈（cart invariant + emit + Transition）。

### 第 6 章 · 語音管線：聽與說（2.5 頁）
- **內容**：STT（Deepgram Nova-3 串流 / ch0 反交錯抽取 / arm-disarm 編排 / 每輪新連線）；TTS（edge-tts / 內容定址快取 / 播放期 prefetch）；繁中 NLU + 本地拼音糾錯小節。
- **素材**：`10 §3.1–3.2`、`20 §4`（NLU）、`00 §6`（STT env 家族，可選表格）。
- **配圖**：**⑥ STT 管線** + **⑦ TTS 管線**。
- **設計取捨（C 精華，本章重頭）**：ch0 突破（6 聲道降混稀釋 + 相位互抵 → 抽晶片處理過的 ch0）；真 barge-in 經 AEC 實測不可行；首字暖機是 Deepgram 串流固有地板（三輪實驗皆 revert）；內容定址快取 = 斷網可播。
- **程式碼候選**：`make_web_display` 不適用此章；可選內容定址快取 key（SHA1）或略。

### 第 7 章 · 前端鏡像與雙模態互動（2 頁）
- **內容**：phase-driven 狀態鏡像（後端 emit phase → 前端折成 standby + overlay）；語音 / 觸控雙模態（觸控只送命令、走同一 input queue、對話層零改動）；斷線韌性（指數退避 + 回歡迎畫面）；Glaze 玻璃 UI。
- **素材**：`30-web-mirror-and-frontend §1–5`。
- **配圖**：**③ web phase 狀態機**。
- **設計取捨**：phase-driven 禁前端樂觀旗號（觸發可能來自語音 / 自動結帳）；web 故障不得拖垮機器人服務（display try/except）。
- **真機素材**：webui 截圖佔位（點餐主畫面 / 確認卡 / 結帳 QR / 致謝）。

### 第 8 章 · 成果與驗證（1.5–2 頁）
- **內容**：711 pytest 回歸網（sales/ 嚴格不碰硬體 → Windows 可完整測）；Pi 實機驗收（辨識大幅改善 / 觸控全鏈路 / 點餐→結帳→付款→次客）；demo 成果。
- **素材**：`roadmap.md` 現況快照、各 `changelog*`「Pi 實測通過」紀錄。
- **配圖**：測試數據 / 驗收項目表格（report-design-system 砂色表頭表格元件）。
- **真機素材**：demo 成果照片佔位。

### 第 9 章 · 結論與展望（1 頁）
- **內容**：總結（規則匹配雙模態銷售機器人、可測試架構）；未來工作 —— 真掃碼器（改 `_PAY_TOKEN` 映射）、cap retry redesign、S7 搶話中斷、更多商品、NLU parser 邊緣。
- **素材**：`roadmap.md` 下一步候選。
- **配圖**：無。

### 後置（~1 頁）
- **參考資料**：Deepgram Nova-3 / edge-tts / Hiwonder TonyPi SDK / FastAPI / uvicorn / pypinyin 等。
- **封底**：自家專題標記 + 封底塗鴉。

---

## 4. 程式碼片段預算（精選 2–4 段，每段 <15 行）

優先序（落定時最多取 4 段，寧缺勿濫）：
1. **`SalesMachine.run` 主迴圈**（第 5 章）—— 展示 cart invariant + emit phase + Transition 調度的核心。**必選**。
2. **`QueueWorker._loop` 骨架**（第 4 章）—— 展示 FIFO 消費者 + try/finally 並行模式。
3. **`make_web_display`**（第 7 章）—— 展示 transport 接縫 + try/except 不拖垮機器人。
4. **內容定址快取 key 或 `parse_products` 片段**（第 6 章）—— 視版面餘裕，可略。

> 取碼時逐字對照實際 `myProgram/` 原碼，不得改寫示意（鐵則：不編造）。

---

## 5. 真機素材清單（使用者提供，版面預留佔位框）

| # | 用途 | 章 |
|---|---|---|
| P1 | 攤位 + 機器人 + 平板全景（封面 / 第 2 章）| 封面 / 2 |
| P2 | webui 點餐主畫面截圖 | 7 |
| P3 | webui 確認卡 / 結帳 QR / 致謝截圖（可合成一組）| 7 |
| P4 | demo 進行中照片（顧客互動）| 8 |

> 佔位策略：先把文字 + 9 張系統圖排完，照片區留標示框「待補：P1…」，使用者交付後填入。

---

## 6. 素材來源對映（取材 SSOT，避免重複造輪）

| 章 | 主要取材 |
|---|---|
| 1 | `architecture/00-system-overview.md §1` |
| 2 | `00 §5` |
| 3 | `00 §3–4`、`30 §8` |
| 4 | `10-runtime-and-workers.md §1–4` |
| 5 | `20-sales-state-machine.md §1–6` |
| 6 | `10 §3.1–3.2`、`20 §4`、`00 §6` |
| 7 | `30 §1–5` |
| 8 | `roadmap.md`、`changelogs/` |
| 9 | `roadmap.md` 下一步候選 |

---

## 7. 產出物規劃（落地時建在 `resources/report/`）

依 `report-design-system` skill `reference/report-pdf.md §10`：`report.html` + `tokens.css` + `assets/{fonts,doodles}/` + `out/`（PDF）。9 張圖以 `<img>` 引 `architecture/diagrams/NN-*.svg`（向量、列印清晰）。

**下一步**：本設計經使用者複審 → 進 `writing-plans` skill 擬「逐章寫 report.html」實作計畫。
