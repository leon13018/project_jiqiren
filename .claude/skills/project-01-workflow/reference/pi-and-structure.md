# Pi 端操作 / pineedtodo / 結構變動維護 / 部署資訊 / Pi 環境陷阱

本 reference 合併 5 個主題：判斷本輪變更是否需要使用者到 Pi 上手動做事（§Pi 端操作觸發條件）、
寫 Pi 端操作說明書的命名 / 結構規範（§pineedtodo 規範）、判斷本輪是否動到專案目錄結構
（§結構變動維護）、部署目標與同步流程（§部署資訊）、以及 Pi 執行環境的兩個已知陷阱
（§Pi 環境陷阱）。

主 agent 在 [`worktree.md`](worktree.md) 階段 3a / 3b（或 [`standard-workflow.md`](standard-workflow.md)
步驟 1a / 1b）做觸發判斷時參考本檔。

---

## §Pi 端操作觸發條件

主 agent 在審查後須判斷本輪變更**實際**會否導致使用者要在 Pi 終端手動做事。

### 觸發 ✅

- 新增 / 移除 Python 套件 import → `pip install / uninstall`
- 新增 / 移除 apt 系統套件 → `sudo apt install / remove`
- 硬體介面啟用（I2C / Camera / Audio / SPI）→ `raspi-config`
- 音訊裝置 / 音量設定（`alsamixer`、raspi-config Audio）
- 新增 systemd service / 自啟動腳本
- 一次性測試 / 校準 / 配置流程
- 任何修改 Pi 系統設定 / 環境變數 / 檔案權限的指令

### 不觸發 ❌

- 純程式邏輯修改 / 重構（無新依賴）
- 純文件 / markdown / memory / `.claude/` 內檔案更新
- `.gitignore` / `sync_pi.ps1` / git 相關設定變動
- CLAUDE.md / 規範自身修訂

### 輸出位置與行為

- 位置固定：`resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`
- **Append-only**：每輪只**新增**新檔，**既有檔不動、不改、不刪**。即使發現先前檔內容有誤，也是新開一個檔做修正紀錄，不回頭改既有檔。理由：當作歷史紀錄，方便日後查閱「某輪在 Pi 上做了什麼事」。
- **檔名規範 + 內容結構** → 見本檔 §pineedtodo 規範（寫新檔前必讀）

### 寫完 pineedtodo 後 → 主 agent 必須提醒使用者回報安裝狀況

> 「請在 Pi 上完成操作後跟我回報哪些**成功**裝上 / 啟用了（apt / pip 套件名、raspi-config 啟用項、systemd service 等），我會更新 `resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單）。失敗 / 未完成的不必回報，我們再討論。」

### 收到使用者回報成功 → 主 agent 更新已安裝清單

- Read `resources/requirements/raspberry_pi_setup.md` → 把使用者**明確**回報成功的項目（套件名 / 啟用項 / 服務名）加進對應區塊 → 標準 5 步收尾流程（純文件編輯例外，主 agent 自己改）
- **禁止自動推測 / 假設使用者已裝什麼**，必須有明確回報才寫
- 失敗 / 未回報項目絕不寫入

---

## §pineedtodo 規範

**主 agent 在 [`worktree.md`](worktree.md) 階段 3a 或 [`standard-workflow.md`](standard-workflow.md)
步驟 1a 撰寫新 pineedtodo 檔前必讀本段。**

**Why：** pineedtodo 是「per-task Pi 端操作說明書」歷史紀錄，append-only。命名一致 + 結構統一才能後續查閱友好。使用者 2026-05-23 確認此規範。

### 檔名格式

`resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`

- `<YYYY-MM-DD>` = 該輪 commit 日期（台灣時區）
- `<short_name>` = 主 agent 依任務性質決定的英數 + 底線描述（如 `TTS` / `camera_install` / `whisper_debug` / `audio_config`）
- **不強制 `_setup` 後綴**，保留彈性適應 install / config / test / debug 各種任務
- 同日多輪 → 用更具體 `short_name` 區隔（例：`2026-05-23_TTS_install.md` 與 `2026-05-23_TTS_debug.md`）

### 內容結構（鬆散指引 + 2 個固定要素）

**檔頭區（必有，置頂）：**
- `**建立日期：** YYYY-MM-DD`
- `**對應提交：** <commit_hash> — <commit 標題>`
- （可選短簡介）

**驗證段（必有，置尾）：**
- 跑什麼指令確認本輪 Pi 端操作真的成功
- 預期看到什麼輸出 / 行為
- 故障排除（如有疑難雜症）

**其他可自選章節：** Step 1..N、故障排除表、完成後說明、注意事項 — 主 agent 視任務性質自由決定。

**參考範例：** `resources/pineedtodo/2026-05-22_TTS_setup.md`

---

## §結構變動維護

主 agent 在審查後須判斷本輪變更是否會**動到專案目錄結構**（不論 tracked 或 gitignored）。

### 觸發 ✅

- 新增 / 刪除 / 移動 / 改名 **檔案**
- 新增 / 刪除 / 移動 / 改名 **資料夾**
- **包括 gitignored 路徑下的變動**（例如 `resources/userPrompt/` 內新增檔案）
- 修改 `.gitignore`

### 不觸發 ❌

- 純內容修改（檔名 / 路徑不變）
- commit message / git config 等不影響結構的變動

### 輸出位置與主 agent 動作

- **結構變動 → 更新 `.claude/code_map.md`**（當前資料夾 / 檔案結構的單一事實來源：新增加一行、刪除撤行、改名改路徑）。
- skill 內部檔案（reference / examples / scripts）增刪 → 更新 `SKILL.md` 路由表。

### 場景 B：使用者手動改結構 → 回報 → 主 agent 更新

使用者在 VSCode / 檔案總管手動改了目錄結構 → 跟主 agent 回報「我改了 X」→ 主 agent 觸發此事件，純文件編輯例外，走 [`standard-workflow.md`](standard-workflow.md) 5 步收尾循環。

---

## §部署資訊

**專案：互動式銷售輔助機器人（project_jiqiren）** — 人形機器人課程期末專題，5/7 已完成進度報告（PDF 在 `resources/presentation/`），主要程式碼骨架完成；2026-05-22 edge-tts 雲端 TTS 已在程式碼層接入。

### 部署目標（Raspberry Pi 4）

| 項目 | 值 |
|---|---|
| 使用者 | `pi` |
| 主機 | `raspberrypi.local` |
| Pi SSH | `pi@raspberrypi.local` |
| 遠端路徑 | `/home/pi/Desktop/project_jiqiren`（絕對路徑，符合 [myprogram-threading-paths.md](myprogram-threading-paths.md) Linux 路徑規範禁用 `~` 條） |
| GitHub Repo | `https://github.com/leon13018/project_jiqiren.git` |

