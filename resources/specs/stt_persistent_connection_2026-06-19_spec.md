# STT 整場共用一條 Deepgram 連線（持久連線 + KeepAlive）— SDD spec

**日期：** 2026-06-19
**類型：** worker 重構（`myProgram/stt.py` `SttWorker` 生命週期）— 延遲優化
**裁定：** 使用者 2026-06-19 選「整場共用一條連線」（對比 prearm，明知較複雜仍選；prearm 留作 fallback）。

## 1. 背景與動機

Pi 實測（`STT_TTS_TIMING=1`，2026-06-19）拆解「語音播完→真的在錄音」的空檔：

| 段 | 實測 | 佔比 |
|---|---|---|
| **開麥連線**（Deepgram ws 握手，arm 同步阻塞、mic 還沒開） | ~**580ms**（465–675） | **~80%** |
| 裝置冷啟動（arecord 首框） | ~**140ms**（0.13–0.15s） | ~20% |

使用者回報「五張刮刮樂…的『五張』沒錄到」——開頭 ~0.7s 掉在這空檔。**元凶是每輪重連 Deepgram 的 580ms**（`arm()` 內 `_connect_with_retry()` 同步阻塞），不是裝置、不是 drain、不是 endpointing。

**修法：整場共用一條連線**——連一次、整場用 KeepAlive 撐住、每輪只開麥（~140ms）。Deepgram 串流支援單一連線承載多次 utterance（官方 KeepAlive/Finalize 機制）。

**Deepgram 既定行為（查證落檔，2026-06-19）：**
- 10s 內無音訊或 KeepAlive → 連線關閉（NET-0001）。
- KeepAlive：`{"type": "KeepAlive"}`，**text frame**，每 3–5s 送一次撐住；server 不回應。
- Finalize：`{"type": "Finalize"}` 強制處理 pending 音訊（沖尾巴）。
- CloseStream：`{"type": "CloseStream"}` 優雅關閉。
- 來源：developers.deepgram.com/docs/audio-keep-alive、/docs/finalize。

## 2. 設計核心 + 行為規約

**把 `SttWorker` 拆成兩層生命週期：**

- **連線層（整場常駐）**：`_ws`（持久連線）+ receiver thread + **keepalive thread**。第一次 `arm()` lazy 建線（這一輪付 580ms），之後整場活著（跨輪、跨對話）。
- **收音層（每輪 arm/disarm）**：arecord（`_audio`）+ sender thread。每輪開關，只剩 ~140ms。

**生命週期行為表：**

| 時機 | 動作 |
|---|---|
| 首次 `arm()` | `_ensure_connected()` 建線（580ms，僅這輪，含「開麥連線 Xms」計時）→ 起常駐 receiver + keepalive thread → spawn arecord + sender → `_armed_at=monotonic`、`_capturing=True` |
| 後續 `arm()` | `_ws` 已活 → **跳過建線** → 只 spawn arecord + sender（~140ms）→ `_capturing=True` |
| `disarm()` | `_capturing=False` → 停 sender（`_send_stop.set()`）+ `_audio.close()`（terminate arecord）+ join sender → 送 `Finalize`（沖尾巴，best-effort）；**`_ws` 不關** |
| 兩輪之間 | keepalive thread 每 **5s** 送 `{"type":"KeepAlive"}`（**僅 `_capturing=False` 時**；capturing 中音訊自然撐住，跳過）撐住連線 |
| receiver（常駐） | `_ws.recv()` 迴圈；speech_final **只在 `_capturing=True` 才 `sink` 注入**（防上一輪殘響/Finalize 結果漏進下一輪）；含「開麥後 Z.Zs 出辨識結果」計時 |
| `_ws` 死掉 | receiver/keepalive 的 recv/send 報錯（非 shutdown 觸發）→ 標記 `_ws=None`（dead）+ 印警示 → **下次 `arm()` 自動重連**（那輪付 580ms，之後又常駐） |
| `shutdown()` | `disarm()` → `_conn_stop.set()` → 送 `CloseStream` + 關 `_ws` → join receiver + keepalive |

