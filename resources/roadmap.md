# Project_01 Roadmap — 現況與下一步

> 本檔只放**現況快照 + 下一步候選 + 路由**；詳細計畫分檔在 `roadmaps/`，已完成的歷史在 `changelogs/`（索引：`changelog.md`）。
> 2026-06-07 重構：原 544 行（絕大部分為已完成里程碑史）搬遷至 `changelogs/sessions_2026-05-26_to_06-01_detail.md`；舊「tts noisy」計畫段已隨 S2 落實（2026-05-27）而移除。

## 現況快照（2026-06-21）

- **主程式**：incremental-rebuild **S1-S6 ✅**（5 層狀態機 + TTS/動作/輸入三 worker 並行 + speak_and_wait 計時架構 + 客服統一）。**全 `tests/` 704 passed**（`py -3.14 -m pytest`，含 sales 回歸網；⚠️ PATH 的 `python` 是 3.12 無 pytest）。**【2026-06-20~21 UX/觸控/啟動弧】**：① 叫賣循環修復（hawk loop idle-gated monotonic 自驅 + 非阻塞 `tts.is_idle()`；移除唯一 production no-op 的 schedule 死抽象——原本實機從不循環）；② 終端 toggles `SALES_SHOW_COUNTDOWN`（藏倒數行）/ `SALES_VOICE`（預設隱藏機器人 echo、`=1` 才顯示，保留導航+錯誤；2026-06-21 反轉自原 `SALES_QUIET`）/ `SALES_KEYBOARD`（預設 0=關鍵盤、`=1` 開；關時改 web/語音控制）+ `--hawk` 進場 flag（跳選單直接叫賣，未來模式加新 flag）+ 啟動防呆（無 mode flag 且鍵盤關 → 印訊息結束防卡死）；③ **移除 OpenCV 偵測 → `'t'`/觸控「開始點餐」觸發 L2**（大重構 -589 行：刪 opencv 4 callbacks/`_S1State`/`OPENCV_*`常數/`l0_subroutine_a`；`via_subroutine_a`+`L1_via_subroutine_a`→`enter_hawk`；`web/commands._WAKE_TOKEN` `c`→`t`）；④ 啟動效能（`--web` 的 fastapi/uvicorn import+start 移背景 thread + tts/action/stt 預熱，修「banner 按 1 卡好幾秒」）；⑤ flaky tts 測試根治 + boot.join timeout。**全 pytest 綠、Pi by-ear 待驗**。詳 `changelogs/changelog_2026-06-20_touch_ux_startup.md`。
- **STT**：**定版 pure Phase 1 ✅**（Deepgram Nova-3 串流 + `main.py` arm/disarm 佈線 + keyterm；`-c 6` 反交錯抽 ch0 處理聲道、arm 才開麥；Pi 驗收辨識大幅改善 ✅）。**prewarm 三輪實驗皆 Pi 實測 revert**——v1 自我回授 / warm-arecord 暖機積壓「收不到音」/ keepalive 未改善辨識 → 放棄（架構性問題）。**聲道（2026-06-20 同源 A/B 推翻舊收斂）：ch0 處理聲道才是最佳（全降混反而最差——稀釋＋相位互抵）→ 定版 `-c 6` 抽 ch0。****真 barge-in 經 AEC 實測不可行**（詳 `specs/stt_p2_2026-06-16_spec.md` §1）。難詞（刮刮樂）若仍不足 → keyterm（已上、對中文有效）/ Deepgram 參數。**開麥裁切**（arecord 在 arm 才開、~300–500ms 冷啟,搶快講掉開頭如「紅茶三瓶→三瓶」）為固有問題、warm-arecord 修法失敗（收不到音）→ **接受**；**Demo 操作:提示音播完停 ~0.5s 再回答**即不裁切。**Pi 端**：`STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10`；喇叭插樹莓派板載。**turn-latency 旋鈕（2026-06-19 實作待 Pi 驗收）**：條件式 ALSA drain（idle 跳過 0.3s 尾巴）/ `STT_TTS_TIMING` 計時 log / `STT_ENDPOINTING_MS` env（預設 300，可 A/B 200）；行為預設不變，驗收單 `pineedtodo/2026-06-19_stt_tts_turn_latency_verify.md`（含 drain 自我回授實測風險點）。**持久連線（2026-06-19 實作待 Pi 驗收）**：Pi 量測證實每輪空檔 ~0.72s 中連線握手佔 ~580ms（裝置僅 ~140ms）→ 改整場共用一條 Deepgram 連線 + KeepAlive（`SttWorker` 連線層常駐 + 收音層每輪 + `_capturing` 閘門 + 死則重連），第 2 輪起開麥 ~140ms、解「開頭被裁」；驗收單 `pineedtodo/2026-06-19_stt_persistent_connection_verify.md`。**hardening + prearm（2026-06-19 實作待 Pi 驗收）**：修 3 個併發 freeze-risk（壞訊息不殺連線 / 建線移出 `_lock` 不凍 disarm / disarm join 逾時跳 Finalize 防掛死，皆出自 `proposals.md` 反思）+ prearm 首連線（`wait_idle` 前背景建線藏 turn-1 540ms 握手）；spec `stt_conn_harden_prearm_2026-06-19`。**zombie bug 修復（已 Pi 驗收 ✅）**：逐輪 disarm Finalize 破壞 Deepgram 後續 finalization → speech_final 空白漏辨識 → 移除 Finalize（`4ff428e`）；全流程 Pi 實測通過（點餐→上限 reask→結帳→付款→次客）。**辨識 robustness（待 Pi 驗收）**：空定稿退用最後非空 interim（`802c646`）；endpointing 試調 450 → 背景音下 Deepgram 等不到靜默、**speech_final 永遠不發 → 整輪 timeout** → 回歸 300（`de444dc`）。spec `stt_recognition_robustness_2026-06-19`。**warm-arecord（2026-06-19 試 → Pi 實測 revert）**：收音層搬 prearm 暖機，但與 mpg123 播放並行開 arecord 在 Pi 上**間歇收不到音/收靜音**（撞舊版「收不到音」老坑）、且開頭裁頭未全解 → revert（`7be81a2`）。退回 arecord 在 arm 才開的可靠版（recognition robustness + endpointing 300 保留）；開頭 40ms 裁頭靠「講話別卡提示音收尾瞬間」習慣解。spec `stt_warm_arecord_2026-06-19`（含 revert 教訓）。**每輪新連線（2026-06-20 待 Pi 驗收）**：持久連線用久累積辨識 lag（interim 空、結果 disarm 後才回）→ 改每輪新連線（disarm 收線、移除 keepalive、prearm 藏重連延遲）；核心假設「lag 來自持久連線」待 Pi 實證（`4d8d388`，spec `stt_per_turn_connection_2026-06-20`）。若 lag 仍在＝假設否證，可 revert 回持久連線版。**【2026-06-20 收尾】連線/lag 已 Pi 驗收接受 ✅（現行每輪新連線 `4d8d388`、持久版 `4ff428e` 為退路）。「首字掉字」第二弧三試皆敗——`STT_MIC_OPEN_DELAY_MS`（微改善）/ `STT_PREROLL_MS`（數位靜音暖不夠）/ `STT_EARLY_MIC`（早麥收機器人音→回授卡死+辨識污染）皆 default-off 保留不清；首字偶掉接受為 Deepgram 串流暖機固有地板，demo 靠「自然頓半拍」+ 觸控 UI 備援。**【2026-06-20 辨識準確度突破 ✅】**整體辨識極差根因 = 6 聲道降混稀釋晶片處理過的 ch0 → 改 `-c 6` 反交錯抽 ch0，Pi by-ear 驗收整體大幅改善（spec `stt_ch0_capture_2026-06-20`）。詳 `changelogs/changelog_2026-06-19_stt_realtime.md`。**
- **NLU/語音 robustness**：全繁體化 ✅；**本地拼音糾錯層 ✅**（問數量 / 問商品 + 統一 token-parser + 完全同音 tie-break + 合音還原；Pi 實測通過）；**結帳收尾語音合併 ✅**（Pi 實測通過）。
- **開發基建**：harness 四件套互鎖（hooks 反思閉環 / skill 路由 + reference / EDD 回歸 / memory 健檢）——詳 `changelogs/`。
- **前端 webui**：**Phase 0 + 1 + 2 全 ✅**（前端互動閉環完成）。Phase 0 玻璃原型（Pi 自瀏覽器跑不動 GPU+OKLCH → demo 走 client 筆電、Pi 只當 server）。**Phase 1 = FastAPI 顯示鏡像後端**（`--web` 啟 uvicorn、`display` 回呼穿 sales/ emit、WS 推送、前端 client 驅動；Pi 驗收即時鏡像 ✅）。**Phase 2 = 觸控雙向**：client 觸控經 `web/commands.to_token` → `input_reader.inject` 同一 input queue 驅動全流程（喚醒/點餐/結帳/確認/付款），對話層零改動 → 語音或觸控雙模態。**Pi 驗收觸控全鏈路 ✅（2026-06-19，含結帳 token hotfix 結賬→結帳）**。詳 `roadmaps/html_ui_plan.md`。**Phase 2 後 Pi 實測 UX 微調**（斷線回歡迎畫面 / StaticFiles no-cache / live 商品卡剩餘標籤 / 揮手動作 `wave_hand_01`；詳 `changelogs/changelog_2026-06-18_webui.md` §3）+ **結帳前確認卡片（v1 繼續點餐路徑 + v2 機器人 phase 驅動，Pi 驗收 ✅；§4）** —— **demo-ready**。
- **展示面**：`resources/presentation/`（gitignored）尚空。

