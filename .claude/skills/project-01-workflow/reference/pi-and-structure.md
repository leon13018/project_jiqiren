# Pi 端操作 / pineedtodo / 結構變動維護 / 部署資訊 / Pi 環境陷阱

> **🎯 何時讀本檔**：判斷本輪是否需 Pi 端操作 → 寫 pineedtodo；結構變動要更新 code_map；或查部署資訊 / Pi 環境陷阱。

## 目錄
- Pi 端操作觸發條件
- pineedtodo 規範
- 結構變動維護（code_map 巢狀判準）
- 部署資訊
- Pi 環境陷阱（GLIBC / git 對齊）

---

## Pi 端操作觸發條件

主 agent 審查後判斷本輪變更**實際**會否導致使用者要在 Pi 終端手動做事。

**觸發 ✅**：新增/移除 Python 套件 import（pip）｜apt 系統套件｜硬體介面啟用 I2C/Camera/Audio/SPI（raspi-config）｜音訊裝置/音量（alsamixer）｜systemd service/自啟動｜一次性測試/校準/配置｜任何改 Pi 系統設定/環境變數/權限。

**不觸發 ❌**：純程式邏輯修改/重構（無新依賴）｜純文件/markdown/memory/`.claude/` 檔｜`.gitignore`/`sync_pi.ps1`/git 設定｜CLAUDE.md/規範自身修訂。

**輸出**：位置固定 `resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`；**append-only**（每輪新增新檔，既有不動不刪；發現先前有誤也新開檔修正）。

**寫完 pineedtodo → 主 agent 提醒使用者回報**：「請在 Pi 完成後回報哪些**成功**裝上/啟用（套件名/raspi-config 項/service），我更新 `resources/requirements/raspberry_pi_setup.md`。失敗/未完成不必報。」收到回報 → Read 該清單把**明確**回報成功項加進去（純文件編輯例外，主 agent 自己改，走標準 5 步收尾）。**禁自動推測**；失敗/未報項絕不寫入。

---

## pineedtodo 規範（寫新檔前必讀）

**檔名**：`resources/pineedtodo/<YYYY-MM-DD>_<short_name>.md`
- `<YYYY-MM-DD>` = 該輪 commit 日期（台灣時區）。
- `<short_name>` = 英數+底線描述（`TTS` / `camera_install` / `whisper_debug`）；**不強制 `_setup` 後綴**；同日多輪用更具體名區隔。

**內容結構（鬆散 + 2 固定要素）**：
- **檔頭（置頂）**：`建立日期` / `對應提交：<hash> — <標題>` /（可選短簡介）。
- **驗證段（置尾）**：跑什麼指令確認本輪 Pi 操作成功、預期輸出/行為、故障排除。
- 其他自選：Step 1..N / 故障排除表 / 完成說明 / 注意事項。
- 參考範例：`resources/pineedtodo/2026-05-22_TTS_setup.md`。

---

## 結構變動維護

主 agent 審查後判斷本輪是否**動到專案目錄結構**（tracked 或 gitignored 皆算）。

**觸發 ✅**：新增/刪除/移動/改名**檔案或資料夾**（含 gitignored 路徑，如 `resources/userPrompt/` 新增檔）｜修改 `.gitignore`。
**不觸發 ❌**：純內容修改（檔名/路徑不變）｜commit message/git config。

**動作 — 更新「變動所在那層」的 `.claude/code_map.md`**（巢狀：每層各有索引、只列直接子項目）。
- **巢狀判準（可優雅失敗）**：改哪層更新哪層。**若該層沒有自己的 `.claude/code_map.md`** → 通常**不需動**：其最近有 code_map 的祖先是粗顆粒、不列個別檔（例：新增 `tests/sales/` 測試檔，`tests/` code_map 只記「`sales/` — 回歸網」不列檔，故不動）。**只有變動影響到某層 code_map 已寫出的直接子項目**（新增/刪除/改名）才更新該層。
- skill 內部檔（reference/examples/scripts）增刪 → 更新 `SKILL.md` 路由表。
- **場景 B（使用者手動改結構）**：使用者回報「我改了 X」→ 主 agent 觸發此事件（純文件編輯例外，走 [standard-workflow.md](standard-workflow.md) 5 步）。
- **code_map 健檢（死引用）**：`pwsh -File .claude/skills/project-01-workflow/scripts/codemap-health.ps1`——掃各層 code_map 的路徑引用逐一驗存活（解析順序：本層→同行目錄→祖先層；只報告不改檔；exit 0/1/2）。gitignored 檔不進 worktree，一律從主 checkout 跑（或 `-RepoRoot` 指過去）。觸發：結構變動收尾順手跑、或使用者喊「code_map 健檢」。死引用 = 該層 code_map 漏更新——修 code_map 而非刪引用。

