# Changelog — STT/TTS 即時化 + 連線可靠性長征（2026-06-19 ~ 06-20）

> 詳細設計 / 逐次 Pi 實測在各 spec；本檔記結論 + 指標位置 + **驗證狀態（已驗 / 待驗 / 試後 revert）**。
> 起點：webui Phase 2 收尾後，使用者轉「優化 STT/TTS 效能與延遲」。

## 淨落地（可靠、留在 main）

| 成果 | commit | 狀態 |
|---|---|---|
| **條件式 ALSA drain**（worker idle 時跳 0.3s 尾巴 sleep，省 turn boundary） | `4810f89` | Pi 驗 ✅（drain=off 正確、無自我回授） |
| **計時診斷 log**（`STT_TTS_TIMING` env-gated：連線 / 開麥首框 / 辨識 delta / Deepgram 每訊息） | `2da4aa1`/`5c66d8e`/`78fea76`/`0cbafde` | 量測利器，預設靜默 |
| **endpointing env 旋鈕**（`STT_ENDPOINTING_MS`，預設 300） | `52e10eb`（+`de444dc` 回 300） | Pi A/B 用 |
| **prearm 首連線**（`read_customer_input` wait_idle 前背景建線，藏 540ms 握手） | `d69e61f` | Pi 驗 ✅ |
| **併發 hardening ×4 反思**（`_receive_loop` 雙層 try / 建線移出 `_lock` / disarm join 守衛 / receiver-start `is_alive` 守衛） | `f6b3c3f`/`5cb9856`/`db52977`/`0cbafde` | reviewer ✅ |
| **zombie bug 根治**（移除逐輪 disarm Finalize——Deepgram 後續 utterance finalization 被破壞→speech_final 空白→整輪漏辨識） | `4ff428e` | **Pi 全流程驗收 ✅**（點餐→上限 reask→結帳→付款→次客） |
| **辨識 robustness**（空 speech_final 退用本句最後非空 interim） | `802c646` | Pi 驗（部分） |

## 試了又 revert（誠實教訓）

| 嘗試 | 為何 revert | commit / spec |
|---|---|---|
| **持久連線**（整場共用一條 Deepgram 連線 + KeepAlive） | 上線即修好（hardening + zombie），但「用久累積辨識 lag」最終促成改每輪新連線 | `5a11739`→`724ef74`（spec `stt_persistent_connection`）；後被 per-turn 取代 |
| **endpointing 450**（減少中途停頓拆句） | 背景音下 Deepgram 等不到靜默 → **speech_final 永遠不發 → 整輪 timeout** | 試 `802c646` → 回 300 `de444dc` |
| **warm-arecord**（念提示音時就開麥暖機、sender discard 丟機器人音、arm 翻送出，修開頭 40ms 冷啟動裁頭） | 雙 reviewer 過、但 Pi **間歇收不到音/收靜音**（arecord 撞 mpg123 播放並行開麥，舊版「收不到音」老坑）、且開頭裁頭未全解 | 試 `8369fd2`→`370e0d0` → revert `7be81a2`（spec `stt_warm_arecord` 含教訓） |

## STT 連線生命週期演變
`stt_p1` 每輪重連（連 580ms 在 arm 同步阻塞）→ **整場持久**（persistent + keepalive + 持久 receiver）→ **每輪新連線**（per-turn：disarm 收線、移除 keepalive、prearm 藏重連；2026-06-20 `4d8d388`，spec `stt_per_turn_connection`）。

## 待 Pi 驗收（核心假設）
**每輪新連線是否解掉辨識 lag**（持久連線用久 lag：interim 空 10s、完整結果 disarm 後才回）。驗收單 `pineedtodo/2026-06-20_stt_per_turn_connection_verify.md`。
- lag 消失 → 假設成立、收。
- lag 仍在 → 假設否證（lag 是 Deepgram/網路非連線）→ revert 回持久連線版（`4ff428e` 線為退路），STT 連線角度窮舉、靠「講話習慣 + 鍵盤備援」撐 demo。

## 固有殘留（非 bug，遞減報酬）
- **開頭偶爾掉字**（Deepgram 對串流第一個字易吞 + Pi 聲學）：靠「講話別卡提示音收尾瞬間、自然頓一下」習慣解（warm-arecord 試圖根治失敗）。
- **辨識準度**（三→湯之類近音誤判）：Deepgram + keyterm 已盡力，固有 floor。

## 反思採納（proposals.md）
本長征觸發並採納 5 條併發 / 測試反思（`receiver-start-after-lock-race` / `receive-loop-outer-try-exit` / `arm-lock-held-during-blocking-io` / `disarm-finalize-blocked-after-join-timeout` / `test-sender-alive-after-disarm-nilptr`），皆 code 層 pytest 守、不轉 eval。

## 流程沉澱
- 全程純 git worktree + sales-coder 派發 + 三段 reviewer（連線生命週期 / 併發改動務必跑）；多次「reviewer 找到 flaky test 屏障 → 改真 `wait_until`」「sales-coder 停下回報 race → coordinator 裁決」。
- **revert 紀律 dogfood**：warm-arecord / endpointing 450 / persistent 三次「試 → Pi 實測否證 → 乾淨 revert」，每次保留可用版為退路。
