# Python 3.11 vendor SDK 依賴補裝

**建立日期：** 2026-05-23
**對應提交：** 本檔自身（worktree-py311-vendor-deps）

---

## 背景

Python 3.11.9 為了 edge-tts 升級安裝；廠商 SDK（`/home/pi/TonyPi/HiwonderSDK/`）內部 import 的多個第三方套件目前**只裝在系統 Python 3.7**，3.11 全缺。

導致：
- `python3.11 myProgram.py` 在 import 階段 crash（從 `BusServoCmd.py` 找不到 `serial`）
- `python3 myProgram.py`（3.7）跑得起來，但 `edge_tts` require Python ≥ 3.8 → `tts.py` 內 `import edge_tts` 失敗 → `_ENABLED = False` → `speak()` 變成只 print 不播音

**結論：** 必須把廠商 SDK 用到的所有 pip 套件**一次性裝到 Python 3.11**，**之後一律用 `python3.11`，永遠不用 `python3` / `python`**。

---

## 安裝指令

> 全部用 `python3.11 -m pip install`（你自己編的 3.11.9，應該不會碰到 `externally-managed-environment` 保護）。
> 若 sudo 才裝得起來請加 sudo；否則 user-level 安裝即可。

### Step 0：暖身（升級 pip / setuptools / wheel）

```bash
python3.11 -m pip install --upgrade pip setuptools wheel
```

### Step 1：硬體 / 通訊核心（從 trace 已確認需要）

```bash
python3.11 -m pip install pyserial RPi.GPIO pigpio smbus2
```

| 套件 | 用途 |
|---|---|
| `pyserial` | 串口（總線舵機通訊）— trace 已 confirm 缺 |
| `RPi.GPIO` | GPIO 控制 |
| `pigpio` | 精準 PWM / 高速 GPIO（需配合 `pigpiod` 系統服務） |
| `smbus2` | I2C 通訊 |

### Step 2：影像 / 數值 / UI 工具

```bash
python3.11 -m pip install numpy Pillow qrcode opencv-python
```

| 套件 | 用途 |
|---|---|
| `numpy` | 數值運算（廠商影像處理常見依賴） |
| `Pillow` | 影像處理（`screen_display.py` 已 `from PIL import ImageTk`） |
| `qrcode` | QR Code 產生（`screen_display.py` 已用） |
| `opencv-python` | 電腦視覺（廠商範例已用 `import cv2`） |

> ⚠️ **`opencv-python` 若 pip 卡住或失敗**：
> 改用 apt（會裝給系統 Python 3.7 不是 3.11）→ 仍卡 → 先跳過，跑 myProgram 看真不真的會用到再回頭。

### Step 3：感測 / 周邊（廠商 TonyPi 常見）

```bash
python3.11 -m pip install pyzbar picamera2
```

| 套件 | 用途 |
|---|---|
| `pyzbar` | QR Code / barcode 解碼 |
| `picamera2` | Pi Camera 2 API（Bookworm 推薦） |

> ⚠️ `picamera`（v1）在 Bookworm 已不支援，被 `picamera2` 取代。若廠商 SDK 還用舊版 v1，import 才會發現：屆時試 `python3.11 -m pip install picamera`（多半找不到 wheel）。

### Step 4：可選 / 重型（裝失敗可跳）

```bash
python3.11 -m pip install mediapipe
```

| 套件 | 用途 / 注意事項 |
|---|---|
| `mediapipe` | 人體 / 手部姿態偵測。**Pi 上 pip install 可能很慢或失敗**（要對應 ARM wheel）。失敗 → 看廠商程式真用到再找專用 wheel；沒用到就跳 |

---

## Step 5：迭代驗證（重點）

每跑一輪都從 Pi **桌面終端**（不是 SSH）做：

```bash
cd /home/pi/Desktop/project_jiqiren/myProgram
python3.11 myProgram.py
```

預期分支：

| 結果 | 行動 |
|---|---|
| ✅ 跑起來 + 按 'y' **有聲音** | 全裝完了，跳到驗證段 |
| ❌ `ModuleNotFoundError: No module named 'XXX'` | `python3.11 -m pip install XXX` → 重跑。**把額外裝的套件名記下來回報給我** |
| ❌ `TclError: no display name and no $DISPLAY` | 你在 SSH 跑了，改桌面終端 |
| ⚠️ Import 過、有印 `[語音] xxx`、但無聲 | edge-tts call 出錯被 try/except 吞了。看終端有沒有 `[語音] TTS 失敗：xxx` 訊息，把訊息給我 |

---

## 驗證段（成功判定）

✅ **逐項確認都通過 = 成功：**

1. `python3.11 myProgram.py` 不再有任何 `ModuleNotFoundError`
2. 程式進入主迴圈，印出 `========================================` banner
3. `hawking_loop` 自動跑：終端有 `[語音] 來喔！...` **且**喇叭出聲
4. 按 `y` 進顧客模式：`[語音] 歡迎光臨！...` **且**喇叭出聲

✅ **完成後請回報：**
- 哪些套件**成功**裝上（pip 套件名、版本不必）— 我會更新 `resources/requirements/raspberry_pi_setup.md`「pip Python 套件」清單
- 哪些**額外**裝的（不在本檔列表內）— 我會補進該檔
- 聲音是否確認播出來

❌ **失敗 / 卡關不必勉強解決，貼錯誤訊息給我再討論。**

---

## 故障排除

**Q: `pip install` 報 `error: externally-managed-environment`**
A: Debian Bookworm 對 apt 裝的 python3 / python3.11 預設禁止 pip。你的 3.11.9 是 source build，**不該**碰到。若真的遇到 → 加 `--break-system-packages` flag，或建 venv（但這次先別）。

**Q: 某套件 pip 安裝編譯時間 > 10 分鐘**
A: 多半缺 ARM 預編譯 wheel 走 source build。先 `Ctrl+C` 跳過，跑 myProgram 看那套件真不真的會被 import 到，需要才回頭找專用 wheel。

**Q: `pigpio` 裝完 vendor SDK 還是壞**
A: `pigpio` Python 套件 ≠ `pigpiod` 系統 daemon。後者要：
```bash
sudo systemctl status pigpiod      # 看狀態
sudo systemctl start pigpiod       # 啟動
sudo systemctl enable pigpiod      # 開機自啟
```

**Q: 裝完一輪後又冒新的 `ModuleNotFoundError`**
A: 正常，廠商 SDK 內部 import 是逐個檔載入的，第一個 import 不到就 stop。**iteration 預期 2~5 次**才會把所有依賴找齊。把每次新冒的套件名記下來。
