# Project_01 — root 層 code_map（本層索引）

> 只索引 root 這一層的直接子項目；一行一個、**粗顆粒宏觀**描述（細節留給各目錄自己的 `.claude/code_map.md`）。
> 要深入某目錄 → 讀 `<該目錄>/.claude/code_map.md`（若無則表示尚未建子索引，以本層說明為準）。

## 目錄
- `myProgram/` — 機器人主程式（Raspberry Pi 上執行）。點餐 / 收款規則匹配系統：`main.py` 線程+queue 進入點與 callback wire-up、`tts.py` / `action.py` / `input_reader.py` 三個 worker、`vendor/` 廠商 Hiwonder TonyPi SDK（🔒 禁改、只能 import）；核心在 `sales/` 銷售對話業務邏輯——L0–L5 多層對話狀態機（歡迎 / 點餐 / 商品數量 / 結帳收款等）+ 取消確認 / 服務確認等跨層流程、NLU 意圖辨識、商品與數量解析、購物車、各層文案與常數。
- `resources/` — 專案文件與產出物（非 code）：SDD 規格 / 計畫 / 審查報告、研究筆記、架構願景與前後端契約、Pi 需求與待辦、範例 code、報告、prompt 存檔、roadmap / changelog。
- `tests/` — pytest 測試：sales 業務邏輯回歸網 + spec 測試。
- `.claude/` — Claude Code 配置：`code_map.md`(本檔，root 層索引)、`skills/`（`project-01-workflow` 等）、`hooks/`（自動化 hook + `NOTES.md`）、`agents/`（`sales-coder`）、`settings*.json`。（專案 `CLAUDE.md` 在 root，不在此資料夾內）
- `.git/` — Git 版控內部資料（非專案內容；噪音候選，日後處理）。

## 單一檔案
- `CLAUDE.md` — 專案主規範入口（核心紅線 + 繁中規範 + skill 觸發表 + 本層 code_map 指標）；root 直接放。
- `pytest.ini` — pytest 設定。
- `.gitignore` — Git 忽略清單。
- `sync_pi.ps1` — （gitignored）把 `myProgram/` 同步到 Raspberry Pi 的腳本；push 後手動執行。
