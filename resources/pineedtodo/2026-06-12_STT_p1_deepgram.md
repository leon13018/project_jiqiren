# STT Phase 1 — Deepgram 串流語音辨識 Pi 端設定

- **建立日期**：2026-06-12
- **對應提交**：`0af68cd — feat(main): read_customer_input 佈線 STT arm/disarm 與 shutdown 鏈`（stt_p1 實作 HEAD）
- **簡介**：顧客對話層（L2–L4）TTS 播完後自動開麥，講話經 Deepgram 轉繁體文字進對話流程；未完成下列設定時程式自動退回純鍵盤模式（不影響既有 demo）。

## 前置（一次性，在任何電腦上做即可）

註冊 Deepgram 帳號取得 API key：<https://console.deepgram.com> 註冊（免綁卡）→ 建立 API key 並複製。註冊送 $200 額度，本專題用量（≤2 小時音訊）用不完。

## Step 1 — 接上 ReSpeaker Mic Array V2

microUSB 線接 Pi 任一 USB 孔。確認系統看得到：

```bash
arecord -l
```

預期輸出含 `ReSpeaker 4 Mic Array` 一列（記下 card 編號，如 `card 1`）。

## Step 2 — 安裝 websockets（Python 3.11）

```bash
python3.11 -m pip install websockets
```

純 Python 套件，無 piwheels / GLIBC 風險。

## Step 3 — 設定環境變數

```bash
echo 'export DEEPGRAM_API_KEY="<貼上你的 key>"' >> ~/.bashrc
source ~/.bashrc
```

（可選）若 ReSpeaker 不是預設錄音裝置，依 Step 1 的 card 編號加：

```bash
echo 'export STT_ARECORD_DEVICE="plughw:<card編號>,0"' >> ~/.bashrc
source ~/.bashrc
```

## Step 4 — 錄音煙霧測試（不經程式，先驗硬體鏈）

```bash
arecord -D "${STT_ARECORD_DEVICE:-default}" -f S16_LE -r 16000 -c 1 -d 5 /home/pi/stt_test.wav
aplay /home/pi/stt_test.wav
```

對著麥克風講 5 秒，回放應清楚聽到自己的聲音。

## 驗證段（置尾）

```bash
cd /home/pi/Desktop/project_jiqiren && python3.11 -m myProgram
```

進顧客對話層（按 `c` 模擬偵測顧客）後**用講的**測 10 句點餐短句（如「我要紅茶兩杯」「結帳」「不用了」）：

- **預期**：終端印 `[語音辨識] <繁體文字>`、機器人正確回應 ≥8/10 句；講完到回應體感 <1 秒；文字為繁體（出現簡體請回報）。
- **故障排除**：
  | 症狀 | 排查 |
  |---|---|
  | 啟動印「未設定 DEEPGRAM_API_KEY」 | Step 3 沒生效——`echo $DEEPGRAM_API_KEY` 檢查；注意要在跑程式的同一個 shell |
  | 印「API key 無效（HTTP 401）」 | key 貼錯 / 被撤銷，回 console.deepgram.com 重建 |
  | 印「連線失敗」 | 網路問題：`ping api.deepgram.com`；重試仍敗請回報 |
  | 連線時 HTTP 400 | language 代碼不被接受——回報我，我改 `zh-Hant` 重推（spec §2.3 已預留） |
  | `arecord` 無聲 / 無裝置 | USB 重插、`arecord -l` 重查 card 編號、確認 STT_ARECORD_DEVICE |

完成後請回報哪些項**成功**（websockets 安裝 / key 設定 / ReSpeaker 錄音 / 10 句驗收結果），我更新 `resources/requirements/raspberry_pi_setup.md`。失敗或未完成不必報。
