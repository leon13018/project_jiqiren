# Changelog — 叫賣循環修復 + 終端 UX toggles + OpenCV→觸控 + 啟動效能（2026-06-20 ~ 06-21）

> 詳細設計在各 spec（`resources/specs/`）；本檔記結論 + commit + 驗證狀態。
> 起點：STT 收斂後，使用者轉「優化主程式」——從「叫賣沒真的循環」一路做到對話觸發改觸控、demo 終端淨化、啟動 lag。
> **驗證**：全程 `py -3.14 -m pytest tests/` 綠（704 passed 收尾）；**行為類改動 Pi by-ear 待使用者驗**（叫賣循環 / 觸控觸發 / 啟動順暢 / toggles）。

## 淨落地（留在 main）

| 成果 | commit | 驗證 |
|---|---|---|
| **叫賣循環修復**：hawk loop 改 idle-gated monotonic 自驅輪播（每句自「上一句 TTS 播完」起算 HAWK_INTERVAL、`% len` 輪替）；新增非阻塞 `tts.is_idle()` 原語；**移除 schedule 死抽象**（唯一 production 實作是 no-op→實機從不循環，測試靠 FakeScheduler 假驅動才綠、漏抓） | `89740b5`+`444cff6` | pytest ✅ / Pi 待驗 |
| **`SALES_SHOW_COUNTDOWN`**：`timeout=N`/`wait=N` 每秒倒數行預設隱藏，`=1` 才印（閘在 `_tick_countdown` 單點、計時不受影響） | `7875d47` | pytest ✅ / Pi 待驗 |
| **`SALES_QUIET`**：藏機器人狀態 echo（`[語音]`/`[動作]`/`[opencv]`/`[模擬]`/`[模擬提示]`），**保留導航**（print_terminal/選單）**+ 錯誤 ⚠️**；main/tts/action 各自讀 env、gate 只包 print（worker dispatch/狀態寫入在閘外） | `f529690` | pytest ✅ / Pi 待驗 |
| **移除 OpenCV 偵測 → `'t'`/觸控「開始點餐」觸發 L2**（大重構，見下） | `daf4fd7`(Wave A 加't')+`1db8c5b`(Wave B 移 opencv) | pytest ✅ / Pi 待驗 |
| **啟動效能**：`--web` 的 FastAPI/uvicorn import + server.start 移背景 daemon thread、worker(tts/action/stt)背景預熱 → menu 立即可互動（修「banner 按 1 進入卡好幾秒」） | `299e482` | pytest ✅ / Pi 待驗 |
| **flaky tts 測試根治**：`test_prefetch_synthesizes_*` 偶 fail `['X','A','B']`——兩個 hang 測試 say("X") 後沒 drain 殘留 daemon worker、重載下「X」晚被後續測試的全域 `_synthesize` patch 合成、污染對方 synth_calls；修法在 hang test 加 `wait_idle` drain | `be02766` | 並發 16/16 綠（修前 2/6 fail）✅ |
| **boot.join timeout**（反思落地）：`_run_wiring` finally `boot.join()`→`boot.join(timeout=15)`，防未來 server.start 變阻塞時吊死 finally、害 os._exit 安全網跑不到 | `43a0f07` | pytest ✅ |

## 移除 OpenCV 偵測 → 觸控觸發（大重構，2026-06-20）

**動機**：取消 OpenCV 相機偵測，改顧客觸控螢幕「開始點餐」進 L2；終端按 `'t'` 模擬該觸控。
**關鍵洞察**：觸控→對話**早已抽象化**——`web/commands.py` 把 `{type:"wake"}` 映射成 token，注入 input queue 走既有 read 路徑。OpenCV + `'c'` + dwell/mute 只是「模擬硬體偵測」那層。
**改動**（spec `touch_trigger_2026-06-20`，**-589 行**淨刪、25 檔）：
- hawk loop 直接讀 `'t'` → `return "L2"`（沿用 `'q'` pattern）；`web/commands.py` `_WAKE_TOKEN` `"c"`→`"t"`（webui app.js 已送 `{type:"wake"}`、不改）。
- 端到端移除：`opencv_enable/disable/dwell_seconds/mute_opencv` 4 callbacks、`_S1State`、`OPENCV_DWELL/OPENCV_MUTE` 常數、各層 `opencv_disable` 防呆、`read_terminal_key` 的 `'c'` 特判；**刪 `l0_subroutine_a.py`**（其唯一作用 mute 隨 OpenCV 消失）；callbacks dict 14→10。
- 更名：`Transition.via_subroutine_a`→`enter_hawk`（欄位）+ next_state 字串 `"L1_via_subroutine_a"`→`"L1_enter_hawk"`（119 處，使用者裁決一併改達真 grep 清零）。
- **out of scope（未動）**：`'s'`/掃碼付款、webui app.js、dialog NLU/cart/L4 budget/L5 邏輯。

## 流程沉澱（教訓）

- **「測試綠但 production 壞」class**：叫賣 schedule no-op——測試 FakeScheduler 假驅動讓抽象「在測試活、在 production 死」。新增**走真實 loop** 的回歸測試才抓得到（FakeScheduler 假路徑漏抓）。
- **Iron Law 抓 sales-coder grep 漏網**：Wave B 自報 grep 清零 EXIT 1，但其 pattern `opencv|OPENCV` 是 **case-sensitive、漏掉混合大小寫 "OpenCV"**（註解/docstring 6 處）；主 agent 用 `-i` 補抓 + 清，才真清零。→ 獨立驗證（不信自報）價值實證。
- **sales-coder 停下回報 race 裁決**：Wave B 中途抓到 spec 沒寫清的衝突（`via_subroutine_a` 欄位 vs `"L1_via_subroutine_a"` 字串是兩個東西、grep 同時命中），停下回報 → coordinator 補正 spec + 裁決（選 full rename）續做。
- **flaky 用並發重現定位**：閒置 10/10 過、6 並發 2/6 fail；抓到確切失敗值 `['X','A','B']` 才定位 test-isolation 洩漏（殘留 daemon worker + 全域 monkeypatch）→ 根治非加 sleep。
- 全程 worktree + sales-coder + 三段 reviewer（大重構 / threading 必跑）；小 toggle 走 mini-SDD 主 agent 自 patch。

## 反思處理（proposals.md → archive/2026-06-21）
- 採納+落實：`boot-join-missing-timeout`（`43a0f07`）；不轉 eval（非 navigator 可判定）。
- 否決：`spec-file-outside-commit-scope`（誤報——spec 為獨立 commit `9b13189`、impl `299e482`，皆明列檔名未用 `git add -A`；反思 agent 看了跨 commit 累積 diff 誤判）。
