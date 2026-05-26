# Pi 端待辦 — S2 同步 TTS 驗證

**建立日期：** 2026-05-27
**對應提交：** 本輪 S2 TTS commit（含 `myProgram/tts.py` + `myProgram/main.py` speak callback 串接 + 本檔 + `projectStructure.md`）

本輪程式碼層接入 S2 同步 TTS（[[incremental-rebuild]] 第 2 步）— `speak()` 阻塞至播完才 return。Pi 端 `edge-tts` + `mpg123` 自 2026-05-22 起已安裝（見 `resources/requirements/raspberry_pi_setup.md`），故本檔重點不是「裝套件」而是 **驗證 + 補音訊設定 + 跑新主程式聽看看**。

---

## Step 0：確認 git pull 已同步

本機 push 後 PostToolUse hook 會自動跑 `sync_pi.ps1`（SSH 過去 `git pull`）。先在 Pi 端確認：

```bash
cd /home/pi/Desktop/project_jiqiren
git log -1 --oneline
```

應看到本輪 S2 commit 標題（含 `feat(tts)` 或 `S2` 字樣 + Co-Authored-By Claude）。若沒看到 → hook sync 失敗，使用者本機手動跑 `& sync_pi.ps1`。

---

## Step 1：確認套件仍可用（防環境 drift）

```bash
which mpg123
python3.11 -c "import edge_tts; print(edge_tts.__version__)"
```

- `which mpg123` 應印 `/usr/bin/mpg123`
- `python3.11 -c ...` 應印版本號不報錯

若任一失敗：
- mpg123 missing → `sudo apt install -y mpg123`
- edge_tts ImportError → `python3.11 -m pip install edge-tts`（**必須用 3.11，不要全域 python3** — 詳見 `resources/pineedtodo/2026-05-23_python311_vendor_deps.md`）

裝完跟主 agent 回報，會更新 `raspberry_pi_setup.md`。

---

## Step 2：設定音訊輸出（首次 / 換喇叭時）

`raspberry_pi_setup.md` 的「raspi-config 啟用項」尚未回報 → 若還沒設過 / 換新喇叭 / 之前已設可跳過。

```bash
sudo raspi-config
```

選 → `System Options` → `Audio` → 依實際接的硬體選：
- **HDMI** — 接 HDMI 螢幕 / HDMI 喇叭
- **Headphones (3.5mm)** — 3.5mm 音源線喇叭
- **USB Audio** — USB 喇叭 / USB 音效卡（若有）

按 `Finish` 離開。

---

## Step 3：調音量（如果聽不到 / 太大聲）

```bash
alsamixer
```

操作鍵：
- ↑↓：調 PCM 音量（建議 70–85%）
- ←→：切換 channel
- `M`：靜音切換（`MM` = 靜音、`OO` = 解除）
- F6：切換音效卡（如有外接 USB 卡）
- `Esc`：離開存檔

存檔生效後可選擇性 `sudo alsactl store` 持久化。

---

## Step 4：smoke test — 單句 TTS

```bash
python3.11 -c "from myProgram import tts; tts.speak('S 二測試一二三')"
```

預期：
1. 終端印 `[語音] S 二測試一二三`
2. **約 1–2 秒後** 從喇叭聽到台灣女聲說「S 二測試一二三」
3. Python 阻塞約 2–3 秒（合成 + 播放）後 return，prompt 回來

### 故障排除

| 症狀 | 可能原因 | 排查 |
|---|---|---|
| `ModuleNotFoundError: edge_tts` | Step 1 失敗 / 裝到別的 Python | 確認用 `python3.11`、`python3.11 -m pip show edge-tts` |
| `FileNotFoundError ... mpg123` | mpg123 binary 不存在 | `sudo apt install -y mpg123` |
| `[語音] ⚠️ TTS 失敗（階段=synth）` + `NoAudioReceived` / `ClientError` | edge-tts 連不到 Microsoft 雲端 | `ping 8.8.8.8` 確認 Pi 有網路；`curl -I https://speech.platform.bing.com` |
| `[語音] ⚠️ TTS 失敗（階段=play）` + `CalledProcessError returncode=N` | mpg123 退出非 0（檔案損毀 / 音訊裝置忙） | 重跑一次；`speaker-test -t wav -c 2 -l 1` 試系統內建測試聲 |
| 印 `[語音]` 但沒聲音 | Step 2 / 3 設定錯 / 喇叭未連 | 回 Step 2、Step 3 確認 |
| Python 立即 return 但沒聲音 | mpg123 fire-and-forget（不該發生 — 本次用 `subprocess.run` 同步阻塞）| 截錯誤訊息回報，疑似 code bug |

---

## Step 5：跑主程式聽看看

```bash
cd /home/pi/Desktop/project_jiqiren
python3.11 -m myProgram
```

預期：
1. 印操作小抄（L1 商家層 1/2/3/q + L2-L5 顧客層）
2. **直接從喇叭聽到** L1 主選單朗讀（之前 S1 stub 只 print 不發聲）
3. 按 `1` 進叫賣 → 聽到「來喔！冰紅茶 27 元、刮刮樂 180 元，全場九折，走過路過不要錯過！」
4. 按 `c` 模擬偵測顧客 → 聽到 L2 ENTRY「歡迎光臨！冰紅茶 27 元、刮刮樂 180 元，全場九折。請問要什麼？」
5. 輸入「冰紅茶 一杯」 → 聽到加單回應 + L3 詢問
6. 按 `q` 或 Ctrl+C 退出

**注意對話節奏：S2 是同步阻塞 TTS — speak() 必須等到一段語音播完才會繼續到下個 read（顧客 timeout 從 speak 結束開始算）**。對比 S1 stub 是瞬間 print，S2 會明顯感覺到「機器人講話 → 等顧客講」的對話節奏。這是 S2 正常行為，不是 lag。

---

## 完成後

跑通 Step 4 + Step 5 即代表 S2 接入成功。請跟主 agent 回報：

1. **Step 1 套件確認狀況**（mpg123 / edge_tts 版本 — 若有變動會更新 `raspberry_pi_setup.md`）
2. **Step 2 raspi-config Audio 選了哪個出口**（HDMI / 3.5mm / USB Audio — 主 agent 會補進「raspi-config 啟用項」段）
3. **Step 3 alsamixer 設了幾 %**（若有調 — 主 agent 會補進「其他手動設定」段）
4. **Step 4 + Step 5 是否聽到聲音**（成功即可繼續下個 S3 階段；失敗截錯誤訊息回報）

任一步卡住把錯誤訊息貼給主 agent 協助診斷。**S3 同步動作**（廠商 `Act.runAction()` 阻塞動作）會在 S2 通過後才開工。
