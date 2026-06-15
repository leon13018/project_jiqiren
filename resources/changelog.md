# 專案開發日誌（changelog）— 索引

> 本檔只做**路由**：詳細日誌按時期分檔在 `changelogs/`，新里程碑 append 到當期檔（換期就開新檔並在下表加列）。結構查 `.claude/code_map.md`；未來計畫查 `roadmap.md`。

| 時期 | 一句話 | 詳錄 |
|---|---|---|
| 2026-05-21 ~ 06-01 | 專案初建 → 規格書 → BDD+TDD L0-L5 → wire-up → S1-S6 增量重建 → hooks 上線 → 多輪 review/Waves → SDD 正式化 → CLAUDE.md→skill 遷移 | `changelogs/changelog_2026-05-21_to_06-01_foundation.md` |
| 2026-05-26 ~ 06-01（session 級詳錄） | P0-P8 重構、Wave 0-10、S2-S6 落地、L4 v2/v3、客服統一、SDD v1→v3 的逐 session 細節（自 roadmap 搬遷） | `changelogs/sessions_2026-05-26_to_06-01_detail.md` |
| 2026-06-02 ~ 06-07 | **Harness Engineering 弧**：反思 hook、EDD 回歸 harness、memory 治理、兩輪官方 plugin 逆向、自進化閉環、weak_asserts 維護循環 | `changelogs/changelog_2026-06-02_to_06-07_harness.md` |
| 2026-06-12 | **效能極限 campaign**：四鏡頭 review → 五波 SDD（熱路徑 -33~55%、TTS 快取零合成斷網可播、504→515 測試、行為零改變） | `changelogs/changelog_2026-06-12_perf_campaign.md` |
| 2026-06-08 ~（當期） | **回歸主程式開發**：STT barge-in Phase 1（Deepgram 串流 + keyterm）→ NLU 全繁體化 → 本地拼音糾錯層（Phase A/B + 統一 parser + 同音 tie-break + 合音還原 + Pi bug 修）→ 結帳收尾語音合併 | `changelogs/changelog_2026-06-08_main_dev.md` |
