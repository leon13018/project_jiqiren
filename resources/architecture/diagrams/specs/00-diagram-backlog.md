# 00 · 報告系統圖 backlog（待畫清單 + 待辦）

> **本檔＝索引 / 待辦單**。「怎麼畫」全在 **`architecture-diagram` skill**（`.claude/skills/architecture-diagram/`），不在此重述。新 session 從零重畫時：載入該 skill，逐張照它的完整流程跑，畫哪張就回本檔對照來源檔與 spec 狀態。
> 訂於 2026-06-22；**2026-06-23 改宗淺色蠟筆風**（風格權威移交 `report-design-system` skill、深色霓虹退場）。**2026-06-23 畫圖階段收官：①–⑨ 全部淺色交付完成，使用者宣告畫圖階段到此結束（⑩⑪ 不畫）。** 現況：**深色 ①–⑤ 已歸檔 `_legacy-dark/`**（含舊 `theme/`，淺色重畫來源素材）；**淺色 ①–⑨ 全已交付**（png+svg 置 `diagrams/` 主層；①②③ html 源在 report-design-system 基準，④⑤ 源在 `_legacy-dark/`，⑥⑦⑧⑨ html 在主層自足）；**⑩⑪ 未畫**（階段結束、不在本批範圍）。`specs/` 內容 spec 沿用（風格無關）。

## 怎麼用本檔

1. 載入 `architecture-diagram` skill。
2. 依下方**波次順序**選一張，照 skill 流程一個循環：主題 spec → **讀實際碼核對**（鐵則 1，別信 digest）→ 設計 SDD（`/frontend-design` + `/superpowers:brainstorming`）→ `/superpowers:writing-plans` 寫畫圖計畫 → 派 **opus** subagent 實作 → 多方截圖自檢（先全圖再局部）→ 你驗收 → 2× PNG + SVG commit。
3. **①–⑤ 已有 spec**（`specs/01–05.md`）可複用其「核對過的碼事實 + 版面」起手；**⑥–⑪ 無 spec**，照 skill step 1–2 現寫。
4. 共用前提（**skill 內已詳述，不重複**）：**視覺風格＝ `report-design-system` skill**（淺色蠟筆：`diagram-crayon.md` 濾鏡/版面 + `report-pdf.md §2/§3` 色票字型 + `assets/benchmarks/` 三基準對照）；起手骨架 = `architecture-diagram/assets/skeleton.html`（淺色自足）；render/QA 見 `render-and-qa.md` + `render-pipeline.md`；DPR **每次實測**；交付 2× PNG（四角驗無黑邊）+ 內嵌 2×PNG 的 SVG。（舊深色 `theme/` 已移入 `_legacy-dark/`、不再用。）

## 11 張清單（已核准）

| # | 系統圖 | 畫什麼（要點） | 主要來源（**畫前必讀實際碼**） | spec |
|---|---|---|---|---|
| ① | Process / Thread 並行模型 | 單 process：1 主線程 + N daemon；queue + EventBus 解耦；**3 producer 扇入單一 input queue**；daemon=True → os._exit | `main.py` `queue_worker.py` `tts.py` `action.py` `input_reader.py` `stt.py` `web/server.py` `web/bus.py`；doc `00§3`/`10` | ✅ `01` |
| ② | L0–L5 銷售對話狀態機 | 4 運行層 L1→dialog→L4→L5；**cart 驅動轉移**；**enter_hawk 回流循環**（主角）；錢包保守 confirm 閘（cancel6s/service24s/checkout12s/C-2 6s/qty12s）；L0 共通 NLU 基座 | `states/machine.py` `l1.py` `l2_l3_dialog.py` `l4.py` `l5.py` `_cancel_confirm.py` `_service_confirm.py` `_timed_confirm.py` `_invalid_qty_reask.py` `_l2_l3_qty_followup.py` `constants/timing.py`；doc `20` | ✅ `02` |
| ③ | web phase 交互狀態機 | 後端 emit phase 驅動前端切畫面（standby/ordering/**checkout_confirm**/checkout/thankyou）；觸控命令上行 inject；**phase-driven、禁前端樂觀**。⚠️ `checkout_confirm` 不在 `machine.py:29 _PHASE_BY_STATE`、是 dialog 內子 phase（`l2_l3_dialog.py` `io.display` emit）——別當平行 5 phase | `web/{bus,display,app,server,commands,models}.py` `webui/app.js` `index.html` `states/machine.py`(_emit)；doc `30` | ✅ `03` |
| ④ | 端到端時序圖 | 一輪互動（觸控喚醒→點冰紅茶→結帳→致謝）跨**泳道**：前端 / WS / 主線程 / STT / TTS / Action | `00§5` 為骨架，逐步回讀 ①②③ 對應碼 | ✅ `04` |
| ⑤ | 部署 / 網路拓樸 | Pi=server（`--hawk --web`）、筆電/手機=渲染端（連 `:8137`）、ReSpeaker USB、Deepgram 雲；**Pi 自身瀏覽器跑不動前端**（GPU+Chromium<111 無 OKLCH） | `00§7` `30`；`webui/serve.py` `web/server.py`；`resources/requirements/raspberry_pi_setup.md` | ✅ `05` |
| ⑥ | STT 管線 | arecord `-c6` 抽 ch0（XVF-3000 處理過 ASR 聲道）→ Deepgram Nova-3 WS → speech_final → `inject`；**每輪 arm/disarm**（SttSender/Receiver）；prearm 藏握手 | `stt.py`；doc `10` | ✅ `06` |
| ⑦ | TTS 管線 | queue → edge-tts synth → **內容定址快取**（命中/未命中分支）+ 1-deep prefetch → mpg123；常駐 asyncio loop；語速三段 | `tts.py` `tts_prewarm.py` `queue_worker.py`；doc `10` | ✅ `07` |
| ⑧ | 模組依賴地圖 | `sales/`（純邏輯、零硬體）↔ `main.py` wire-up ↔ workers ↔ `web/` ↔ `webui/`；**callback 注入邊界**（sales 不 import 硬體/廠商 SDK） | `00§4`；各模組 import 結構 | ✅ `08` |
| ⑨ | 類別圖 | `SalesMachine` / `State`(ABC) / `Transition` / 4 個 `*State` / `Cart` / `DialogIO` / nlu 純函式 關係 | `states/machine.py` `cart.py` `dialog_io.py` `nlu.py`；doc `20` | ✅ `09` |
| ⑩ | 資料契約圖（原「資料模型」改框） | ⚠️**無真 DB** → 畫 `Cart`(dict[str,int]) ↔ Pydantic DTO ↔ 前端；`commands.py` 觸控→token 對照；2 商品常數（冰紅茶/刮刮樂，九折硬編） | `web/models.py` `cart.py` `web/commands.py` `constants/products.py` | ✗ |
| ⑪ | 啟動分流流程（新增） | `main._run_wiring`：`--hawk` / `--web` / `SALES_KEYBOARD` 三旗標分支 + **防呆**（無 mode flag 又無鍵盤 → early return）；webui-boot 背景啟 server | `main.py`（`_run_wiring` / `main`） | ✗ |

