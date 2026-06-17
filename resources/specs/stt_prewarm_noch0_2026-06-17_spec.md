# STT prewarm（不加 ch0）— v2 式來源端閘預熱、保留 Phase 1 `-c 1` mono spec

> 2026-06-17 定案。基線 = Phase 1（`734781e`：`arecord -c 1` mono、`wait_idle` 播完才 `arm`、辨識已 Pi 實證正常）。在 Phase 1 上**只加回 v2 式 prewarm**（預連 Deepgram ws + KeepAlive 維持、播放期不開麥），**不加 ch0**（音源維持 `-c 1` mono 降混）。目的：把 ws 握手延遲藏進 prompt 播放期、不犧牲辨識準確度。

## 1. 背景與動機

Phase 1 流程：`wait_idle`（等 TTS 播完）→ `arm`（**才連 ws + 開 arecord + 送音訊**）。問題：Deepgram ws 握手（Pi 連外網 ~0.2–0.5s）整段擠在「播完之後」→ 顧客感覺「播完不能馬上講」。

v2/v3 曾試 turn-taking 但**連同 ch0 一起進**，Pi 實測辨識變不准 → 全 revert（見 changelog 里程碑 6）。使用者證實：**ch0 處理後聲道是準確度元凶**，prewarm 機制本身（v2 來源端閘）無回授。

本案（使用者構想，2026-06-17）：**只取 v2 的 prewarm、丟掉 ch0**。`read_customer_input` 進場先 `prewarm`（在 prompt 播放期背景連 ws + 週期送 KeepAlive 維持連線、**完全不開麥不送音訊**）；`wait_idle` 播完後 `arm` 才**開 arecord（`-c 1` mono）+ 送顧客音訊**。ws 握手已於播放期完成 → arm 後省掉握手延遲；arecord 仍播完才開、從乾淨狀態錄 → **零積壓、音質同 Phase 1**。

**安全要點**：prewarm 期只送 KeepAlive text frame、**絕不送任何音訊**（arecord 根本沒開）→ 機器人聲從沒進 Deepgram → 無自我回授（v2 已 Pi 實證）。非 v3「邊播邊錄送靜音」（那有積壓風險）。

> 仍剩的延遲：endpointing(300ms)+轉錄——**結構性、本案不處理**（要動是另一題：調 Deepgram 參數）。本案只省 ws 握手。

## 2. 設計核心 + 行為規約

**單一增量**：把 Phase 1 的 tuple-session、arm-做全部，改為 v2 式 dict-session + prewarm/arm 兩段。**音源工廠不動**（`-c 1`、`_ArecordSource.read = stdout.read(n)`、無 `_extract_ch0`/`_CHANNELS`）。

- `__init__`：加 `keepalive_interval=5.0` 參數；`_session` tuple→dict（`stop/ws/receiver/keepalive/sending/audio/sender`）。
- `_open_ws()`（新）：caller 持 lock。連 ws + 起 receiver + 起 keepalive thread（**不開 arecord、不送音訊**）。缺 key→停用、連線失敗→放棄。回傳就緒與否。冪等（已有 session 直接回 True）。
- `prewarm()`（新）：`with lock: _open_ws()`。
- `arm()`（改）：`with lock:` 確保連線（無 session 則 `_open_ws`）→ 已有 sender 則 no-op（冪等）→ `sending.set()`（停 KeepAlive、音訊接手維持）→ 開 arecord + 起 sender。
- `_keepalive_loop(ws, stop, sending)`（新）：`while not stop.wait(interval): if not sending.is_set(): ws.send(KeepAlive JSON)`。stop / ws 關即止。
- `_send_loop(ws, audio, stop)`：**不動**（送真實 chunk）。
- `_receive_loop` / `_connect_with_retry` / `_is_auth_error` / 音源類與工廠：**不動**。
- `disarm()`（改）：dict 版，close audio（若有）+ ws，join `receiver/keepalive/sender`（各自若非 None）。
- 模組層加 `prewarm()`；`arm/disarm/shutdown` 不動。
- `main.py read_customer_input`：在 `wait_idle()` **之前**加 `stt.prewarm()`（播放期連線）。

