# STT warm-arecord（麥克風暖機修開頭裁切）— SDD spec

**日期：** 2026-06-19
**類型：** worker 收音層重構（`myProgram/stt.py`）— 修 onset clip
**裁定：** 使用者 2026-06-19 批准（連續丟棄版 warm-arecord，可 revert）。

## 1. 背景與動機
開頭裁切：arecord 在 `arm()`（提示音播完）才開，~40ms 冷啟動咬掉「紅茶」字頭 → Deepgram 認不出整個詞。使用者要「麥克風提早開好、開在倒計時之前」。

**修法：連續丟棄版 warm-arecord**——`prearm`（念提示音時）就開 arecord + 啟動 sender，sender 先「丟棄模式」（讀麥克風但不送 Deepgram）；`arm` 把 sender 翻「送出模式」。麥克風全程暖機 → arm 後首框即時送、無冷啟動裁頭。連續讀 pipe → 不會緩衝爆掉（舊 warm-arecord「收不到音」正是沒連續讀、pipe 塞爆）。

## 2. 設計核心 + 行為規約

**收音層（arecord + sender）從 `arm` 搬到 `prearm`；sender 加 capturing 控制的 discard/send 模式。**

- **`_warm_capture()`（新，冪等）**：`_audio is None` 才開 arecord（`audio_factory`）+ 起 sender thread。`_audio`/`_send_stop`/`_sender` 於 `_lock` 內寫。單一 caller thread（主線程 prearm/arm）。
- **`prearm()`**：quick-check（disabled / capturing / no-key 即返）→ `_warm_capture()`（capturing=False → 丟棄模式暖機）→ 背景 `_ensure_connected`（ws 未連才起 thread）。
- **`arm()`**：quick-check → `_ensure_connected()`（確保 ws，等 prearm 背景連線完成則復用）→ `_lock` 內設 `_armed_at` + `_capturing=True`（sender 翻送出）→ `_warm_capture()`（冪等 fallback：prearm 已暖則 no-op，否則現開；capturing 已 True → sender 直接送，無 race）。
- **`_send_loop(audio, send_stop)`**（去掉 `ws` 參數，改讀 `self._ws`）：
  ```
  讀 chunk → EOF break
  not capturing → continue（丟棄：讀+丟，保持 pipe 排空、麥克風熱）
  ws = self._ws；ws is None → continue（capturing 但連線未就緒，罕見）
  首次送出印「arm→首框送出 ~0s（麥已暖）」
  with _send_lock: ws.send(chunk)
  ```
- **`disarm()`**：判定改 `if self._audio is None: return`（涵蓋「prearm 暖機但未 arm」也要收 sender，非只看 capturing）→ `_capturing=False` + 停 sender + close arecord + join + 清。
- **`is_armed()`**：仍回 `_capturing`（暖機未 arm ≠ armed）。

**行為不變式 / 規約：**
- `arm`/`disarm`/`shutdown`/`prearm` 對外 signature 不變 → `main.py` 不動（read_customer_input 已 prearm→wait_idle→arm→disarm）。
- 念提示音期間（capturing=False）錄到的機器人聲音**全丟棄、不送 Deepgram** → 無自我回授。
- 機器人尾巴音（arm 後 ALSA 仍響 ~0.3s）會被送一小段 → 與**現狀相同**（現狀 arm 後也收尾巴），非回歸。
- 連續讀 arecord → pipe 不爆（修舊版「收不到音」根因）。
- 辨識 / 注入 / 連線層 / receiver / keepalive / disarm 收尾 行為不變。

## 3. 改檔範圍（高層；step 移 plan）
- `myProgram/stt.py`：新增 `_warm_capture()`；`prearm` 改（warm + connect）；`arm` 改（capturing+warm，不再自開 arecord/sender）；`_send_loop` 改（去 ws 參、discard/send 模式）；`disarm` 改判定（`_audio is None`）。
- `tests/stt/test_worker.py`：新增 warm 行為測（discard→send 翻轉、prearm 暖機未 arm 也被 disarm 收）；既有 `test_sender_streams_audio_chunks` / `test_prearm_*` / `test_disarm_closes_audio_and_allows_rearm` / 連線測 → 對齊新結構（多為續綠，少數斷言調整）。

## 4. Out of scope
- 機器人尾巴音的額外 guard（現狀相同、demo 容忍）：不做。
- endpointing / 對話文案 / 連線生命週期 / receiver / 辨識 robustness：不動。
- 結構更大的 AEC / barge-in：不做（revert 史）。

## 5. 規範與參考
- 派 **sales-coder**；動手前讀 `reference/myprogram-threading-paths.md`。**走完整三段 reviewer**（動到 working 收音層、併發）。
- 既有 reuse：`_ensure_connected` / `_connect_lock` / `_send_lock` / `_timing` / `audio_factory` / FakeWs / FakeAudioSource / wait_until。

## 6. 測試指令 + 預期
- `py -3.14 -m pytest tests/stt/ -q`：
  - 新 `test_warm_capture_discards_then_sends_after_arm`：blocking audio source → prearm 啟 sender；capturing=False 餵 chunk → ws **未**收（丟棄）；arm → 餵 chunk → ws **收**（送出）。
  - 新 `test_prearm_warmed_sender_stopped_by_disarm`：prearm 暖機（未 arm）→ disarm → sender 被收（不殘留）。
  - 既有 `test_sender_streams_audio_chunks`（arm 直呼：capturing 先 True 再 warm → 不丟首框）/ `test_prearm_*` / `test_disarm_*` / `test_speech_final_*` / `test_connection_*` → 續綠（必要時對齊斷言）。
- 全套 `py -3.14 -m pytest tests/ -q`（baseline 675）。
- Pi：`STT_TTS_TIMING=1` 多輪 → `arm→首框送出` 趨近 0；搶快講「紅茶」字頭收得到、不裁；無機器人尾音被誤辨識；全流程通。

## 7. Commit 規範
- 分階段或合一；明列 `myProgram/stt.py tests/stt/test_worker.py`（禁 `-A`）；末尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

## 8. 流程鳥瞰
```
read_customer_input
 ├ prearm()  → _warm_capture（開 arecord + sender discard 模式）+ 背景連線
 ├ wait_idle（提示音播放；sender 讀+丟機器人音、麥克風暖著、pipe 排空）
 ├ arm()     → _ensure_connected（復用 prearm 連線）→ capturing=True（sender 翻送出）
 │            → arm 後首框即時送（麥已暖、無冷啟動裁頭）
 ├ 倒數讀輸入
 └ disarm()  → capturing=False + 停 sender + close arecord
```

## 風險 / Pi 驗證點（收尾 pineedtodo）
- **動 working 收音層**：三段 reviewer + Pi 全流程驗收;壞了 revert（現版可用 STT 為退路）。
- **discard→send 翻轉時序**：arm 翻 capturing 後第一框是否即時送、有無漏首框 / 送到機器人尾音。
- **prearm 暖機未 arm 的清理**：disarm `_audio is None` 判定確保不殘留 sender。
- **arm→首框送出 趨近 0**：證明暖機生效、字頭不裁。