## 下一步候選（待使用者選方向）

| 選項 | 範圍 | 收益 / 前置 |
|---|---|---|
| 前端 webui **Phase 0+1+2 ✅** | 互動閉環完成（玻璃原型 + FastAPI 顯示鏡像 + 觸控雙向，Pi 驗收 OK）；**wake 已定版為觸控「開始點餐」/ 終端 `'t'`（OpenCV 偵測 2026-06-20 移除）**；`pay`/`'s'` 仍模擬，未來接真掃碼器改 `_PAY_TOKEN` 映射即可（對話層零改動） | demo 直接用此前端；硬體接線非 demo 必需 |
| **期末 demo 準備** | demo 腳本 / 簡報素材 | 展示日近時優先級反超一切；`presentation/` 尚空 |
| S7 / 搶話中斷邏輯 | 新任務終止舊任務（action/tts queue） | 與 STT Phase 2 搶話重疊；預設 FIFO 已夠用，併入 P2 處理 |
| Cap retry redesign | 顧客超量被拒後的對話設計（dormant） | 三輪 revert 史，需先重新對齊 expectation |
| 拼音 parser 邊緣 | 無分隔雙數量 / filler / 插字 garble / 合音表擴充 | demo 浮現才修（C1/C3/C4 + D4 於 2026-06-15 deferred）|

**建議優先序**：HTML UI **Phase 0+1+2 全完成**（Pi 驗收顯示鏡像 + 觸控雙向 OK，前端互動閉環）→ **期末 demo 準備**（展示日近時優先級最高，`presentation/` 尚空）。（STT 定版 Phase 1；turn-taking v1/v2/v3 與真 barge-in 皆經 Pi 實測收掉。）

## 路由

- 未來計畫詳檔：`roadmaps/html_ui_plan.md`（新計畫開新檔並在此加列）
- 歷史 / 里程碑：`changelog.md`（索引）→ `changelogs/`
- harness 留觀察項：`watchlist.md`｜EDD 題庫：`evals/`