| 場景 | 行為 |
|---|---|
| prewarm（prompt 播放中） | 連 ws + KeepAlive 維持；**arecord 未開、零音訊送出** → Deepgram 無轉錄 |
| arm（播完，wait_idle 後） | 停 KeepAlive → 開 arecord（`-c 1`）+ 送真實音訊；ws 已熱 → 省握手 |
| 缺 key / 連線失敗 | prewarm/arm graceful no-op（純鍵盤照常；缺 key 印一次警告後停用） |
| disarm | stop + close audio(若有)+ws + join 三 thread；冪等 |
| 未 prewarm 直接 arm | `arm` 內 `_open_ws` 即連即送（向後相容，既有測試不破） |
| 自我回授 | prewarm 期不送音訊 → 機器人聲不進 Deepgram（v2 已證） |

## 3. 改檔範圍

| 檔 | 改動 | 行數估 |
|---|---|---|
| `myProgram/stt.py` | `__init__`（+keepalive_interval、dict session）、新增 `_open_ws`/`prewarm`/`_keepalive_loop`、`arm` 改（兩段）、`disarm` 改（dict+三 join）、模組層 `prewarm` | ~55（淨增） |
| `myProgram/main.py` | `read_customer_input`：`wait_idle` 前加 `stt.prewarm()`（移 import + 註解） | ~5 |
| `tests/stt/test_worker.py` | 加 3 prewarm 測試（KeepAlive-no-audio / arm-after-prewarm-sends / 重用連線）+ 模組 `prewarm` delegate | ~45 |
| `tests/stt/test_main_wireup.py` | `wired` fixture 加 `prewarm` stub；既有 ordering 測試加 `prewarm < wait_idle` 斷言 | ~6 |

## 4. Out of scope

ch0 / `_extract_ch0` / `-c 6`（音源維持 `-c 1`）｜v3 邊播邊錄送靜音（積壓風險，不做）｜endpointing / Deepgram 參數調校｜AEC / 真 barge-in｜跨輪共用單一連線（維持每輪 prewarm→arm→disarm）｜`sales/` / `vendor/`。

## 5. 規範與參考

- 派 **sales-coder**；預載 karpathy。
- 必讀：`myprogram-threading-paths.md`（daemon thread + Event；sender/receiver/keepalive join；不用手動 Lock/Condition）。
- **機制參考**：v2 commit `d8c8d77`（KeepAlive prewarm 的證實實作；本案＝該機制 + Phase 1 `-c 1` 音源，不含 ch0）。
- 既有 reuse：`tests/stt/conftest.py`（`FakeAudioSource`/`FakeWs`/`wait_until`；`FakeWs.sent` 收所有送出 frame，KeepAlive 為 JSON text）。
- KeepAlive frame = `json.dumps({"type": "KeepAlive"})`（Deepgram 維持連線官方訊息）。
- **Pi 端**：無新依賴。裝置須 `plughw:CARD=ArrayUAC10`（`-c 1` 降混；`hw:` 固定 6ch 會失敗）——已記於 Phase-1 reverify pineedtodo，本案沿用。

## 6. 測試指令 + 預期

```
python -m pytest tests/stt/ tests/sales/
```
預期：sales 592 + stt 33（29 基線 + 4 新 prewarm 測試）= **625 全綠**。Windows 全 fake。

## 7. Commit 規範

- commit 1（code）：`feat(stt): v2 式 prewarm 預熱連線（保留 -c 1 mono、不加 ch0）`；`git add myProgram/stt.py myProgram/main.py tests/stt/test_worker.py tests/stt/test_main_wireup.py`。
- commit 2（docs，收尾）：roadmap/changelog/pineedtodo。
- worktree 首 commit = 本 spec + plan。

## 8. 流程鳥瞰

```
[approval] → commit spec/plan → sales-coder（prewarm 實作）→ Iron Law（pytest+branch）
          → spec-reviewer → code-quality → 收尾：roadmap/changelog + pineedtodo（重測跟手度）
          → ExitWorktree → ff-merge → push → Pi sync
          → Pi 實測（驗：辨識仍正常 + 播完到能講有無變快）
```
