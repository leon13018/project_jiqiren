# Project_01 — 互動式銷售輔助機器人

人形機器人課程期末專題。Raspberry Pi 4 上的規則匹配點餐 / 收款模擬系統。

---

## ⛔ 絕對禁止（違反就壞東西）

1. **不要修改 `myProgram/ActionGroupControl.py` 和 `myProgram/Board.py`**
   廠商 Hiwonder TonyPi SDK，內含 Pi-only 路徑（`/home/pi/TonyPi/...`）與底層庫 import（`pigpio` / `RPi.GPIO` / `BusServoCmd` / `PWMServo` / `smbus2`）。改了直接破壞硬體通訊。只能 `Read` 引用、`import` 使用。
2. **不要在 Windows 本機安裝任何依賴**（`pip` / `npm` / `apt`）
   本機只負責編輯與 git，執行環境是 Pi。
3. **不要嘗試在 Windows import / 執行任何依賴廠商 SDK 的程式碼** — 必 ImportError。
4. **不要用 `git add -A` / `git add .`** — 明確列出檔名，避免誤加。

---

## ✅ 標準任務收尾循環（每次都做）

1. 編輯檔案
2. `git status` + `git diff` 確認變更範圍
3. `git add <具體檔名>`
4. `git commit -m "..."` 英文簡短訊息，附：
   `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`
5. `git push origin main`
6. **`& "C:\Users\LIN HONG\Desktop\Project_01\sync_pi.ps1"`** — SSH 自動 pull 到 Pi
7. 檢查退出碼 0 = 任務完成

> 若變更全在 ignored 路徑（`resources/` / `sync_pi.ps1` / `.claude/`）→ git 看不到 diff，跳過 commit/push/sync，但仍要告知使用者。

---

## 🌐 部署資訊

| 項目 | 值 |
|---|---|
| Pi SSH | `pi@raspberrypi.local` |
| Pi 路徑 | `/home/pi/Desktop/project_jiqiren` |
| GitHub Repo | `https://github.com/leon13018/project_jiqiren.git` |
| 部署方式 | 本機 push → 跑 `sync_pi.ps1` → SSH 自動 `git pull` |

---

## 📝 Pi 端要做的事 → 寫進 markdown，不執行

所有 `apt install` / `pip install` / `raspi-config` / systemd / 一次性指令
→ **條列到 `resources/requirements/raspberry_pi_setup.md`**，由使用者在 Pi 終端手動執行。
寫程式引入新套件時，**同步**更新該檔。

---

## 🔗 我需要更多細節時 → 看這裡

| 我要找... | 路徑 |
|---|---|
| 完整目錄結構 / 每檔職責 | `resources/projectStructure/projectStructure.md` |
| Pi 安裝什麼 / 跑什麼 bash | `resources/requirements/raspberry_pi_setup.md` |
| 專案背景 / 進度報告 | `resources/presentation/人形機器人期末專題5.7進度報告.pdf` |
| 廠商 SDK 完整 API 清單 | memory: `vendor-files` |
| 完整 5 步收尾流程細節 | memory: `standard-workflow` |
| 工作邊界（能做不能做） | memory: `workflow-constraints` |
| 使用者背景 | memory: `user-profile` |
| 部署細節（IP / repo / 路徑） | memory: `project-deployment` |

---

## 🛠️ 廠商 SDK 關鍵 API（直接 import 使用）

**`ActionGroupControl`**（播放 `/home/pi/TonyPi/ActionGroups/*.d6a` 動作）
- `runAction(actName, lock_servos='')`
- `runActionGroup(actName, times=1, with_stand=False, lock_servos='')`
- `stopAction()` / `stopActionGroup()`

**`Board`**（舵機 / 蜂鳴器）
- `setBusServoPulse(id, pulse, use_time)` — 總線舵機，pulse 0–1000
- `setPWMServoPulse(servo_id, pulse, use_time)` — PWM 舵機 1–2，pulse 500–2500
- `setBuzzer(state)`
- 各種 servo getter/setter（deviation / angle limit / temp / vin / pulse）

---

## ⚙️ 操作習慣

- 優先 `Read` / `Edit` / `Write` / `Glob` / `Grep` —— Windows shell 只給 git 用。
- 規劃階段（還沒確定要做什麼）→ 暫停確認，不要先 commit。
- 任務完成回報用 1-2 句話：改了什麼、Pi 是否同步成功。

---

## 📍 路徑規範（寫程式 / 設定檔時必遵守）

程式最終在 **Raspberry Pi 4 (Linux)** 上執行，所有檔案路徑必須符合：

1. **Linux 路徑格式** — 正斜線 `/`，不用反斜線 `\`；大小寫敏感。
2. **絕對路徑** — 從 `/` 開始的完整路徑；**不要**用：
   - Windows 路徑（`C:\Users\...`）
   - 相對路徑（依賴執行時 cwd，容易在不同呼叫方式下失效）
   - `~` 或 `~/`（bash 引號內 / subprocess / 某些 context 不會展開）

### 常用 Pi 端絕對路徑

| 用途 | 路徑 |
|---|---|
| 專案根目錄 | `/home/pi/Desktop/project_jiqiren` |
| 廠商動作檔（`.d6a`） | `/home/pi/TonyPi/ActionGroups/` |
| 廠商 SDK | `/home/pi/TonyPi/HiwonderSDK/` |
| Pi 使用者家目錄 | `/home/pi` |
