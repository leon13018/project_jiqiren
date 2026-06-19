# Project_01 Roadmap — 現況與下一步

> 本檔只放**現況快照 + 下一步候選 + 路由**；詳細計畫分檔在 `roadmaps/`，已完成的歷史在 `changelogs/`（索引：`changelog.md`）。
> 2026-06-07 重構：原 544 行（絕大部分為已完成里程碑史）搬遷至 `changelogs/sessions_2026-05-26_to_06-01_detail.md`；舊「tts noisy」計畫段已隨 S2 落實（2026-05-27）而移除。

## 現況快照（2026-06-18）

- **主程式**：incremental-rebuild **S1-S6 ✅**（5 層狀態機 + TTS/動作/輸入三 worker 並行 + speak_and_wait 計時架構 + 客服統一）。pytest sales/ **592** 個 test 通過。
- **STT**：**定版 pure Phase 1 ✅**（Deepgram Nova-3 串流 + `main.py` arm/disarm 佈線 + keyterm；`-c 1` plughw 降混、arm 才開麥；使用者確認辨識正常）。**prewarm 三輪實驗皆 Pi 實測 revert**——v1 自我回授 / warm-arecord 暖機積壓「收不到音」/ keepalive 未改善辨識 → 放棄（架構性問題）。聲道試驗收斂:ch0／單一 raw 麥軌皆不如全麥降混。**真 barge-in 經 AEC 實測不可行**（詳 `specs/stt_p2_2026-06-16_spec.md` §1）。難詞（刮刮樂）若仍不足 → 下一步攻 keyterm / Deepgram 參數（prewarm、聲道皆已窮舉）。**開麥裁切**（arecord 在 arm 才開、~300–500ms 冷啟,搶快講掉開頭如「紅茶三瓶→三瓶」）為固有問題、warm-arecord 修法失敗（收不到音）→ **接受**；**Demo 操作:提示音播完停 ~0.5s 再回答**即不裁切。**Pi 端**：`STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10`；喇叭插樹莓派板載。
- **NLU/語音 robustness**：全繁體化 ✅；**本地拼音糾錯層 ✅**（問數量 / 問商品 + 統一 token-parser + 完全同音 tie-break + 合音還原；Pi 實測通過）；**結帳收尾語音合併 ✅**（Pi 實測通過）。
- **開發基建**：harness 四件套互鎖（hooks 反思閉環 / skill 路由 + reference / EDD 回歸 / memory 健檢）——詳 `changelogs/`。
- **前端 webui**：**Phase 0 + 1 + 2 全 ✅**（前端互動閉環完成）。Phase 0 玻璃原型（Pi 自瀏覽器跑不動 GPU+OKLCH → demo 走 client 筆電、Pi 只當 server）。**Phase 1 = FastAPI 顯示鏡像後端**（`--web` 啟 uvicorn、`display` 回呼穿 sales/ emit、WS 推送、前端 client 驅動；Pi 驗收即時鏡像 ✅）。**Phase 2 = 觸控雙向**：client 觸控經 `web/commands.to_token` → `input_reader.inject` 同一 input queue 驅動全流程（喚醒/點餐/結帳/確認/付款），對話層零改動 → 語音或觸控雙模態。**Pi 驗收觸控全鏈路 ✅（2026-06-19，含結帳 token hotfix 結賬→結帳）**。詳 `roadmaps/html_ui_plan.md`。**Phase 2 後 Pi 實測 UX 微調**（斷線回歡迎畫面 / StaticFiles no-cache / live 商品卡剩餘標籤 / 揮手動作 `wave_hand_01`；詳 `changelogs/changelog_2026-06-18_webui.md` §3）—— **UI 微調進行中**。
- **展示面**：`resources/presentation/`（gitignored）尚空。

## 下一步候選（待使用者選方向）

| 選項 | 範圍 | 收益 / 前置 |
|---|---|---|
| 前端 webui **Phase 0+1+2 ✅** | 互動閉環完成（玻璃原型 + FastAPI 顯示鏡像 + 觸控雙向，Pi 驗收 OK）；後續純選配——真 OpenCV / 掃碼器接線時 `wake`/`pay` 映射改真觸發 | demo 直接用此前端；硬體接線非 demo 必需 |
| **期末 demo 準備** | demo 腳本 / 簡報素材 | 展示日近時優先級反超一切；`presentation/` 尚空 |
| S7 / 搶話中斷邏輯 | 新任務終止舊任務（action/tts queue） | 與 STT Phase 2 搶話重疊；預設 FIFO 已夠用，併入 P2 處理 |
| Cap retry redesign | 顧客超量被拒後的對話設計（dormant） | 三輪 revert 史，需先重新對齊 expectation |
| 拼音 parser 邊緣 | 無分隔雙數量 / filler / 插字 garble / 合音表擴充 | demo 浮現才修（C1/C3/C4 + D4 於 2026-06-15 deferred）|

**建議優先序**：HTML UI **Phase 0+1+2 全完成**（Pi 驗收顯示鏡像 + 觸控雙向 OK，前端互動閉環）→ **期末 demo 準備**（展示日近時優先級最高，`presentation/` 尚空）。（STT 定版 Phase 1；turn-taking v1/v2/v3 與真 barge-in 皆經 Pi 實測收掉。）

## 路由

- 未來計畫詳檔：`roadmaps/html_ui_plan.md`（新計畫開新檔並在此加列）
- 歷史 / 里程碑：`changelog.md`（索引）→ `changelogs/`
- harness 留觀察項：`watchlist.md`｜EDD 題庫：`evals/`
