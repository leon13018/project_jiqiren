# STT/TTS turn-boundary 即時化 — SDD spec

**日期：** 2026-06-19
**類型：** 效能 / 延遲優化（worker 層 `myProgram/tts.py` + `myProgram/stt.py`）
**裁定方案：** Approach 1（安全對策 + 量測），使用者 2026-06-19 敲定。

## 背景

一個顧客 turn 的 boundary 死時間地圖（`read_customer_input`，`main.py:127`）：

```
機器人說最後一句 ──► [A] ALSA drain 0.3s（每句固定 sleep）
  └─ tts.wait_idle() 返回
       └─► [B] stt.arm() → arecord 冷啟動 ~0.3–0.5s（mic 尚未熱）
              └─► 顧客講話 …
                   └─► [C] Deepgram endpointing 300ms 靜默 → speech_final
                        └─► NLU+dispatch（µs，perf_w1/w3/w4 已優化）
                             └─► 機器人回話：[D] 未快取句的合成 round-trip
```

[A][B][C] 是**互鎖的聲學 guard band**，不是獨立旋鈕——這正是 prewarm / warm-arecord / barge-in 三輪實驗 Pi 實測 revert 的原因。本 spec 只動其中**有乾淨論證的安全槓桿**，其餘留量測決定。

**前置已完成（不重做）：** perf_w5 TTS 已內容定址快取 + 1-deep prefetch + 常駐 loop + 55 句 prewarm；STT 冷啟動 / barge-in / 多聲道實驗皆 revert（見 roadmap 現況快照）。

## 元件 1 — 條件式 ALSA drain（真正的提速，tts.py）

`TtsWorker._process` 結尾的 `time.sleep(ALSA_DRAIN_SEC)` 改成**只在 queue 還有下一句時才睡**：

- 條件：播放成功後，`if self._peek_next() is not None: time.sleep(ALSA_DRAIN_SEC)`；`_peek_next()` 為 None（worker 即將 idle）→ 跳過 drain。
- **理由**：drain 防的是「下一個 mpg123 開**同一播放裝置**沖掉 ALSA buffer 截尾」。playback→listen 轉場沒有下一個 mpg123；且喇叭 = Pi 板載、麥 = USB ReSpeaker（`plughw:CARD=ArrayUAC10`），**不同物理裝置**，arecord 開 capture 不會沖播放 buffer。
- **保留行為**：連發句之間（`_peek_next()` 非 None）drain 照舊 → 連發截尾防護不變。
- **收益**：每個 turn boundary 省 ~0.3s（機器人最後一句 → 開始聽）。
- **已知 µs race**：`_peek_next()` 與 `_process` return 之間若剛好有新句 put 進來，理論上該尾巴可被下一輪 mpg123 截掉。機率可忽略（µs 窗）、與既有 prefetch peek 同性質、demo 可接受；不另加鎖。

## 元件 2 — 選用式計時 log（量測，env gated）

新增環境變數 `STT_TTS_TIMING`：**未設 = 完全靜默、零行為改變**；設了才印 `[計時]` 行。各模組內聯 env guard（不建共享 util，YAGNI；可隨時移除）。

- `tts.py` `_process`：每句播放後印一行，含「來源（cache 命中 / prefetch / 現場合成）＋ play 時長（mpg123 wait 前後 monotonic 差）＋ drain（on/off）」。→ 直接看到 [D] 合成 round-trip 與 [A] drain 是否省下。合成現場（`run_until_complete(_synthesize)`）另量 synth 時長。
- `stt.py`：`arm()` 記 `_armed_at = time.monotonic()`；`_receive_loop` 每個注入的 speech_final 印「開麥後 Z.Zs 出結果」。→ 看 mic 開多久才有結果（顧客馬上講就反映冷啟動 + endpointing）。

計時數字用 `time.monotonic()`；`stt.py` 需新增 `import time`（目前未 import）。

## 元件 3 — endpointing env 旋鈕（stt.py）

`DEEPGRAM_URL` 目前硬編 `endpointing=300`。改為模組載入時讀 env：

- `_ENDPOINTING_MS = int(os.environ.get("STT_ENDPOINTING_MS", "300"))`，URL 用 `f"&endpointing={_ENDPOINTING_MS}"` 組。
- default 300 → 未設時 URL 與現狀逐字元相同。Pi 設 `STT_ENDPOINTING_MS=200` 即可 A/B「顧客講完 → 反應」速度，**不動碼**。

## 環境變數總覽（寫進 `resources/requirements/raspberry_pi_setup.md`）

| 變數 | 用途 | 預設 |
|---|---|---|
| `STT_TTS_TIMING` | 設任意值即開計時 log（量測用，平時不設） | 未設 = 靜默 |
| `STT_ENDPOINTING_MS` | Deepgram endpointing 毫秒（A/B 用） | 未設 = 300 |

## 行為邊界不變式

> 兩個 env 未設時，全系統行為與現狀**逐位元相同**。

- 文案、L0–L5 狀態轉換、計時倒數秒數、cancel / service confirm / C-2 流程：全不動。
- 連發句之間的 ALSA drain：不變（仍防截尾）。
- `STT_ENDPOINTING_MS` 未設 → URL 不變；`STT_TTS_TIMING` 未設 → 零新增輸出。

## 測試（Windows pytest 全可跑）

- **tts**（`tests/sales/test_tts_worker.py`，已注入 fake `edge_tts`）：
  - drain 在 queue 空（`_peek_next()` 為 None）時 **skip**（spy `tts_module.time.sleep` 未被以 `ALSA_DRAIN_SEC` 呼叫）。
  - queue 有下一句時 drain **照舊**（`time.sleep(ALSA_DRAIN_SEC)` 被呼叫）。
  - `STT_TTS_TIMING` 設 / 未設 → `[計時]` 行有 / 無（capsys 斷言）。
- **stt**（`tests/stt/`，stt.py Windows import-safe）：
  - `STT_ENDPOINTING_MS` 未設 → `DEEPGRAM_URL` 含 `endpointing=300`；設 `200` → 含 `endpointing=200`。
  - `STT_TTS_TIMING` guard：env gating 行為（設 / 未設）。
- **Iron Law**：`py -3.14 -m pytest tests/ -q` 全綠（baseline 649）。

## 風險 / Pi 驗證點（收尾寫 pineedtodo）

- **R1 自我回授（drain）**：skip drain 後機器人尾音是否被 mic 收進自我辨識？理論上 arecord 冷啟動（~300–500ms）≥ 尾音（~200–400ms）會吸收，但**需 Pi 實測確認**。若出現自我辨識 → 單獨 revert 元件 1 commit（原子）。
- **endpointing 200ms**：Pi 設 `STT_ENDPOINTING_MS=200` A/B；若切掉中途停頓的顧客 → 維持 300（不改碼，移除 env 即可）。
- **量測**：Pi 設 `STT_TTS_TIMING=1` 跑一輪 demo，`[計時]` log 貼回 dev 端，用真數字決定下一步（是否再動 endpointing / 走 Approach 3 prewarm 擴充）。

## Out of scope（本輪不做）

- warm-arecord / 連續開麥 / barge-in / 多聲道：已 revert，不重做。
- Approach 3（prewarm 動態句擴充）：留待量測數據顯示 [D] 是大頭才做。
- endpointing 不預設改 200（保持 300，由 Pi A/B 後使用者決定）。
- 計時 log 不預設開（避免 demo log 噪音）。
- 元件 1 的 µs race 不加鎖（YAGNI；機率可忽略）。
