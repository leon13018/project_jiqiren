# STT 暖機 arecord（消除開麥裁切）— 來源端閘送靜音、保留 -c 1 降混 spec

> 2026-06-17。基線 = main `ead8a13`（v2 式 keepalive prewarm + `-c 1` plughw 降混）。Pi 實測根因:**arecord 在 `arm()`（語音播完）才 spawn,USB 裝置開啟 + 首音框 ~200–400ms → 顧客一播完就開口時,話的開頭被裁掉**（「刮刮樂」掉「刮」→ Deepgram 聽成「25/八二五張」）。修法:arecord 提前到 `prewarm` 暖機就錄、暖機期送靜音、`arm` 翻旗號即切真實 → 開麥零裁切。音源維持 `-c 1` 降混（不碰 ch0）。

## 1. 背景與動機

現行 v2 式:`prewarm` 只連 ws + KeepAlive（**arecord 沒開**）;`arm` 才 spawn arecord + 送音訊。`arm` 緊跟 `wait_idle`（語音播完）,但 arecord USB 裝置冷啟動需 ~200–400ms,**這段顧客若已開口就被裁掉** → 辨識難詞掉頭被誤判（非聲道、非降混問題,是「開麥沒暖好」）。

修法（使用者最早的 v3 構想,當時連帶 ch0 才辨識爛、ch0 已剔除;本案只取「暖 arecord」對的部分接上降混）:`prewarm` 就起 arecord 背景錄音、sender 送**等長靜音**（機器人聲收進但不送 Deepgram → 無回授、靜音同時維持連線取代 KeepAlive）;`arm` 翻 `live` 旗號 → sender 改送真實。arecord 早暖好且即時抽乾（無積壓）→ **arm 後第一個真實音框就是顧客開口的起點,零裁切**。

**低延遲 / 高效能要點**:sender 在 mute 期以即時節奏 read 一框（~100ms）→ 送靜音,與 arecord 產出鎖步,pipe 維持淺（~1 框）→ arm 當下無積壓、切換即時。靜音串流 32kbps、arecord 一支 subprocess,開銷可忽略。

**安全（v1 栽過）**:mute = 來源端送靜音、**絕不送機器人真實聲**;`arm` 在 `wait_idle`（播完 + 0.3s ALSA drain）之後,緩衝裡已是 post-機器人 乾淨音。

## 2. 設計核心 + 行為規約

**單一增量**:把 prewarm 機制從 keepalive-based 改 silence-based（arecord 提前、去 keepalive）。**音源工廠完全不動**（`-c 1` plughw 降混、`_ArecordSource.read = stdout.read(n)`、無 ch0/抽軌）。

- `__init__`:**移除** `keepalive_interval`;session dict 改 `stop/ws/receiver/audio/sender/live`。
- `_start_session(live_initial)`（取代 `_open_ws`）:連 ws + 起 receiver + **起 arecord + sender**;起 sender 前依 `live_initial` 定 `live`（race-safe）。回傳就緒與否;已有 session 直接 True。
- `prewarm()`:`_start_session(live_initial=False)`（sender 進 mute 送靜音、arecord 開始暖機錄音）。冪等。
- `arm()`:無 session → `_start_session(live_initial=True)`（未 prewarm 即起即送、向後相容）;已 prewarm → `session["live"].set()`（解 mute）。冪等。
- `_send_loop(ws, audio, stop, live)`:每框 `ws.send(chunk if live.is_set() else b"\x00"*len(chunk))`。
- **移除** `_keepalive_loop`（靜音維持連線）。
- `disarm()`:dict 版,close audio + join receiver/sender（無 keepalive）。
- `_receive_loop` / `_connect_with_retry` / 音源類與工廠 / `main.py`:**不動**。

| 場景 | 行為 |
|---|---|
| prewarm（播放中） | arecord 暖機錄音;sender 讀真實聲但**送等長靜音** → Deepgram 收靜音、無轉錄、無回授 |
| arm（播完 post-drain） | `live` set → sender 改送真實;arecord 已暖 + 即時抽乾 → **零裁切、零積壓** |
| 連線維持 | 靜音串流維持（無需 KeepAlive） |
| 缺 key / 連線失敗 | prewarm/arm graceful no-op（純鍵盤照常） |
| disarm | stop + close audio + ws + join receiver/sender;冪等 |
| 未 prewarm 直接 arm | `_start_session(live_initial=True)`:即起即送（向後相容、既有測試不破） |

## 3. 改檔範圍

| 檔 | 改動 | 行數估 |
|---|---|---|
| `myProgram/stt.py` | `__init__`（去 keepalive_interval、session dict）、`_open_ws`→`_start_session(live_initial)`（+arecord+sender）、`prewarm`、`arm`（解 mute）、`_send_loop`（+live 靜音分支）、`disarm`（去 keepalive join）;**刪 `_keepalive_loop`**。**音源工廠不動** | ~45（淨減） |
| `tests/stt/test_worker.py` | 更新 prewarm 測試:keepalive 語意 → 靜音語意（prewarm 暖 arecord 送靜音 / arm 解 mute 送真實）;加 `_RepeatSource` | ~25 |

`myProgram/main.py` / `tests/stt/test_main_wireup.py`:**不動**（wiring 同前:prewarm→wait_idle→arm）。

## 4. Out of scope

ch0 / 抽單軌（已剔除,音源維持 `-c 1` 降混）｜endpointing / Deepgram 參數 / keyterm（難詞若仍偶誤辨另案）｜ALSA drain 縮減｜AEC / barge-in｜`sales/` / `vendor/`。

## 5. 規範與參考

- 派 sales-coder;預載 karpathy。
- 必讀:`myprogram-threading-paths.md`（daemon thread + Event;sender/receiver join;`live.set()` 在 `sender.start()` 前 race-safe）。
- **機制參考**:reverted 的 v3 commit `ea0bd57`（silence-based prewarm 證實實作;本案＝該機制 + `-c 1` 降混音源,不含 ch0）。
- 既有 reuse:`tests/stt/conftest.py`（`FakeWs`/`wait_until`/`_results`）;測 mute 需持續供 chunk 的音源（inline `_RepeatSource`,`FakeAudioSource` 耗盡即 EOF 不適用）。靜音 = `b"\x00" * len(chunk)`。
- **Pi 端**:無新操作。裝置維持 `STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10`（`-c 1` 降混,同上輪）。無新依賴。

## 6. 測試指令 + 預期

```
python -m pytest tests/stt/ tests/sales/
```
預期:sales 592 + stt 全綠（keepalive 測試改靜音測試;既有 arm/disarm/idempotent/retry/401/sender 直送 不破）。Windows 全 fake。

## 7. Commit 規範

- commit 1（code）:`feat(stt): 暖機 arecord 送靜音、arm 即切真實（消開麥裁切；保留 -c 1 降混）`;`git add myProgram/stt.py tests/stt/test_worker.py`。
- commit 2（docs,收尾）:roadmap/changelog/pineedtodo。
- worktree 首 commit = 本 spec + plan。

## 8. 流程鳥瞰

```
[approval] → commit spec/plan → sales-coder → Iron Law（pytest+branch+grep 無 keepalive）
          → spec-reviewer → code-quality → 收尾:roadmap/changelog + pineedtodo
          → ExitWorktree → ff-merge → push → Pi sync
          → Pi 實測:語音一播完馬上講「刮刮樂五張」,驗開頭不再被裁、辨識正確 + 無回授
```
