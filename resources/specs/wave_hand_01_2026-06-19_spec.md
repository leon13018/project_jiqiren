# 揮手動作 wave_hand → wave_hand_01 — Mini SDD spec

**日期：** 2026-06-19
**類型：** 使用者要求的動作組常數值替換（超級小，純值）

- **檔**：`myProgram/sales/constants/actions.py`
  - `:22` `ACTION_L1_HAWK`（L1 叫賣揮手）
  - `:40` `ACTION_L5_FAREWELL`（L5 致謝揮手）
- **改前**：兩者皆 `"wave_hand"`
- **改後**：兩者皆 `"wave_hand_01"`
- **Why**：使用者要求把全部揮手動作改用 `wave_hand_01` 動作組。
- **範圍**：`sales/` 各層只透過常數名（`ACTION_L1_HAWK` / `ACTION_L5_FAREWELL`）引用、不寫死字串 → 改值即全域生效；無 caller 改動。grep 全 repo「wave_hand」僅此 2 處於 `myProgram/`，其餘皆 resources 歷史文件 / skill 範例（不動）。無測試硬寫 `"wave_hand"`（測試以常數名引用，值無關）→ 測試零回歸。
- **Out of scope**：不改其他動作（bow / point_screen / L2 / L3 等）；不動歷史 changelog / spec 內的 `wave_hand` 字樣（那是當時紀錄）。
- **⚠️ Pi 依賴**：`/home/pi/TonyPi/ActionGroups/wave_hand_01.d6a` 必須存在，否則 `do_action("wave_hand_01")` 經廠商 SDK 靜默無動作（揮手不會動）。使用者須確認該 .d6a 已在 Pi。
- **驗證**：
  - Windows：`python -m pytest tests/` 全綠（基線 649）。
  - Pi：L1 進叫賣 / L5 致謝離場時，機器人揮手改跑 `wave_hand_01` 動作組。