**併發安全（多 thread 共用 `_ws`）：**
- **`_send_lock`** 序列化所有 send（sender 音框 / keepalive / Finalize / CloseStream）——websockets sync client 並發 send 非 thread-safe；recv 與 send 雙工分離不需同鎖。
- keepalive 只在 `_capturing=False` 送、sender 只在 capturing 中跑 → 兩者本就互斥；`_send_lock` 主要序列化 keepalive vs disarm-Finalize vs shutdown-CloseStream 的瞬間重疊。
- `_capturing` bool：arm 設 True、disarm 設 False；receiver 注入前讀、keepalive 送前讀。set-before-spawn / 單一 writer 路徑，配合 `_lock` 保護狀態切換。

**行為不變式（對話層零感知）：**
- 每輪注入的顧客 utterance 與現狀**完全相同**（同 speech_final → 同注入）；每輪只取第一個 speech_final（與現狀「拿到輸入即 disarm」一致）。
- `arm()` / `disarm()` / `shutdown()` 對外 signature 不變 → `main.py read_customer_input` **零改動**。
- 缺 key / 連線失敗 → 停用走純鍵盤（現狀 graceful degradation 保留）。
- `STT_TTS_TIMING` 計時：「開麥連線」現在**只在真正建線時印**（首輪 / 重連）→ 後續輪不印 = 連線復用的視覺證據；「開麥→第一個音框」「開麥後…辨識結果」每輪照印。

**效果：** 首輪 580ms（建線），**第 2 輪起 ~140ms**（只開麥）。一段 5–8 輪點餐只在開頭付一次連線。

## 3. 改檔範圍（高層；step-by-step 移 plan.md）

- `myProgram/stt.py` — **`SttWorker` 重構**（大改）：
  - `__init__`：state 從 `_session` 單元組 → 拆 `_ws`/`_capturing`/`_conn_stop`/`_receiver`/`_keepalive`（常駐）+ `_audio`/`_sender`/`_send_stop`（每輪）+ `_send_lock`；保留 `_armed_at`/`_disabled`/`_lock`。
  - `_ensure_connected()`（新）：lazy 建線 + 起常駐 receiver/keepalive；含連線計時。
  - `arm()`：改為 `_ensure_connected()` → spawn arecord+sender → set capturing（不再建 receiver/每輪 ws）。
  - `disarm()`：停收音層 + Finalize，不關 ws。
  - `_send_loop(audio, send_stop)`：send 走 `_ws` + `_send_lock`。
  - `_receive_loop(conn_stop)`：常駐、`_capturing` 閘門、ws 死標記。
  - `_keepalive_loop(conn_stop)`（新）：5s 週期、capturing 跳過、`_send_lock`。
  - `shutdown()`：收兩層 + CloseStream + 關 ws + join 常駐 thread。
  - module helper（KeepAlive/Finalize/CloseStream 送出）按需抽。
- `tests/stt/` — 擴充 `conftest.py` 的 `FakeWs`（recv 空時阻塞至有訊息/關閉、捕捉 control send、模擬 death）+ `test_worker.py` 新增持久連線 / keepalive / 閘門 / 重連 / Finalize 測試。
- `main.py` — **不動**（arm/disarm/shutdown 介面不變）。

## 4. Out of scope（本輪不做）

- **prearm（念提示音時建線）**：persistent 已涵蓋第 2 輪起的提速；首輪 580ms 暫留（要連首輪都即時再另議，YAGNI）。
- **per-conversation 連線**（回 hawk 即關、下對話重連）：先做「整場一條」；若 Pi 顯示 Deepgram 限制長 session → 再縮（§見風險）。
- arecord 冷啟動（~140ms）：本輪不碰（已是小頭）。
- drain / endpointing / 既有辨識行為：不動。

## 5. 規範與參考

- 派 **sales-coder**（worker 級重構）；Karpathy + TDD frontmatter 預載。
- 多線程設計參考：skill `reference/myprogram-threading-paths.md`（daemon cleanup / Event 旗號 / blocking IO 不強解）、`reference/incremental-rebuild.md`（單 queue 單消費者 / race 收斂）。
- Deepgram 訊息格式見 §1（已查證）。
- 既有可 reuse：`_connect_with_retry`（連線重試 + 401 偵測，搬進 `_ensure_connected`）、`_timing`（計時閘門）、`_normalize_transcript`、`FakeWs`/`FakeAudioSource`/`wait_until`（測試 harness）。