## 波次順序（建議）

- **Wave A 核心**：① ② ③ —— ✅ **淺色已交付**（深色原版 → `_legacy-dark/`；淺色 png+svg 在 `diagrams/`、html 源在 report-design-system 基準）。釘定全系列風格基準 + 硬化 skill（9 條視覺 gotchas + 色彩 token 化）。
- **Wave B 高值**：④ 時序、⑤ 部署 —— ✅ **淺色已交付**（2026-06-23 換膚：copy `_legacy-dark/` → 外科改 head/濾鏡/inline、body 座標逐字保留；html/png/svg 進 `diagrams/` 主層、html 源在此）。本波硬化 skill：QA 平行 3 opus 質檢（只讀靜態 PNG+bbox dump）、render 必序列化（Playwright 單一共享瀏覽器）、§5.5 canonical bbox dump、CSS 改動換新埠繞快取。
- **Wave C 管線**：⑥ STT、⑦ TTS（線性機械，風格穩後快）。
- **Wave D 結構**：⑧ 模組依賴、⑨ 類別。
- **Wave E 低**：⑩ 資料契約、⑪ 啟動分流。

> 波內**獨立的圖一次平行派 ≥2 個 opus implementer 各寫各檔 HTML（不 render）**；**render 全歸 orchestrator 序列獨占**（Playwright 單一共享瀏覽器，見 SKILL「⚡ 平行加速」+ step 5.5）——別讓 ≥2 圖同時 render。

## 待辦 checklist

每張「done」＝ 照 skill 流程完成 + 多方自檢通過（先全圖再局部、無黑邊/截字/線交纏/跨 band 相撞）+ **使用者驗收** + 交付 2× PNG + SVG + 更新本檔勾選 + commit。

- [x] ① Process / Thread　- [x] ② L0–L5 狀態機　- [x] ③ web phase　✅ **淺色已交付**（深色原版在 `_legacy-dark/`）
- [x] ④ 時序　- [x] ⑤ 部署 / 網路　✅ **淺色已交付**（2026-06-23 換膚；html/png/svg 在 `diagrams/` 主層；深色原版在 `_legacy-dark/`）
- [x] ⑥ STT 管線　- [x] ⑦ TTS 管線　✅ **淺色已交付**（2026-06-23；html/png/svg 在 `diagrams/` 主層；使用者逐輪像素級 QA + 箭頭全重拉 + attribute 置中後定版）
- [x] ⑧ 模組依賴　- [x] ⑨ 類別　✅ **淺色已交付**（2026-06-23；html/png/svg 在 `diagrams/` 主層）。⑧＝Hexagonal 注入邊界（orchestrator 自己從零重做，使用者逐項像素級驗收：注入 seam signature、5 條 lazy 自 main 右緣中點扇出、queue_worker 三依賴邊補上、全卡蠟筆 hachure 著色、main/core 收窄頁面變窄）；⑨ UML 三格框 + generalization 三角逐輪調 +（123620 修）«returns» 箭頭尖不戳入 Transition 框
- [ ] ⑩ 資料契約　- [ ] ⑪ 啟動分流　—— **不畫**（2026-06-23 畫圖階段收官止於 ⑨；未來若要補再開）
