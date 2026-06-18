# HTML 網頁 UI — 階段路線

> 2026-06-07 自 `resources/roadmap.md` 搬遷。**2026-06-18 更新：Phase 0 + Phase 1 ✅ 完成**（Pi 實機驗收即時鏡像 OK）——這是進行中的前端弧，分階段如下。

## 階段路線（2026-06-18）

| 階段 | 範圍 | 狀態 |
|---|---|---|
| **Phase 0 — 玻璃效能切片** | Glaze Liquid Glass 點餐頁 buildless 化（`myProgram/webui/`）+ Pi 實機量 fps | **✅ 完成**（計畫 `plans/webui_phase0_2026-06-18_plan.md`；詳錄 `changelogs/changelog_2026-06-18_webui.md`；commit `db2d6b7`） |
| **Phase 1 — 後端串接 + 即時鏡像** | FastAPI + WS server + `display` 事件回呼穿 sales/ emit（**含原 Phase 2 事件注入 + Phase 3 端到端，本階段一併完成**）+ 前端 WS client 驅動 | **✅ 完成**（spec `webui_phase1_2026-06-18_design.md`；詳錄 changelog；commit `8005e57` + hardening `d2cb850`；**Pi 驗收即時鏡像 ✅、延遲幾乎沒有**） |
| **Phase 2 — 觸控雙向** | client 觸控點餐 → 注入機器人 input queue（類 STT inject seam），從「顯示鏡像」進化到「可觸控操作」，完成互動閉環 | ⬜ 下一步 |

### Phase 0 裁決（2026-06-18 Pi 實機）
玻璃方向過關，但 **Pi 4 自帶 Chromium 跑不動**（GPU 撐不住 backdrop-blur → 卡；Chromium <111 無 OKLCH → 部分顏色失效）→ **demo 由同 wifi client 筆電瀏覽器渲染、Pi 只當 `serve.py` 靜態伺服器**。**Phase 1+ 的前端輸出端 = client 筆電，不是 Pi 螢幕。**（要 Pi 自瀏覽器也能顯示 → 需做 OKLCH→sRGB fallback + 砍 blur 的「Pi 相容檔」，暫不做。）

### Phase 1 接點（既有資產）
- **後端 callback 注入點**已在 `main.py` 入口層 wire-up（`TerminalSim` callback 類別餵 `logic.run`）——Phase 1 把這些 callback 改成往 web client 推事件。
- **前後端契約**：`architecture/frontend-backend-contract.md`（使用者註記部分內容過時 → Phase 1 設計時校對）。
- **約束**：廠商檔（[[vendor-files]]）禁改；`sales/` 不 import 廠商 SDK；UI 文案繁中；前端落 `myProgram/webui/`（`sync_pi.ps1` 才會自動部署 Pi）。

---

## 背景：tkinter → HTML 網頁實現（原始決議）

**狀態更新（2026-05-25）：** `screen_display.py` 已歸檔到 `resources/examples/legacy_threading_v1/`（S1 v1→v2 重構時），現在 S1 v2 沒有 UI 層。此計畫變成「未來上 UI 時直接走 HTML，不再寫 tkinter」。

**決議：** 未來實作 UI 時直接走 **HTML 網頁模式**（瀏覽器 UI），跳過 tkinter 階段。

**Why:** tkinter 必須在 Pi 桌面 session 內才跑得起來，純 SSH 終端會 `_tkinter.TclError: no display name and no $DISPLAY`。開發迭代每次都得接 HDMI 螢幕 + 鍵盤太繁瑣。改成 HTML 後可直接從筆電瀏覽器連 Pi 開的 HTTP server 操作，SSH 開發流程更順。

**How to apply:**
- **時機：** S1 v2（純單線程業務邏輯）+ S2-S3（真實 TTS / 廠商動作）跑通後才動 UI 重構。
- **架構介接：** 後端 callback 注入點已在 `myProgram.py` 入口層 wire-up（A3-d）— 加 HTML 時新增 `sales/api.py` + WebSocket，把 callback 改成往 web client 推事件。
- **約束：** 廠商檔（[[vendor-files]]）仍禁改；sales/ 嚴格不 import 廠商 SDK（選項 C）。
- **觸發紀錄：** 使用者 2026-05-23 在 tkinter DISPLAY 錯誤討論中明確提出此計劃。

**狀態：** 待辦（等主框架完成）