## 6. 測試指令 + 預期

- `py -3.14 -m pytest tests/stt/ -q`：既有全綠 + 新增涵蓋——
  - 連線復用：連兩輪 arm/disarm，`ws_factory` 只被呼叫 **1 次**。
  - keepalive：disarm 後（capturing=False）`_ws` 收到 `{"type":"KeepAlive"}`（捕捉 control send，可縮短間隔測）。
  - 閘門：capturing=False 時到達的 speech_final **不注入**；capturing=True 才注入。
  - Finalize：disarm 送 `{"type":"Finalize"}`。
  - 重連：`_ws` 標記 dead 後，下次 arm 重新呼叫 `ws_factory`。
  - shutdown：送 `CloseStream` + 常駐 thread 收掉（不卡）。
- 全套 `py -3.14 -m pytest tests/ -q`（baseline 660，新增測試後上升）。
- Pi：`STT_TTS_TIMING=1 python3.11 -m myProgram` 跑一段多輪點餐 → 確認「開麥連線」只在**第一輪**印、之後不印；「五張」開頭不再被裁；多輪辨識正常；長對話 / 回 hawk 後再來客連線未死。

**既有測試的語意更新（非「弱化」，是行為改變的合法調整）：** 部分既有 STT 測試把「**每輪建新 ws**」寫死進斷言——本重構刻意改成持久連線，故這些斷言必須改成持久語意（reviewer 勿誤判為弱化）：
- `test_disarm_closes_audio_and_allows_rearm`：原斷言 re-arm 後 `len(wss) == 2`（每輪新 ws）→ 改為 `len(wss) == 1`（ws 復用）、`len(audios) == 2`（arecord 仍每輪重開）、`audios[0].closed` 仍真。
- `test_stream_interruption_warns`：ws 死的警示路徑由「每輪 receiver 結束」改為「標記 `_ws` dead + 警示」→ 斷言對齊新訊息/行為。
- 其餘（`test_connect_retry_*` / `test_401_*` / `test_arm_idempotent_*` / 計時三測 / `test_speech_final_*`）首次 arm 仍走 `_ensure_connected`→`_connect_with_retry`，預期續綠；plan 逐一核對，紅則隨重構同步更新斷言。

## 7. Commit 規範

- 重構較大，可分 commit（依 plan 分階段：state 拆分 + _ensure_connected / receiver 常駐化 / keepalive / disarm-Finalize / 重連 / shutdown），每階段 pytest 綠才下一步。
- git add 明列 `myProgram/stt.py tests/stt/conftest.py tests/stt/test_worker.py`（禁 `-A`）。
- message 末尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰

```
首次 arm ─► _ensure_connected（連線 580ms，僅此輪）─► 起 receiver(常駐) + keepalive(常駐)
                                                      └► spawn arecord + sender ─► capturing=True
後續 arm ─► _ws 已活 ─► spawn arecord + sender（~140ms）─► capturing=True
顧客講話 ─► receiver 收 speech_final（capturing 才注入）─► read 取得 ─► disarm
disarm ─► 停 arecord/sender + Finalize（沖尾巴）─► capturing=False（ws 不關）
兩輪間 ─► keepalive 每 5s 撐住 ─► 下輪 arm 直接開麥
ws 死 ─► 標記 dead ─► 下次 arm 重連
shutdown ─► CloseStream + 關 ws + 收常駐 thread
```

## 風險 / Pi 驗證點（收尾寫 pineedtodo）

- **Deepgram 最長 session 限制**：整場一條連線可能撞 server 端 session 上限 → Pi 跑長對話 / 多組客人確認不斷；若撞 → 縮成 per-conversation（Out of scope 的備案）。
- **跨輪殘響漏單**：`_capturing` 閘門 + Finalize 是否真擋住上一輪尾巴 → Pi 觀察下一輪開頭有無冒出上一輪殘字。
- **重連 fallback**：手動中斷網路一下 → 下輪 arm 應重連、不卡死（最壞退回該輪鍵盤）。
- **keepalive 撐連線**：兩輪間隔 >10s（機器人長回應）後連線仍活、辨識正常。
