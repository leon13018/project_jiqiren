# Pi 已安裝清單

> 本檔記錄 Pi 上**實際完成安裝並經使用者回報確認**的項目。
>
> **更新機制：** CLAUDE.md「🚦 Pi 端操作觸發條件」1a / 3a 觸發 → 使用者完成 Pi 操作後 → 使用者主動跟主 agent 回報成功項目 → 主 agent 更新本檔。
>
> **不寫入：** 失敗 / 未回報 / 主 agent 自行推測的項目，絕不寫入。
>
> **格式：** 純項目名稱，一行一個。版本資訊 / 對應 commit / 日期 → 查 git log。

---

## apt 系統套件

- mpg123
- tk-dev
- tcl-dev
- libjpeg-dev
- zlib1g-dev
- libfreetype6-dev
- liblcms2-dev
- libtiff5-dev
- libwebp-dev

## pip Python 套件（Python 3.11）

- edge-tts
- pyserial
- RPi.GPIO（source build，跳過 piwheels）
- pigpio
- smbus2
- numpy
- Pillow 9.5.0（source build with libtiff5-dev，連結系統 libtiff.so.5）
- qrcode
- opencv-python
- wheel
- pypinyin
- websockets（STT Deepgram 串流 client；純 Python，無 piwheels/GLIBC 風險）
- fastapi（webui Phase 1 顯示鏡像後端；使用者 2026-06-18 確認裝成功）
- uvicorn（**純 uvicorn，非 `uvicorn[standard]`**——避 uvloop/httptools C 擴充 Pi wheel 風險；webui Phase 1 ASGI server）

## raspi-config 啟用項

(待使用者回報)

## systemd / 自啟動

(待使用者回報)

## 其他手動設定（音量 / 權限 / 設定檔 / 服務啟動等）

- Python 3.11.9 source build（edge-tts 依賴，原 Pi OS 內建版本不足；2026-05-23 加裝 tk-dev / tcl-dev 後 rebuild，使 `_tkinter` 編進 stdlib）
- DEEPGRAM_API_KEY 環境變數（STT Deepgram 串流金鑰，寫入 `~/.bashrc`；STT Phase 1 已 Pi 實測通過）
- STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10 環境變數（ReSpeaker 開麥裝置，寫入 `~/.bashrc`；plughw 降混成單聲道，未設則 arecord `-c 1` 撞「Channels count non available」。2026-06-19 使用者確認設妥、Channels 錯誤消失）
