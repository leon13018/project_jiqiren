# STT 持久連線 hardening + prearm 首連線 — SDD spec

**日期：** 2026-06-19
**類型：** worker 併發 hardening + 延遲優化（`myProgram/stt.py` + `myProgram/main.py`）
**裁定：** 使用者 2026-06-19 選「安全極限」（A+B；opener-split / local 模型不做）。

## 1. 背景與動機

持久連線（`stt_persistent_connection` 2026-06-19）上線後，反思 worker 在 `proposals.md` 提出 3 條 **pending** 併發 freeze-risk，經評估全採納；另使用者要把連線延遲推到極限（prearm 首連線）。本 spec = **Part A（3 hardening）+ Part B（prearm）**。

**3 條反思（proposals.md，本 spec 落實後改 adopted）：**
- `receive-loop-outer-try-exit-persistent-conn`：`_receive_loop` try 包整個 while，**單則壞訊息**（json 異常）即令 receiver 退出 → `_ws=None` → 強迫重連，違背「整場一條連線」。
- `arm-lock-held-during-blocking-io`：`arm()` 持 `_lock` 期間做阻塞建線（可達數十秒），同鎖被 `disarm`/`shutdown`/receiver-finally 取用 → 建線逾時**全凍**。
- `disarm-finalize-blocked-after-join-timeout`：`disarm()` 在 `sender.join(timeout=1.0)` 後送 Finalize；若 sender 卡在 `ws.send`（持 `_send_lock`）→ disarm 的 `with _send_lock` **無限阻塞掛死**。

**Part B（prearm）動機**：持久連線後唯一殘留是**首輪建線 540ms**（Pi 實測）。在 `read_customer_input` 的 `tts.wait_idle()` **之前**非阻塞預連線 → 首輪握手藏進 L2 提示音播放（~3.7s）→ 連線延遲歸零。

## 2. 設計核心 + 行為規約

### Part A — 3 hardening 修復（`stt.py`）

**A1 `_receive_loop` 雙層 try**：外層只包 `ws.recv()`（連線層——recv 失敗=連線死→退出重連）；**內層**包單訊息處理（`json.loads`→`sink`，壞訊息→印「跳過異常訊息」後 `continue`，**連線層存活**）。`finally` 標記死亡不變。

**A2 連線移出 `_lock` + `_connect_lock`**：新增 `self._connect_lock`。`_ensure_connected()` 改為：
1. `with _lock:` 快查 `_ws is not None → return True`；
2. `with _connect_lock:`（序列化 prearm 背景 vs arm 主線程的建線）→ 內再 `with _lock:` 複查 `_ws`（等鎖期間別人已建好→復用）→ **鎖外**（`_lock` 已釋放）做 `_connect_with_retry()` 阻塞建線 → 成功後 `with _lock:` 寫 `_ws`/conn_stop/threads → start。
`arm()` 改為：第一個 `with _lock:` 只查 disabled/capturing/key；**鎖外**呼叫 `_ensure_connected()`；再 `with _lock:` spawn arecord+sender + 設 capturing。→ 建線全程不持 `_lock`，disarm/shutdown 不被凍。

**A3 disarm join 逾時跳過 Finalize**：`sender.join(timeout=1.0)` 後，僅 `not sender.is_alive()`（sender 已收，未卡在 send 持 `_send_lock`）才送 Finalize；逾時仍 alive → 跳過（連線多半已異常，送不送意義不大），避免搶 `_send_lock` 掛死 disarm。

### Part B — prearm 首連線（`stt.py` + `main.py`）

**`SttWorker.prearm()`**：非阻塞——快查 `_disabled / _capturing / not _api_key / _ws is not None` 任一成立即返（不起 thread）；否則起 daemon thread 跑 `_ensure_connected`（`_connect_lock` 保證與 arm 不重複建線）。

**module `prearm()`** → `_get_worker().prearm()`。

**`main.py` `read_customer_input`**：在 `tts.wait_idle()` **之前**呼叫 `stt.prearm()`（import 上移）。首輪：背景建線（540ms）overlap 提示音播放；第 2+ 輪：`_ws` 已連 → prearm no-op。`arm()` 之後若 prearm 仍在建線，arm 的 `_ensure_connected` 經 `_connect_lock` 等其完成→復用（不重連）。

### 行為不變式
- 每輪注入的顧客 utterance、辨識行為、對話流程**完全不變**；`arm`/`disarm`/`shutdown` 對外 signature 不變。
- A1：壞訊息只略過該則，正常 speech_final 照注入。
- A2：連線復用 / 重連 / 401 停用 / 失敗走鍵盤 行為全保留（只是建線不再持 `_lock`）。
- A3：正常情況（sender 已收）Finalize 照送；只有 sender 卡死才跳過。
- B：prearm 純加速，不改任何對外行為（純鍵盤 / 缺 key 模式 prearm no-op）。

