# Changelog — 前端 webui（2026-06-18 ~ 當期）

> 本檔記前端網頁點餐 UI 的開發弧。主題：Glaze Liquid Glass 玻璃 UI buildless 化 + Pi 實機效能切片 + 後端串接（Phase 1+）。階段路線見 `roadmaps/html_ui_plan.md`；Phase 0 SDD 計畫 `plans/webui_phase0_2026-06-18_plan.md`。

## 里程碑（執行序）

### 0. WebUI Phase 0 — Glaze 玻璃點餐頁 buildless 原型 + Pi 效能裁決

**決策**：互動模式 **A（顯示鏡像）**——語音驅動機器人、螢幕只鏡像狀態（未來 WebSocket 推）；觸控元件保留當備援。**Buildless**——無 npm / bundler / React runtime，純 `index.html` + 一支 `app.js` + CSS，對齊「Windows 禁裝依賴」紅線（「用 React」決策以 buildless + CDN 調和）。

**來源**：claude.ai/design 的「Glaze」設計系統（Apple iOS 27 Liquid Glass：backdrop-filter blur + OKLCH 漸層 + SF Pro），經 Claude Design DesignSync connector 匯入「In-Person Ordering」點餐頁。

**建置**（`myProgram/webui/`，worktree `worktree-webui-phase0` → ff-merge `db2d6b7`）：
- `index.html` + `app.js`（~546 行）+ `app.css` + `tokens/`（6 個 Glaze token CSS；`fonts.css` 重寫成 CDN Inter + Noto Sans TC，取代未打包的專利 SF Pro）+ `serve.py`（no-cache stdlib 靜態伺服器，綁 0.0.0.0）。
- `app.js`：DCLogic 狀態 / 購物車 / QR 邏輯逐字移植；5 元件（AdBanner / QuantityStepper / Button / Badge / IconButton）重寫成「回傳 HTML 字串 + `data-act` 事件委派」；5 狀態 demo 切換器（待機 / 點餐 / 結帳 / 感謝 / review）。
- **效能重構（核心）**：`syncCart()` 只局部更新 `#tb-cart` / `#act-<id>` / `#cart-inner`，玻璃 `backdrop-filter` 面板永不重建（避免每次 +/- 重算 ~4 層模糊 → 解「卡頓」）；動效全走 transform / opacity（GPU 合成）不碰 max-height / clip-path（會 reflow + 重算模糊）。
- **動效迭代**（多輪使用者校正）：加入 ↔ 數量器 morph（藍長鈕 → 靠左短膠囊 → 分裂兩圓、保留 +/− 符號、0.38s）；購物車列「先空出位置 → 整卡由左流星刷入（含尾光）→ 刪除反向 fade + 右滑 + 往上縮收合」；背景 OKLCH 霓虹飄移（`.bg-glows` `inset:-10%` 防 drift 位移露黑邊垂直分界線）。

**Pi 實機裁決（2026-06-18，Phase 0 最終目的）**：Pi 4 自帶 Chromium **跑不動**——
- **很卡**：GPU 撐不住多層 backdrop-filter 玻璃模糊 + 連續動畫（一直擔心的 fps 風險，實機證實）。
- **部分顏色失效**：設計大量用 OKLCH 色彩，而 **OKLCH 需 Chromium 111+（2023）**；Pi 的 Chromium 較舊 → `oklch()` 整個失效、那些顏色消失（hex / rgba 的顏色還在 → 症狀是「**有些**顏色出不來」）。

→ **裁決：玻璃方向過關，但渲染端改用 client**——同 wifi 筆電瀏覽器（GPU 夠力 + Chromium 夠新、OKLCH 正常）連 `http://raspberrypi.local:8137`（解析不到用 Pi IP）渲染；**Pi 只跑 `serve.py` 送靜態檔**。與前後端契約拓樸一致（裝置連區網 server），只是主展示螢幕從「Pi 接 HDMI」改成「筆電」，機器人邏輯照樣跑 Pi。