### 同步流程

本機 git push → **PostToolUse hook 自動執行 sync_pi.ps1**（2026-05-25 起）→ 腳本 SSH 到 Pi 自動
`git pull`（首次則 clone）。SSH 金鑰已設定完成。

> **矛盾校正（以現況為準）**：早期 memory 寫「主 agent 不需手動跑 sync_pi.ps1」（2026-05-25），但
> **現行統一規則是 push 後永遠手動跑 `& sync_pi.ps1`**（PowerShell tool）。原因：background session 內
> PostToolUse hook 觸發**非 deterministic、不可依賴**；hook 自動跑時手動跑為 idempotent no-op
> （git pull → Already up to date），~3s SSH 成本可接受，省得判斷 session 類型。詳見
> [`standard-workflow.md`](standard-workflow.md) 與 [`worktree.md`](worktree.md) 階段 4。

### Pi 端執行環境

（已安裝清單細節見 `resources/requirements/raspberry_pi_setup.md`）

- Python：**3.11.9**（2026-05-23 升級；edge-tts 強制依賴；原 Pi OS 內建版本不足）。系統內建 Python 是 3.7；3.11.9 是 **source build 在 `~/Python-3.11.9/`**。
- 雲端 TTS：edge-tts（pip）+ mpg123（apt 播放器）
- （2026-05-23 使用者回報 edge-tts / mpg123 / Python 3.11.9 安裝成功，已寫入 Pi 已安裝清單。）

### S1 v2 跑法（2026-05-26 P6.S8 後）

```bash
python3.11 -m myProgram        # 推薦（透過 __main__.py）
python3.11 -m myProgram.main   # 等效
```

**舊跑法 `python3.11 -m myProgram.myProgram` 已失效**（檔名改為 main.py）。

### .gitignore 排除清單（2026-05-22 重構為精準排除）

- `.claude/settings.local.json`
- `.claude/worktrees/`
- `sync_pi.ps1`
- `resources/presentation/`
- `resources/userPrompt/`

→ 其餘 `resources/*` 子資料夾已 tracked，會 push 上 GitHub + sync 到 Pi。
→ `.claude/CLAUDE.md` tracked 並 push（2026-05-21 起），讓專案上下文跟著 repo 走。

---

## §Pi 環境陷阱

### 1. GLIBC / piwheels source build 陷阱

**事實：** 專案的 Raspberry Pi 4 跑 **Debian Buster + GLIBC 2.28**（2026-05-23 確認，從 `apt install`
看到 `http://archive.debian.org/debian buster/main`）。

