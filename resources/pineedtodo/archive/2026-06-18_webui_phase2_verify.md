# Pi 驗收 — WebUI Phase 2 觸控雙向（2026-06-18）

> 前置：Phase 1 已驗（fastapi + 純 uvicorn 已裝）。**Phase 2 零新依賴**。
> 對應：spec `resources/specs/webui_phase2_2026-06-18_design.md`、plan `resources/plans/webui_phase2_2026-06-18_plan.md`；commits `433b469`→`cb1a994`（5 個）。

## 步驟
1. `git pull`（拉 Phase 2 commits）。
2. 在 Pi：`python3.11 -m myProgram --web`（建議帶 `STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10`；Phase 2 與 STT 無關，只為避免 arecord 噪訊干擾觀察）。
3. 機器人首次顯示商家主選單 → 在 **Pi 鍵盤按 `1`** 進叫賣模式（hawk）。**這是一次性 setup**，之後每輪交易結束自動回 hawk。
4. client 筆電瀏覽器連 `http://raspberrypi.local:8137/`（解析不到用 Pi IP）。

## 驗收項（全程**不碰 Pi 鍵盤、不講話**，純筆電觸控）
- [ ] **喚醒**：歡迎頁點「開始點餐」→ 機器人轉 L2 + 螢幕跳點餐頁（且機器人有語音 ack）。
- [ ] **點餐**：商品卡用 − / + 選數量（如冰紅茶 3）→ 點「加入購物車」→ 機器人語音 ack + 右側購物車長出「冰紅茶 ×3」；加入後預選 stepper 歸 1。
- [ ] **多商品**：再選刮刮樂 2 加入 → 購物車兩列正確。
- [ ] **結帳兩拍**：點「結帳」→ 機器人問「總共 X 元，正確嗎」+ 按鈕變「確認金額正確」→ 點它 → 機器人進結帳頁（QR）。
- [ ] **付款**：結帳頁點「我已完成付款」→ 機器人轉感謝頁 + 顯示已付金額。
- [ ] **唯讀購物車**：購物車欄商品只顯示「× N」無減量鈕（符合 add-only；機器人對話無減量單品路徑）。
- [ ] **斷線**：（Pi 端 Ctrl+C 停 server）→ 筆電右上「重新連線中」+ 歡迎頁點「開始點餐」**無反應、不跳轉**。重啟 server → 自動重連。
- [ ] **語音／觸控對等**：穿插用語音點一項、觸控點一項 → 兩者都進同一購物車（驗證單一 input queue）。

## 回報
- 各項 OK / NG；NG 附現象（畫面 / 機器人語音 / 終端 log）。
- 延遲體感。
- 放行 Phase 2 收尾（changelog/roadmap 標 ✅）？

## 備註（已知設計取捨，非 bug）
- 「結帳」→「確認」之間，按下確認到機器人 emit QR 的短暫空窗，按鈕文案仍顯示「確認金額正確」（刻意不本地 render，交由機器人 checkout 畫面接手；若觀察到覺得突兀再回報）。