---

## 部署資訊

| 項目 | 值 |
|---|---|
| 使用者 / 主機 | `pi` / `raspberrypi.local`（SSH `pi@raspberrypi.local`） |
| 遠端路徑 | `/home/pi/Desktop/project_jiqiren`（絕對路徑，禁 `~`） |
| GitHub Repo | `https://github.com/leon13018/project_jiqiren.git` |

**同步**：`git push` 後 **Stop hook（`stop-sync-pi.ps1`）在本 turn 結束自動 sync Pi**（SSH 到 Pi `git pull`，首次則 clone；SSH 金鑰已設）。機制見 [standard-workflow.md](standard-workflow.md) §為何用 Stop hook。

**Pi 端執行環境**（已安裝清單見 `resources/requirements/raspberry_pi_setup.md`）：
- Python **3.11.9**（source build 在 `~/Python-3.11.9/`；系統內建 3.7 不足、edge-tts 強制依賴）。
- 雲端 TTS：edge-tts（pip）+ mpg123（apt）。
- **跑法**：`python3.11 -m myProgram`（推薦，透過 `__main__.py`）或 `python3.11 -m myProgram.main`。舊 `myProgram.myProgram` 已失效（檔名改 main.py）。
- **.gitignore 排除**：`.claude/settings.local.json` / `.claude/worktrees/` / `sync_pi.ps1` / `resources/presentation/` / `resources/userPrompt/`；其餘 `resources/*` 已 tracked。`CLAUDE.md` 在 root、tracked 並 push。

---

## Pi 環境陷阱

### 1. GLIBC / piwheels source build 陷阱
**事實**：Pi 4 跑 Debian Buster + GLIBC 2.28（EOL，系統 .so 偏舊）。piwheels（Pi 預設 pip index）為相容新發行版會 rebuild wheel 連結到新 GLIBC/SONAME → 在 Buster 上 ImportError，降版 wheel 也常救不了。

**症狀**：`ImportError: ...libc.so.6: version 'GLIBC_X.XX' not found`（wheel 對 GLIBC 太新）｜`ImportError: libXXX.so.N: cannot open shared object file`（link 到新 SONAME，Buster 只有舊）。

**修法（優先序）**：
- **首選 — 強制 source build 跳過 piwheels**：
  ```bash
  python3.11 -m pip uninstall -y <pkg>
  python3.11 -m pip install --no-binary :all: --index-url https://pypi.org/simple/ <pkg>
  ```
  （`--no-binary :all:` 拿 source、`--index-url pypi` 跳過 piwheels；編譯連結 Buster 現有 lib 自然相容。）
- 缺 C extension `*-dev`（編 Pillow 需 libjpeg-dev/libtiff5-dev）→ 先 `sudo apt install <list>-dev` 再 build。
- 不推薦升級系統 lib（Buster repo 無新版）。
- **已驗證可行**：`RPi.GPIO` source build ✅；`Pillow<10`（9.5.0）+ `libtiff5-dev` ✅；純 Python（pyserial/pigpio/smbus2）piwheels 版可直接用。
- **Python stdlib C extension 缺失（如 `_tkinter`）**是另一回事：`apt install tk-dev tcl-dev` → `cd ~/Python-3.11.9 && make clean && ./configure --enable-optimizations --prefix=/usr/local && make -j4 && sudo make altinstall`（Pi 4 約 20-40 分；既有 pip 套件不受影響）。

### 2. 使用者報「X 沒作用」→ 先對 git commit 再 debug
使用者實機報「X 沒按預期動」但你 trace code 覺得邏輯對時——**別急著挖 code**，先確認 Pi 端 commit 與本機 main 同步：
```bash
git log -1 --oneline main && ssh -o ConnectTimeout=5 pi@raspberrypi.local "cd /home/pi/Desktop/project_jiqiren && git log -1 --oneline"
```
兩邊 SHA 對齊才往下；不同先排查 sync。**Why**：邏輯明明對卻不動，常是 Pi 沒同步到新 commit；一條指令省下深挖成本。**也適用**「之前可以的 X 現在不行」→ 比對最近 commit 是否動到 X。
