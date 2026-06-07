# Project_01 Roadmap — 現況與下一步

> 本檔只放**現況快照 + 下一步候選 + 路由**；詳細計畫分檔在 `roadmaps/`，已完成的歷史在 `changelogs/`（索引：`changelog.md`）。
> 2026-06-07 重構：原 544 行（絕大部分為已完成里程碑史）搬遷至 `changelogs/sessions_2026-05-26_to_06-01_detail.md`；舊「tts noisy」計畫段已隨 S2 落實（2026-05-27）而移除。

## 現況快照（2026-06-07）

- **主程式**：incremental-rebuild **S1-S6 ✅**（5 層狀態機 + TTS/動作/輸入三 worker 並行 + speak_and_wait 計時架構 + 客服統一），S7 中斷邏輯 ⬜（FIFO 夠用，未必要做）。pytest sales/ 344 個 test 函式（含參數化展開 380+）。
- **開發基建**：harness 四件套互鎖（hooks 反思閉環 / skill 17 列路由 + 18 reference / EDD 回歸 workflow + 11 場景題庫 / memory 健檢）——詳 `changelogs/changelog_2026-06-02_to_06-07_harness.md`。
- **展示面**：`resources/presentation/`（gitignored）尚空。

## 下一步候選（待使用者選方向）

| 選項 | 範圍 | 收益 / 前置 |
|---|---|---|
| **STT 導入** ⭐ | Whisper / vosk + push-to-talk 或 VAD | demo 收益最直接（語音點餐）；前置 S6 input queue 已就緒 ✅；STT↔TTS 回授坑已記 threading reference |
| **HTML UI** | FastAPI + WebSocket + 前端（詳 `roadmaps/html_ui_plan.md`） | 展示視覺收益最大；前置：S6/STT 穩定 |
| **期末 demo 準備** | demo 腳本 / 簡報素材 | 展示日近時優先級反超一切 |
| S7 中斷邏輯 | 新任務終止舊任務（action/tts queue） | 「快速切換」UX；race window 大，預設 FIFO 已夠用，**未必要做** |
| Cap retry redesign | 顧客超量被拒後的對話設計（dormant） | 三輪 revert 史，需先與使用者重新對齊 expectation |
| L1-L3 動作 UX 體感 | 純體感評估 + 微調 | 使用者實機反饋驅動 |

**建議優先序**：展示日有餘裕 → STT > HTML UI；兩週內要展示 → demo 準備優先。

## 路由

- 未來計畫詳檔：`roadmaps/html_ui_plan.md`（新計畫開新檔並在此加列）
- 歷史 / 里程碑：`changelog.md`（索引）→ `changelogs/`
- harness 留觀察項：`watchlist.md`｜EDD 題庫：`evals/`
