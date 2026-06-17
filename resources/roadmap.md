# Project_01 Roadmap — 現況與下一步

> 本檔只放**現況快照 + 下一步候選 + 路由**；詳細計畫分檔在 `roadmaps/`，已完成的歷史在 `changelogs/`（索引：`changelog.md`）。
> 2026-06-07 重構：原 544 行（絕大部分為已完成里程碑史）搬遷至 `changelogs/sessions_2026-05-26_to_06-01_detail.md`；舊「tts noisy」計畫段已隨 S2 落實（2026-05-27）而移除。

## 現況快照（2026-06-17）

- **主程式**：incremental-rebuild **S1-S6 ✅**（5 層狀態機 + TTS/動作/輸入三 worker 並行 + speak_and_wait 計時架構 + 客服統一）。pytest sales/ **592** 個 test 通過。
- **STT**：**Phase 1 ✅**（Deepgram Nova-3 串流 + `main.py` arm/disarm 佈線 + keyterm；Pi 實測通過）；**真 barge-in 搶話經 AEC 實測不可行**（硬體~0 / 最佳線性上限~10dB / 近距聲學耦合非線性；詳 `specs/stt_p2_2026-06-16_spec.md` §1）→ **Phase 2 v3（來源端閘 prewarm + 讀 ch0）已實作 ✅**：prewarm 就起 arecord（背景暖好）、暖機期送**等長靜音**（機器人聲讀進但永不送 Deepgram，同時維持連線取代 KeepAlive），arm 翻 `live` 旗號解 mute 改送真實顧客音訊 → 無自我回授 + 消除 v2「arm 才起 arecord」的啟動延遲（v1 結果端閘擋不住延遲轉錄、v2 改來源端閘 KeepAlive；演進史見 changelog 里程碑 6）。**待 Pi 實測**：驗無自我回授仍成立 + 播完跟手度改善（`STT_ARECORD_DEVICE=hw:CARD=ArrayUAC10` 原生 6ch；喇叭插樹莓派板載）。
- **NLU/語音 robustness**：全繁體化 ✅；**本地拼音糾錯層 ✅**（問數量 / 問商品 + 統一 token-parser + 完全同音 tie-break + 合音還原；Pi 實測通過）；**結帳收尾語音合併 ✅**（Pi 實測通過）。
- **開發基建**：harness 四件套互鎖（hooks 反思閉環 / skill 路由 + reference / EDD 回歸 / memory 健檢）——詳 `changelogs/`。
- **展示面**：`resources/presentation/`（gitignored）尚空。

## 下一步候選（待使用者選方向）

| 選項 | 範圍 | 收益 / 前置 |
|---|---|---|
| **HTML UI** | FastAPI + WebSocket + 前端（詳 `roadmaps/html_ui_plan.md`） | 展示視覺收益最大；前置 S6/STT 穩定 ✅ |
| **期末 demo 準備** | demo 腳本 / 簡報素材 | 展示日近時優先級反超一切；`presentation/` 尚空 |
| S7 / 搶話中斷邏輯 | 新任務終止舊任務（action/tts queue） | 與 STT Phase 2 搶話重疊；預設 FIFO 已夠用，併入 P2 處理 |
| Cap retry redesign | 顧客超量被拒後的對話設計（dormant） | 三輪 revert 史，需先重新對齊 expectation |
| 拼音 parser 邊緣 | 無分隔雙數量 / filler / 插字 garble / 合音表擴充 | demo 浮現才修（C1/C3/C4 + D4 於 2026-06-15 deferred）|

**建議優先序**：展示日有餘裕 → HTML UI；展示日近 → demo 準備優先。（STT 已收尾於 Phase 2 turn-taking；真 barge-in 經實測收掉。）

## 路由

- 未來計畫詳檔：`roadmaps/html_ui_plan.md`（新計畫開新檔並在此加列）
- 歷史 / 里程碑：`changelog.md`（索引）→ `changelogs/`
- harness 留觀察項：`watchlist.md`｜EDD 題庫：`evals/`