**下一步（Phase 1+）**：見 `roadmaps/html_ui_plan.md`——Phase 1 後端 FastAPI + WebSocket（`main.py` 的 `TerminalSim` callback 改成往 web client 推事件）、Phase 2 `sales/` 結構化事件注入點、Phase 3 端到端 Pi 整合。**Pi 相容備援檔**（OKLCH→sRGB fallback + 砍 blur，讓 Pi 自瀏覽器也能顯示）暫不做（demo 走筆電）。

### 1. WebUI Phase 1 — FastAPI 顯示鏡像後端（點餐即時鏡像到 client 瀏覽器）

**決策**（brainstorm → spec `specs/webui_phase1_2026-06-18_design.md`）：傳輸 **FastAPI + uvicorn**（process 內背景執行緒，契約原訂）；模組 **`myProgram/web/`** 獨立 transport 套件（與 sales/ 分離）；狀態觀測用**事件回呼 `display` 穿透 sales/**（非輪詢，使用者選純事件驅動）；互動模式 A（瀏覽器被動鏡像）。

**建置**（SDD plan `plans/webui_phase1_2026-06-18_plan.md`，8 task，worktree → ff-merge `8005e57`）：
- **`display` 事件回呼 seam**（第 15 callback，穿 `logic.run`→`DialogIO`→`SalesMachine`，終端 no-op）：`machine.py` 進場 emit phase（standby/ordering/checkout/thankyou + l5 paid）；`l2_l3_dialog.py` 每輪 emit ordering+cart（購物車逐項長出）。**既有 621 測試零行為改變**（None guard）。
- **`myProgram/web/`**：`bus.py`（EventBus，`run_coroutine_threadsafe` 橋機器人執行緒→uvicorn loop）+ `display.py`（cart→dict）= 純 stdlib Windows-TDD；`models.py`（Pydantic DTO）+ `app.py`（`/api/state`+`/ws/state`+StaticFiles）+ `server.py`（uvicorn 背景執行緒）= Pi-only。
- **`main.py --web`**：`_run_wiring` 旗號分流 + lazy import 隔離 + graceful fallback。**前端 `app.js`**：WS client 驅動 render、phase→view 映射、後端 catalog 為商品來源、live 觸控停用、`?demo=1` 保留 Phase 0 demo。
- **測試**：633 Windows pytest 綠（pydantic/fastapi/uvicorn 那層 Pi-only `ast.parse`）；雙 reviewer（code-quality ✅）。

**Pi 實機驗收（2026-06-18）✅**：裝 fastapi + 純 uvicorn → `python3.11 -m myProgram --web` → client 筆電連 `raspberrypi.local:8137` → **待機→點餐→購物車增量→結帳 QR→感謝 各階段即時鏡像正確、延遲幾乎沒有**（pineedtodo `2026-06-18_webui_phase1_deps_verify.md`）。

**Hardening（驗收後，spec `specs/webui_phase1_hardening_2026-06-18_spec.md`，ff-merge `d2cb850`，635 綠）**：① UX——live 模式停用所有改鏡像狀態的本機觸控（`act!=="adGoto"`），修「斷線時點開始點餐跳轉死頁」（使用者報告）；② 2 反思守衛——`machine._emit` phase-map `.get`（未知 current 不 KeyError）+ `main._run_wiring` web 啟動全程 graceful（`except Exception`，port 衝突等不 crash 機器人）。

### 2. WebUI Phase 2 — 觸控雙向（觸控注入機器人 input queue，完成互動閉環）

**決策**（brainstorm → spec `specs/webui_phase2_2026-06-18_design.md`）：**全模態對等**（觸控可喚醒 / 點餐 / 結帳 / 付款）+ **方案 A 結構化逐筆注入**。關鍵洞察：`read_terminal_key`（L1 喚醒）與 `read_customer_input`（對話）共用同一 `input_reader` queue → **單一 `inject` seam 驅動全流程**，觸控產生與語音 / 鍵盤相同的字串、走相同 NLU、機器人照常開口 ack，**對話層零改動**。與 Phase 1 `display` 下行對稱的上行 seam。

**建置**（SDD plan `plans/webui_phase2_2026-06-18_plan.md`，worktree → ff-merge `cb1a994`）：
- **`web/commands.py`（新，純 stdlib Windows-TDD）**：`to_token(cmd)` 結構化命令 → 對話既有消費的 token（wake→`c`、order→`品名數量`、checkout→結帳 token、confirm→`正確`、pay→`s`；非法→None）。
- **`web/app.py`·`server.py`（Pi-only）**：WS `receive_text`（Phase 1 丟棄）改 `to_token`→`on_input`；`create_app(bus, on_input)` / `start(bus, on_input, …)`。
- **`main.py`**：`_run_wiring` 注入 `on_input = input_reader.inject`。
- **前端 `app.js`**：live 觸控改送 WS 上行命令（取代 Phase 1 一律停用）；本地預選 stepper + 加入（add-only，購物車欄唯讀，∵對話無減量單品路徑）；結帳兩拍（結帳→本地「確認金額」affordance→確認）；斷線 `sendCommand` no-op（保留 Phase 1「斷線不跳轉」修正）。
- **SDD 三段審**：sales-coder 實作 → Iron-Law 649 綠 → spec-reviewer + code-quality-reviewer（2 Important + Minor）→ 修補（test stub 簽章 / dead import / stepper 歸位）→ 複驗綠。

**Pi 實機驗收（2026-06-19）✅**：client 筆電純觸控走通 **喚醒（Pi 按 1 進 hawk 後筆電「開始點餐」）→ 點餐（預選數量加入、購物車即時鏡像）→ 結帳 → 確認 → 付款** 全鏈路。

**Hotfix（Pi 實測發現，spec `specs/webui_phase2_checkout_token_fix_2026-06-19_spec.md`，ff-merge `69815e4`）**：觸控結帳無效 root cause——commands token 用「結賬」(賬) 只匹配 C-2 子狀態的 `KEYWORDS_C2_CHECKOUT`，但顧客在 L3 點結帳走**主迴圈** `classify_intent(.,"normal")` → `nlu._KEYWORDS_CHECKOUT`（「結帳/帳」），帳≠賬 → 主路徑落 unclear。修：token 結賬→結帳；測試改**行為斷言** `classify_intent(token,"normal")=="結帳"`（原 membership 驗錯集故漏抓）。

**下一步**：觸控閉環完成 → demo 準備 / 真 OpenCV·掃碼器接線（屆時 `wake`/`pay` 映射改真觸發、與 sim token 解耦）。

## 流程 / 沉澱
- **零新 Python 依賴**：字型 / 圖示走 CDN、伺服器用 stdlib `http.server` → Pi 不必 pip / apt（Phase 0 需 Pi 有網路抓 CDN；離線在地化留待後續）。
- **cwd-pinned worktree 收尾**：本弧在釘住 cwd 的 worktree 內，收尾用 `git -C 主checkout` 做 ff-merge + push（協議 `worktree.md`）；worktree 空殼因自鎖留待新 session 清。
- 反思採納：AdBanner 輪播、Phosphor 圖示 url-fixup（Phase 0）；phase-map-unguarded-keyerror、web-startup-non-import-error-crash（Phase 1 hardening 守衛）——皆採納，記於 `reflections/proposals.md`。
- Phase 1 worktree 收尾：主 agent 全程不進 worktree（純 git `worktree add` + 派 sales-coder 編輯 + `git -C` 收尾）→ 無 cwd 自鎖、worktree remove 乾淨（驗證 worktree.md「cwd-pinned 例外 Option B」）。
- Phase 2 純 git worktree 全程（spec / hotfix mini-spec 先 commit main → worktree 改 code → `git -C` 收尾），連 3 個 worktree（phase2 / checkout-fix / wave-hand-01）remove 皆乾淨無自鎖殘殼。
- 反思採納 `token-test-asserts-wrong-keyword-set`（Phase 2 結帳 hotfix）：token 映射測試要斷言「token 真正被消費路徑的行為」（`classify_intent` / `parse_products`），不是 membership in 一個貌似相關的鄰近 keyword 集——原 checkout 測試驗 C-2 集（賬）而非主迴圈 dispatch（帳）故漏抓。記於 `reflections/proposals.md`。