**Why：** Buster 是 EOL Debian，GLIBC 與 libtiff 等系統 .so 版本相對舊（GLIBC 2.28、libtiff.so.5）。
piwheels（預設 pip index for Pi）為了相容較新發行版，**會 rebuild 包括舊版本套件的 wheel，連結到新
GLIBC / 新 .so SONAME**。結果：在 Buster 上跑這些 wheel 會 ImportError。降版 wheel 也常常救不了
（piwheels 連舊版都重編了）。

**症狀辨識：**
- `ImportError: /lib/.../libc.so.6: version 'GLIBC_X.XX' not found` → piwheels wheel 對 GLIBC 太新
- `ImportError: libXXX.so.N: cannot open shared object file` → piwheels wheel link 到新版系統 lib，但 Buster 只有舊 SONAME

**修法（優先順序）：**

- **首選 — 強制 source build 跳過 piwheels：**
  ```bash
  python3.11 -m pip uninstall -y <pkg>
  python3.11 -m pip install --no-binary :all: --index-url https://pypi.org/simple/ <pkg>
  ```
  `--no-binary :all:` 拿 .tar.gz source、`--index-url https://pypi.org/simple/` 跳過 piwheels（預設會混 pypi + piwheels）。編譯時連結 Buster 系統現有 lib，自然相容。
- 缺 C extension 對應 `*-dev`（編 Pillow 需 libjpeg-dev / libtiff5-dev 等）→ 先 `sudo apt install <list>-dev` 再 source build。
- 不推薦升級系統 lib（Buster repo 沒新版，從 source 編 .so + 管 ldconfig 比 source build 套件累很多）。

**已驗證套件（2026-05-23）：**
- `RPi.GPIO` → source build 過 ✅
- `Pillow<10`（9.5.0）→ source build + `libtiff5-dev` 過 ✅
- 純 Python 套件（`pyserial` / `pigpio` / `smbus2`）無此問題，piwheels 版可直接用

**Python stdlib C extension 缺失（如 `_tkinter`）是另一回事：** 不是 pip 套件問題，要 `apt install <對應>-dev`
（`tk-dev` / `tcl-dev`）→ `cd ~/Python-3.11.9 && make clean && ./configure --enable-optimizations --prefix=/usr/local && make -j4 && sudo make altinstall` 重編 Python。Pi 4 約 20~40 分鐘。重編後
`~/.local/lib/python3.11/` 既有 pip 套件**不受影響**（site-packages 跟 interpreter 分離）。

**相關歷史紀錄：**
- `resources/pineedtodo/2026-05-23_python311_rebuild_pillow_libtiff.md` — 3 個坑的完整修補紀錄
- `resources/pineedtodo/2026-05-23_python311_vendor_deps.md` — 廠商 SDK 依賴補裝原始計畫

### 2. 使用者報「X 沒作用」→ 先對 git commit 再 debug

當使用者實機回報「為什麼 X 沒按預期動作」但你 trace code 後覺得邏輯應該對的時候 — **不要急著挖 code**。
先一條指令確認 Pi 端 git commit 跟本機 main 同步：

```bash
git log -1 --oneline main && ssh -o ConnectTimeout=5 pi@raspberrypi.local "cd /home/pi/Desktop/project_jiqiren && git log -1 --oneline"
```

兩邊 SHA 對齊才繼續往下查；不同就先排查 sync_pi.ps1 hook / 手動 pull。

**Why：** 2026-05-26 使用者報「Dialog 路徑 mute 沒生效，只有 L4 路徑有」。trace code + 寫 Python 模擬
都證實兩條路徑邏輯一樣，差點開始猜「是不是某個 dispatch path 漏 `_invoke_subroutine_a`」。實際原因：
使用者印象中的差異來自之前的測試（commit `5fb7ab3` + `6483573` 之前），那時 `mute_opencv` 還只設 flag。
新版本兩條路徑都正常 — 猜對了但浪費一輪 round-trip。使用者直接挑明後（「先確定兩邊 git 同一個版本」）
才一條指令解決，省下後面要派 subagent 深挖的成本。

**How to apply：**
- 觸發條件：使用者實機回報「行為 X 不對」+ 你 read code 後覺得 logic 應該對
- **不要**：立刻派 Explore subagent / 開始改 code 假設有隱藏 bug
- **要**：一條 bash 對兩邊 commit SHA → 對齊才往下；不對齊先處理 sync
- 也適用：使用者說「之前明明可以的 X 現在不行」→ 比對最近 commit 是否動到 X

---

**相關 reference**：[worktree.md](worktree.md)（階段 3a / 3b 觸發判斷）/
[standard-workflow.md](standard-workflow.md)（步驟 1a / 1b + sync 規範）/
[CLAUDE.md](../../../CLAUDE.md)（部署資訊表 + 觸發條件大標題）
