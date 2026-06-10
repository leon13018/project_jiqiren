# 2026-06-11 — OOP 重構 W6 worker 實機驗證

- **建立日期**：2026-06-11
- **對應提交**：oop_w6 wave（`780ecb4` QueueWorker 基底 / `edcf5bc` TtsWorker・ActionWorker 繼承 / `6a8da7d` TerminalSim）
- **簡介**：W6 把 TTS / 動作兩個 worker 改為繼承 `QueueWorker` 基底、main.py 改 `TerminalSim` 類別。**ActionWorker 在 Windows 無測試**（vendor 耦合），TTS 真實播放時序也只能實機驗——需在 Pi 跑一輪完整流程確認行為與重構前一致。

## Step 1 — 確認同步

```bash
cd /home/pi/Desktop/project_jiqiren && git log -1 --oneline
```
SHA 應與 GitHub main 最新一致（Stop hook 已自動 sync；不一致先 `git pull`）。

## Step 2 — 跑一輪完整流程

```bash
python3.11 -m myProgram
```
1. L1 選 `1` 進叫賣 → 應聽到叫賣語音輪播、看到 **進場揮手動作**
2. 按 `c` 模擬偵測 → 進 L2，聽到「請問需要購買什麼東西嗎？」+ L2 進場動作
3. 說/打「紅茶 2」→ 加單，聽到轉場語音 + L3 動作
4. 說「結帳」→ confirm 報明細 → 答「1」→ 聽到結帳引導 + 指屏動作
5. L4 看到金額明細 + 倒數 `timeout = N` 每秒遞減 → 按 `s` 掃碼 → **付款鞠躬動作**
6. L5 致謝語音 + **送客揮手** + `wait = N` 3 秒倒數 → 自動回 L1 連續叫賣
7. 按 `q` `q` 退出

## Step 3 — 驗證點（與重構前行為對照）

| 項 | 預期 |
|---|---|
| TTS 播放 | 每句完整不截尾（句尾 ALSA drain 正常）；連續兩句間無異常長停頓 |
| 動作組 | 上述 5 個動作點全部照常觸發（**本輪唯一無 Windows 測試的部分**） |
| 倒數顯示 | `timeout = N` / `wait = N` 每秒整數遞減、不跳號 |
| 退出 | `q` `q` 後立即退出：mpg123 立停、終端不 hang、不需多按一鍵 |

## 故障排除

- **動作全部不動**：看啟動時 stderr 有無 `Exception in thread ActionWorker`（vendor import / runAction 失敗）——回報該段訊息。
- **TTS 不出聲**：看有無 `[語音] ⚠️ TTS 失敗` 訊息（synth / play 階段）或 `wait_idle 超過 max_wait` 警告。
- **退出 hang**：回報卡住前最後一行輸出。

## 驗證段

上述 Step 2 全程走完、Step 3 四項全符合 → 本輪 Pi 驗證通過。**請回報結果**（通過 / 哪一項異常 + 訊息），異常我來修。