## 3. 改檔範圍（高層；step 移 plan）

- `myProgram/stt.py`：`__init__` 加 `_connect_lock`；`_ensure_connected` 重構（鎖外建線 + double-check）；`arm` 重構（建線移出 `_lock`）；`_receive_loop` 雙層 try；`disarm` 加 `not sender.is_alive()` 守衛；新增 `prearm()` method + module `prearm()`。
- `myProgram/main.py`：`read_customer_input` 在 wait_idle 前加 `stt.prearm()`（import 上移）。
- `tests/stt/test_worker.py`：A1（壞訊息連線存活）、A3（sender 卡死跳 Finalize 不掛死）、B（prearm 背景連線 / 已連 no-op / 缺 key no-op）新測；既有連線測試（復用/重連/401/retry）續綠。
- `tests/stt/conftest.py`：按需擴充 `FakeWs`（可選 blocking-send 模擬 A3）。
- `tests/sales/test_main_read_callbacks.py`（或對應 main wire 測）：prearm 被呼叫的 wire 測（若既有測 read_customer_input 流程）。

## 4. Out of scope

- **opener-split**（結帳句固定開場白）、**prewarm-expansion**（log 證實近乎無剩、動態句不可預熱）：本輪不做。
- **local 模型**（Piper / whisper）：延遲已解、會 regress accuracy/音質，不做。
- **shutdown-during-connect zombie**：極罕見（剛好在首輪 540ms 建線瞬間退出），殘留 daemon thread 隨行程退出而死，接受不另加旗號。
- arecord 冷啟動（~140ms）、drain、endpointing、vendor、對話文案：不動。

## 5. 規範與參考

- 派 **sales-coder**（worker 併發重構）。動手前讀 skill `reference/myprogram-threading-paths.md`。
- 既有 reuse：`_connect_with_retry` / `_timing` / `_normalize_transcript` / `_keepalive_loop` / FakeWs / FakeAudioSource / wait_until。
- 反思出處：`proposals.md` 3 條 pending（落實後本 spec commit SHA 回填）。

## 6. 測試指令 + 預期

- `py -3.14 -m pytest tests/stt/ tests/sales/test_main_read_callbacks.py -q`：新測 + 既有續綠。
  - A1：armed 時 feed 一則非 JSON 壞訊息 → receiver 不退出（`worker._ws` 仍非 None）；隨後 feed 正常 speech_final → 仍注入。
  - A3：sender 卡死（blocking-send ws 或 blocking-read audio）→ disarm 在 ~1s 內返回（不掛死）、`_FINALIZE_MSG` **未**送出。
  - B：`prearm()` 未連 → 背景建線（`wait_until` _ws 非 None、ws_factory 1 次）；已連 → no-op（factory 仍 1 次）；缺 key → 不建線（factory 0 次）。
  - 既有 `test_connection_reused` / `test_dead_connection_reconnects` / `test_connect_*` / 控制訊息測 / 計時測：續綠（arm 重構後行為等價）。
- 全套 `py -3.14 -m pytest tests/ -q`（baseline 666，新增後上升）。
- Pi：`STT_TTS_TIMING=1` 跑多輪 → **第一輪也看不到「開麥連線」延遲感**（藏進提示音）；壞訊息 / 斷網重連 / 長對話穩定。

## 7. Commit 規範

- 分階段 commit（A1 / A2+arm 重構 / A3 / B），每階段 pytest 綠才下一步。
- git add 明列 `myProgram/stt.py myProgram/main.py tests/stt/...`（禁 `-A`）。
- message 末尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
read_customer_input ─► stt.prearm()（背景建線，首輪 overlap 提示音）─► tts.wait_idle()
   └► stt.arm()：_lock 查狀態 → 鎖外 _ensure_connected（_connect_lock 序列化、復用 prearm 連線）
       → _lock spawn arecord+sender + capturing=True
receiver：外層 try(recv) / 內層 try(單訊息) → 壞訊息略過、連線活；recv 死 → finally 標記重連
disarm：停收音層 → join(1.0) → 僅 sender 已收才送 Finalize（卡死則跳過）
```

## 風險 / Pi 驗證點（收尾 pineedtodo）
- prearm 首輪是否真的藏掉 540ms（第一輪開頭體感即時）。
- A1：實際 Deepgram 壞訊息罕見，主要防禦性；確認正常流程無回歸。
- A3：sender 卡死屬極端網路情境，Pi 難主動觸發；確認正常 disarm/結帳收尾無回歸。
