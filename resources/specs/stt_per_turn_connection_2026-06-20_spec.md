# STT 每輪新連線（per-turn，棄持久連線）— SDD spec

**日期：** 2026-06-20
**類型：** worker 連線生命週期重構（`myProgram/stt.py`）— 修辨識 lag
**裁定：** 使用者 2026-06-20 選「最後一搏：每輪新連線」。

## 1. 背景與動機
Pi 實測：持久連線**用久了累積辨識延遲**（第 1 輪剛建線正常、第 2 輪復用連線 interim 空 10s、完整結果到 disarm **之後**才回 → 該輪 timeout 取消）。這與之前的空定稿、no-fire 同源——都是**長命持久連線的毛病**。

**修法：棄持久連線，改每輪新連線。** disarm 即收線；下輪 prearm（背景）/ arm 重連。每輪連線都新鮮、不累積 lag。prearm 仍把建線（~560ms）藏進提示音播放。keepalive **移除**（連線不再跨輪存活，無 idle 可撐）。

## 2. 設計核心 + 行為規約

**連線層從「整場常駐」改「每輪」：disarm 收線、下輪重連。**

- **`_close_connection()`（新，從 shutdown 抽出）**：送 CloseStream + 關 ws + 收 receiver thread。冪等（無連線 no-op）。
- **`disarm()`**：停收音層（capturing 才停 sender/arecord）→ **`_close_connection()`**（每輪收線；涵蓋 prearm 已連但未 arm 的情況——判定用 capturing 局部變數 + 無條件收線）。
- **`shutdown()`**：`self.disarm()`（已涵蓋收音層 + 收線）。
- **`_ensure_connected()`**：不變（lazy 建線 + `_connect_lock` 序列化 prearm/arm）——但**不再起 keepalive thread**（只起 receiver）。`_ws` 由 disarm 收掉 → 每輪 arm 都重連。
- **`prearm()`**：不變（背景 `_ensure_connected` 建線，藏延遲）。
- **移除 keepalive**：`_keepalive_loop`、`_KEEPALIVE_INTERVAL`、`_KEEPALIVE_MSG`、`__init__` 的 `_keepalive`、`_ensure_connected` 起 keepalive、`_close_connection`/原 shutdown 收 keepalive ——全刪。

**行為不變式 / 規約：**
- `arm`/`disarm`/`shutdown`/`prearm` 對外 signature 不變 → `main.py` 不動。
- 收音層（arecord 在 arm 才開、discard 無——warm 已 revert）、receiver `_capturing` 閘門、last-non-empty fallback、endpointing 300、Finalize 不送：**全不動**。
- 每輪：prearm 連線 → arm 收音 → 辨識 → disarm 收線。連線只活一輪（<12s，期間音訊撐住，無需 keepalive）。
- 連線失敗 → arm 走鍵盤（現狀保留）；每輪獨立，無「重連」概念（下輪本就重建）。

## 3. 改檔範圍（高層）
- `myProgram/stt.py`：新 `_close_connection`；`disarm` 加收線；`shutdown` 簡化為 disarm；`_ensure_connected` 去 keepalive；刪 keepalive 全部（loop / 常數 / 欄位）。
- `tests/stt/test_worker.py`：`test_connection_reused_across_arm_disarm` → 改為 **per-turn 重連**（arm/disarm/arm → ws_factory **2 次**）；刪 `test_keepalive_sent_when_idle`（per-turn 無 idle keepalive）；新增 `test_disarm_closes_connection`（disarm → CloseStream 送、`_ws` None）；其餘（重連 / 閘門 / 計時 / speech_final / prearm / shutdown CloseStream）對齊。

## 4. Out of scope
- warm-arecord（已 revert，不重做）。
- 辨識準度（Deepgram floor）/ 對話 timeout 調整：不動。
- endpointing / 對話文案 / 收音層 / 辨識 robustness：不動。

## 5. 規範與參考
- 派 **sales-coder**；讀 `reference/myprogram-threading-paths.md`。**走完整三段 reviewer**（連線生命週期 + 併發）。
- 既有 reuse：`_ensure_connected` / `_connect_lock` / `_send_lock` / `_close_connection`（抽出）/ `_CLOSE_MSG`。

## 6. 測試
- `py -3.14 -m pytest tests/stt/ -q`：
  - `test_reconnects_per_turn`（原 reused 改名/改斷言）：arm→disarm→arm，ws_factory **被呼叫 2 次**（每輪新連線）。
  - `test_disarm_closes_connection`：arm → disarm → `_control_sent(ws,"CloseStream")` 真、`worker._ws is None`、receiver thread 收掉。
  - 刪 `test_keepalive_sent_when_idle`。
  - 既有 `test_dead_connection_reconnects_on_next_arm` / `test_speech_final_*` / `test_prearm_*` / `test_closestream_sent_on_shutdown` / 計時 → 續綠（必要時對齊）。
- 全套 `py -3.14 -m pytest tests/ -q`（baseline 675，刪 1 + 新 1 → 675）。
- Pi：`STT_TTS_TIMING=1` 多輪 → **每輪都 `開麥連線 Xms`**（每輪重連，prearm 藏在提示音）；辨識**不再 lag**（結果即時、不會 disarm 後才回）；全流程通。

## 7. Commit
- 明列 `myProgram/stt.py tests/stt/test_worker.py`；末尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 風險 / Pi 驗證點（收尾 pineedtodo）
- **動連線生命週期**：三段 reviewer + Pi 全流程；壞了 revert（持久連線版為退路）。
- **每輪重連的延遲**：prearm 是否確實把每輪 ~560ms 藏進提示音（看 `開麥連線` 出現在提示音播放期間、arm 不卡）。
- **lag 是否消失**（核心假設）：每輪新連線後，辨識結果是否即時回（不再 disarm 後才回）。若 lag 仍在 → 假設否證，回報（lag 非連線、是 Deepgram/網路）。
