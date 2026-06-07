# 未來計畫：HTML 網頁 UI（自 roadmap.md 搬遷）

> 2026-06-07 自 `resources/roadmap.md` 搬遷。狀態：待辦（等 STT / 主框架穩定）。

## UI：tkinter → HTML 網頁實現

**狀態更新（2026-05-25）：** `screen_display.py` 已歸檔到 `resources/examples/legacy_threading_v1/`（S1 v1→v2 重構時），現在 S1 v2 沒有 UI 層。此計畫變成「未來上 UI 時直接走 HTML，不再寫 tkinter」。

**決議：** 未來實作 UI 時直接走 **HTML 網頁模式**（瀏覽器 UI），跳過 tkinter 階段。

**Why:** tkinter 必須在 Pi 桌面 session 內才跑得起來，純 SSH 終端會 `_tkinter.TclError: no display name and no $DISPLAY`。開發迭代每次都得接 HDMI 螢幕 + 鍵盤太繁瑣。改成 HTML 後可直接從筆電瀏覽器連 Pi 開的 HTTP server 操作，SSH 開發流程更順。

**How to apply:**
- **時機：** S1 v2（純單線程業務邏輯）+ S2-S3（真實 TTS / 廠商動作）跑通後才動 UI 重構。
- **架構介接：** 後端 callback 注入點已在 `myProgram.py` 入口層 wire-up（A3-d）— 加 HTML 時新增 `sales/api.py` + WebSocket，把 callback 改成往 web client 推事件。
- **約束：** 廠商檔（[[vendor-files]]）仍禁改；sales/ 嚴格不 import 廠商 SDK（選項 C）。
- **觸發紀錄：** 使用者 2026-05-23 在 tkinter DISPLAY 錯誤討論中明確提出此計劃。

**狀態：** 待辦（等主框架完成）
