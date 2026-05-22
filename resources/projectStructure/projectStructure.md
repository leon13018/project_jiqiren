# 專案目錄結構

> 本檔案記錄整個專案的資料夾與檔案結構，方便日後快速查閱。
> 最後更新：2026-05-21

---

## 完整結構（不含 `.git/` 內部檔案）

```
Project_01/
├── .claude/                              # Claude Code 設定資料夾
│   ├── CLAUDE.md                         # 📌 每輪載入的專案上下文（路徑規範 / 工作流 / 禁令）
│   └── settings.local.json               # 本機 Claude 設定（.gitignore 排除）
│
├── .gitignore                            # Git 忽略清單
│
├── sync_pi.ps1                           # Windows 端 SSH 部署腳本（.gitignore 排除）
│                                         # 用途：push 後執行，SSH 到 Pi 自動 git pull / clone
│
├── myProgram/                            # 主程式資料夾（所有 .py 在此）
│   ├── myProgram.py                      # ✍️ 自寫 — 主程式：狀態機、規則匹配、點餐、結帳
│   ├── screen_display.py                 # ✍️ 自寫 — Tkinter POS 螢幕（訂單、QR Code）
│   ├── robot_actions.py                  # ✍️ 自寫 — 機器人動作封裝（頭部 / 四肢）
│   ├── ActionGroupControl.py             # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│   └── Board.py                          # 🚫 廠商 SDK — Hiwonder TonyPi，禁止修改
│
└── resources/                            # 開發參考資源（.gitignore 排除）
    ├── presentation/
    │   └── 人形機器人期末專題5.7進度報告.pdf   # 5/7 進度報告簡報
    │
    ├── requirements/
    │   └── raspberry_pi_setup.md         # Pi 端依賴清單與部署操作（apt / pip / raspi-config 等）
    │
    └── projectStructure/
        └── projectStructure.md           # 本檔案
```

---

## `.gitignore` 排除清單

```
.claude/settings.local.json
sync_pi.ps1
resources/
```

⚠️ `resources/` 整個被 ignore，本資料夾下的所有檔案（PDF、Pi 依賴清單、本結構圖）僅作為 **本機開發參考**，不會 push 到 GitHub / Pi。
✅ `.claude/CLAUDE.md` **會** push 上去（2026-05-21 起），讓專案上下文跟著 repo 走；只有 `.claude/settings.local.json`（本機 Claude 設定）保持 ignore。

---

## 各檔案職責簡述

### 自寫程式碼（myProgram/）

| 檔案 | 職責 |
|---|---|
| `myProgram.py` | 主程式入口；全域狀態（`has_customer`, `waiting`）、商品目錄、規則匹配、叫賣循環、顧客服務流程 |
| `screen_display.py` | `POSScreen` 類別；Tkinter 視窗、queue 執行緒安全、`show_welcome()` / `update_order()` |
| `robot_actions.py` | 動作封裝；`nod_head` / `shake_head` / `look_forward` / `action_idle` / `action_greet` / `action_pay` |

### 廠商 SDK（myProgram/，禁止修改）

| 檔案 | 職責 |
|---|---|
| `ActionGroupControl.py` | 播放 `/home/pi/TonyPi/ActionGroups/*.d6a` 四肢動作組 |
| `Board.py` | 總線舵機（頭部）、PWM 舵機、蜂鳴器、GPIO 等底層控制 |

> 廠商檔內含 Pi-only 路徑與底層庫 import（`pigpio`, `RPi.GPIO`, `BusServoCmd` 等），**Windows 本機無法 import 測試**，實際執行驗證一律在 Raspberry Pi 4 上。

### 部署 / 設定

| 檔案 | 職責 |
|---|---|
| `sync_pi.ps1` | SSH 到 `pi@raspberrypi.local`，自動 `git pull` / clone 到 `/home/pi/Desktop/project_jiqiren` |
| `.gitignore` | 排除 `.claude/settings.local.json`, `sync_pi.ps1`, `resources/` |
| `.claude/CLAUDE.md` | 每輪載入的專案上下文（禁令 / 工作流 / 路徑規範 / 廠商 API）|
| `.claude/settings.local.json` | Claude Code 本機設定（.gitignore 排除）|

### 文件 / 參考（resources/）

| 檔案 | 職責 |
|---|---|
| `resources/presentation/人形機器人期末專題5.7進度報告.pdf` | 5/7 期末專題進度報告簡報 |
| `resources/requirements/raspberry_pi_setup.md` | Pi 端需要的 apt / pip 依賴、raspi-config 設定、bash 操作 |
| `resources/projectStructure/projectStructure.md` | 本檔案 — 專案目錄結構 |

---

## 更新紀錄

| 日期 | 變更 |
|---|---|
| 2026-05-21 | 建立初版；`resource/` 已重新命名為 `resources/` |
