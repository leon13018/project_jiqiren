# myProgram/ — code_map（本層索引）

> 只索引 `myProgram/` 這一層的直接子項目；中顆粒描述。深入 `sales/` / `vendor/` → 讀其 `.claude/code_map.md`（若無，以本層說明為準）。

## 目錄
- `sales/` — 銷售對話業務邏輯（**核心**）：主控狀態機 `logic.py`、NLU 意圖辨識、商品 / 數量解析、購物車、L0–L5 各層狀態與跨層流程（取消確認 / 服務確認 / 數量追問等）、各層文案與常數。
- `vendor/` — 廠商 Hiwonder TonyPi SDK（🔒 `ActionGroupControl.py` / `Board.py` 禁改、只能 `import`；含 `pigpio` / `RPi.GPIO` / `smbus2` 等 Pi-only 依賴）。
- `.claude/` — 本層 CC 配置：`code_map.md`(本檔)。

## 單一檔案
- `main.py` — 進入點：多線程 + queue 架構、callback wire-up、各 worker 啟動與關閉。
- `tts.py` — 語音合成 worker（edge-tts 雲端 TTS；計時倒數 / UX 過場）。
- `action.py` — 機器人動作組 worker（呼叫 vendor SDK 播動作）。
- `input_reader.py` — 非阻塞鍵盤輸入 worker。
- `__init__.py` / `__main__.py` — 套件標記與 `python -m myProgram` 進入點。
- `CLAUDE.md` — 本層導引（綁定本層 code_map + SDD / vendor 提醒）。
