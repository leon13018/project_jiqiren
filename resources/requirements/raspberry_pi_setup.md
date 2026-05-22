# Raspberry Pi 4 部署依賴清單

> 本文檔記錄專案在 Raspberry Pi 4 上需要安裝的所有依賴、驅動設定，以及任何需要在 Pi 終端機執行的指令。
> Claude Code 不會在 Windows 本機執行任何安裝指令，所有 Pi 端操作都會更新到本文檔，由開發者手動執行。

---

## 0. 部署環境資訊

| 項目 | 內容 |
|---|---|
| 目標裝置 | Raspberry Pi 4 |
| 遠端使用者 | `pi` |
| 遠端主機 | `raspberrypi.local` |
| 遠端專案路徑 | `~/Desktop/project_jiqiren` |
| GitHub Repo | `https://github.com/leon13018/project_jiqiren.git` |
| 同步腳本 | Windows 端執行 `./sync_pi.ps1`（SSH 自動 pull / clone） |

---

## 1. 系統層依賴（apt）

在 Pi 終端機執行：

```bash
sudo apt update
sudo apt upgrade -y
```

| 套件 | 安裝指令 | 用途 |
|---|---|---|
| `python3` | 通常已預裝 | 主程式執行環境 |
| `python3-pip` | `sudo apt install -y python3-pip` | Python 套件管理 |
| `python3-tk` | `sudo apt install -y python3-tk` | Tkinter GUI（POS 螢幕） |
| `python3-pil` `python3-pil.imagetk` | `sudo apt install -y python3-pil python3-pil.imagetk` | Tkinter 中顯示 QR Code 圖片 |
| `git` | `sudo apt install -y git` | 程式碼同步（通常預裝） |

---

## 2. Python 套件（pip）

建議建立虛擬環境後安裝（或視專案需要直接系統安裝）：

```bash
# 進入專案資料夾
cd ~/Desktop/project_jiqiren

# （可選）建立虛擬環境
python3 -m venv venv
source venv/bin/activate
```

| 套件 | 安裝指令 | 用途 |
|---|---|---|
| `qrcode` | `pip3 install qrcode[pil]` | 動態生成付款 QR Code |
| `Pillow` | `pip3 install Pillow` | 圖片處理（搭配 Tkinter ImageTk） |

> 廠商提供的 `Board.py` / `ActionGroupControl.py` SDK 應已隨 Pi 系統映像預裝；若缺失需另行向廠商取得。

---

## 3. 硬體 / 驅動設定

| 項目 | 設定指令 | 用途 |
|---|---|---|
| 啟用 I2C | `sudo raspi-config` → Interface Options → I2C → Enable | 頭部舵機通訊 |
| 啟用 Camera | `sudo raspi-config` → Interface Options → Camera → Enable | 後續 OpenCV 人形偵測（尚未導入） |
| 音訊輸出測試 | `aplay /usr/share/sounds/alsa/Front_Center.wav` | 後續 Piper TTS 語音輸出（尚未導入） |

---

## 4. 後續模組（尚未導入，預留紀錄）

當下列模組要導入時，會在此補充安裝步驟：

### 4.1 語音辨識（Whisper）— ⏳ 未導入
- 目前替代方案：鍵盤輸入模擬
- 預期套件：`openai-whisper` 或 `faster-whisper`

### 4.2 語音合成（Piper TTS）— ⏳ 未導入
- 目前替代方案：終端文字輸出 `[語音]`
- 預期套件：`piper-tts` + 語音模型檔

### 4.3 人形偵測（OpenCV）— ⏳ 未導入
- 目前替代方案：鍵盤指令 `y` 模擬
- 預期套件：`opencv-python`、可能搭配 `mediapipe`

---

## 5. 其他終端操作 / 一次性設定

> 若有任何需要在 Pi 上執行的一次性指令（檔案權限、systemd 服務、自啟動腳本等），條列於此。

| 操作 | 指令 | 說明 |
|---|---|---|
| _（暫無）_ | | |

---

## 更新紀錄

| 日期 | 更新內容 |
|---|---|
| 2026-05-21 | 建立初版骨架；列出 PDF 報告中已使用的依賴（tkinter / qrcode / Pillow）與後續預計導入模組 |

---

## 語音輸出（TTS）— edge-tts

### Python 套件
```bash
pip install edge-tts
```

### 系統套件（MP3 播放器）
```bash
sudo apt install -y mpg123
```

### 音訊輸出裝置設定（一次性，demo 前務必確認）
```bash
sudo raspi-config
# → System Options → Audio → 選擇輸出裝置（HDMI / 3.5mm jack）
```
然後調整音量：
```bash
alsamixer
# 上下方向鍵調 PCM 音量，M 切換靜音，Esc 離開
```

### 測試是否能發聲
```bash
python3 -c "import edge_tts, asyncio; asyncio.run(edge_tts.Communicate('測試一下', 'zh-TW-HsiaoChenNeural').save('/tmp/t.mp3')); import subprocess; subprocess.run(['mpg123','-q','/tmp/t.mp3'])"
```
聽到台灣女聲說「測試一下」即成功。
