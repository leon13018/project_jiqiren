# Project_01 — Code Map（檔案導航索引）

> Claude / 開發者**快速定位檔案**用：只放結構 + 一行描述。
> 歷史 / 變更日誌見 `resources/projectStructure/projectStructure.md`（已降級為日誌，勿當 code map）。

## Top-level
- `myProgram/` — 機器人主程式（Pi 上執行）：點餐 / 收款規則匹配狀態機（見下）
- `tests/` — pytest 測試（sales 業務邏輯 + spec）
- `resources/` — 專案文件與產出物（spec / plan / review / 研究 / Pi 待辦…），非 code
- `.claude/` — CC 配置：`CLAUDE.md`、`code_map.md`(本檔)、`skills/`、`hooks/`(見 `NOTES.md`)、`agents/sales-coder.md`、`settings*.json`
- `sync_pi.ps1` 同步 myProgram→Pi　`pytest.ini` 測試設定

## myProgram/
- `main.py` 進入點：線程 + queue / callback wire-up　`tts.py` 語音 worker　`action.py` 動作組 worker（呼 vendor SDK）　`input_reader.py` 非阻塞鍵盤輸入
- `vendor/` 🔒 Hiwonder TonyPi SDK（`ActionGroupControl.py` / `Board.py`，禁改、只能 import）
- `sales/` 銷售對話業務邏輯：
  - `logic.py` 主控狀態機　`nlu.py` 意圖辨識　`product_parser.py` 商品/數量解析　`cart.py` 購物車
  - `states/` 各層狀態（`l0`–`l5` + `_cancel_confirm` / `_service_confirm` / `_l2_l3_qty_followup`）
  - `constants/` 常數（`l1`–`l5_text` / `keywords` / `products` / `actions` / `timing` / `shared`）

## resources/（依需要才開）
- `specs/` SDD 規格　`plans/` SDD 計畫　`reviews/` 審查報告　`research/` 研究筆記
- `requirements/` 需求(Pi setup)　`architecture/` 架構願景+前後端契約　`pineedtodo/` Pi 待辦
- `examples/` 範例 code　`presentation/` 報告　`userPrompt/` prompt 存檔
- `projectStructure/projectStructure.md` 專案日誌（大、歷史）
