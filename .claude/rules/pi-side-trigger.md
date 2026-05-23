# Pi 端操作觸發條件（給工作流程 1a / 3a 步驟參考）

主 agent 在審查後須判斷本輪變更**實際**會否導致使用者要在 Pi 終端手動做事。

**觸發 ✅：**
- 新增 / 移除 Python 套件 import → `pip install / uninstall`
- 新增 / 移除 apt 系統套件 → `sudo apt install / remove`
- 硬體介面啟用（I2C / Camera / Audio / SPI）→ `raspi-config`
- 音訊裝置 / 音量設定（`alsamixer`、raspi-config Audio）
- 新增 systemd service / 自啟動腳本
- 一次性測試 / 校準 / 配置流程
- 任何修改 Pi 系統設定 / 環境變數 / 檔案權限的指令

**不觸發 ❌：**
- 純程式邏輯修改 / 重構（無新依賴）
- 純文件 / markdown / memory / `.claude/` 內檔案更新
- `.gitignore` / `sync_pi.ps1` / git 相關設定變動
- CLAUDE.md / 規範自身修訂

**輸出位置與行為：**
- 位置固定：`resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`
- **Append-only**：每輪只**新增**新檔，**既有檔不動、不改、不刪**。即使發現先前檔內容有誤，也是新開一個檔做修正紀錄，不回頭改既有檔。理由：當作歷史紀錄，方便日後查閱「某輪在 Pi 上做了什麼事」。
- **檔名規範 + 內容結構** → memory `pineedtodo-spec`（寫新檔前必讀）

**寫完 pineedtodo 後 → 主 agent 必須提醒使用者回報安裝狀況：**
> 「請在 Pi 上完成操作後跟我回報哪些**成功**裝上 / 啟用了（apt / pip 套件名、raspi-config 啟用項、systemd service 等），我會更新 `resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單）。失敗 / 未完成的不必回報，我們再討論。」

**收到使用者回報成功 → 主 agent 更新已安裝清單：**
- Read `resources/requirements/raspberry_pi_setup.md` → 把使用者**明確**回報成功的項目（套件名 / 啟用項 / 服務名）加進對應區塊 → 標準 5 步收尾流程（純文件編輯例外，主 agent 自己改）
- **禁止自動推測 / 假設使用者已裝什麼**，必須有明確回報才寫
- 失敗 / 未回報項目絕不寫入
