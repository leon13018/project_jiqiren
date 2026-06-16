# Changelog — 回歸主程式開發（2026-06-08 ~ 當期）

> 本檔記當期里程碑與指標位置；逐項 SDD spec/plan 在 `resources/specs|plans/`，Pi 待辦在 `resources/pineedtodo/`。主題：STT 串流 + NLU/語音對 ASR 近音誤辨識的 robustness。

## 里程碑（執行序）

### 1. STT barge-in Phase 1 — Deepgram Nova-3 串流基礎
- 統領設計 `a3b0dd3`；spec/plan `4e63279`（`specs/stt_bargein_2026-06-12_design.md`）。
- `myProgram/stt/`：SttWorker 骨架 + no-key 停用路徑、session sender/receiver + `speech_final` 注入、disarm 生命週期（冪等 / re-arm / join 收束）、連線重試 / 401 永久停用、production factories（arecord/websockets）+ lazy singleton。
- `main.py` `read_customer_input` 佈線 STT arm/disarm + shutdown 鏈；`input_reader` inject 公開注入點（STT 與鍵盤共用單 queue）。
- **keyterm prompting 詞表偏置**（`07f7729`/`4cf80bd`）：解「三瓶」被誤辨識為商品的近音問題。
- **Phase 2（25% 開麥 + 搶話中斷 + AEC）未做** → 見「下一步」。

### 2. NLU 全繁體化 + 醬就好合音
- 移除全部簡體 keyword 與對應測試（`91155fa`/`e2e7144`）；spec `0d389bc`。「這樣→醬」連讀合音先入 CHECKOUT（`7014579`），後撤回 hardcode 改由糾錯層統一處理（`7ccee39`）。

### 3. 本地拼音糾錯層（demo 抗 ASR 近音誤辨識核心支線）
- 統領設計 `a01214e`（合音還原 + 拼音近音）。
- **Phase A 問數量**：`phonetic.py` 近音比對核心（聲韻母模糊 + 歧義安全閥 + pypinyin 注入 seam + 缺依賴 graceful）→ 問數量 sub-loop 掛載（解「商品→三瓶」）。
- **Phase B 問商品**：引擎擴展（疊字去重 / 介音等價 / group_key / 子串）+ 內嵌數量(①) + 問商品 unclear 出口掛載。
- **Pi 實測 bug 修**：千/萬（一千張→1000）、阿拉伯+中文乘數（9萬→90000）、商品名歪+數量同句拆句、`_product_group` 空 parse 守衛。
- **②數量提前**（三瓶紅茶→×3）+ **③合音還原**（醬/將就好→這樣就好→結帳）。
- **統一 token-parser 重寫**（`1062173`）：`parse_products` 重寫為一次解任意順序 / 多商品 / garbled 品名+數量，subsume 掉 sticky-right / ②leading / ①window / Phase B split 四機制；**完全同音 tie-break**（`5ea9f6f`，解「紅茶食品→×10」真歧義）。
- 測試 504 → 589（+85）。**Pi 實測通過**。

### 4. 結帳收尾語音合併
- L4「付款成功」+ L5「謝謝光臨，歡迎再來」合為**單句**「付款成功，謝謝光臨，歡迎再來」由 L4 播；L5 去 speak（移除 `speak` 參數）只留 wave_hand；移除死常數 `L4_A_PAY_SUCCESS`/`L5_THANKS`；附帶免疫「付款成功尾巴被截」ALSA drain。
- spec/plan `3377f6b`/`8745d8b` → 重構 `dfa8bbf` → doc 清理 `f1e851f`；589 全綠、三段審通過。
- 預錄資產：Pi `tts_prewarm` 合成合併句（+6% rate）+ scp 拉回 commit（`b8de404`，斷網可播）。**Pi 實測通過**。

### 5. parser filler-strip + housekeeping triage（精實批次）
- **C2 filler-strip**（`46d3d6c`，走完整 SDD）：`parse_products` step 3 garbled 品名 phonetic 前剝意圖前綴 filler（`_GAP_FILLER_PREFIXES`），解「我要刮樂」→刮刮樂；保守單一前綴、剝空不誤造商品。
- **D1**（`5f0aefa`）：`test_constants` 補 `C2_DECISION_TIMEOUT==6` 守值斷言（補齊 timing sibling pattern）。
- **D3**（`a13c7ac`）：語音合併後 2 個孤兒快取 mp3 `git rm`。
- **roadmap 刷新**（`adc2495`）+ **watchlist consolidate**（`b022e30`，遷 perf §10 4 條入單一事實來源 W-14~17）。
- **triage 共識 defer**（已記 watchlist/roadmap）：C1 無分隔雙數量（輸入本歧義）/ C3 插字 garble（需編輯距離）/ C4 合音表擴充（缺證據）/ D4 daemon warning（連 repro 未有）/ D3 通用清理工具。
- 測試 589 → 592；無 Pi 操作（純解析邏輯）。

### 6. STT Phase 2 — 讀 ch0 + 預熱連線（barge-in 經 AEC 實測收掉）
- **真 barge-in 不可行（Pi 實測 2026-06-16）**：硬體 AEC ~0dB、最佳線性 AEC 上限 7–10dB（換主動式喇叭僅+2dB、1秒窗≈整段排除時脈漂移、`norm_xcorr 0.178` 非線性耦合）；需 20–30dB 才能可靠搶話 → 收掉。詳 spec `stt_p2_2026-06-16_spec.md` §1（離線最佳線性 FIR 工具 `userPrompt/aec_offline*.py`）。
- 轉 turn-taking 微調（spec/plan `55ed770`）：① 讀 ReSpeaker **ch0 處理後聲道**（`_extract_ch0` + `_ArecordSource` 反交錯 + factory `-c 6`，取代 6ch 降混稀釋）`a908209`；② **prewarm gate** 預熱 Deepgram 連線（`_live` Event + `_start_session(live)` race-safe + `main.py` `prewarm→wait_idle→arm`）`fad257e`；review minor doc `47ba770`。
- 測試 592 → 627（+35 stt，含 ch0 反交錯 / gate 丟棄）；spec-reviewer + code-quality 三段審通過（Windows）。
- **❌ 已 revert（2026-06-16 Pi 實測）**：prewarm 邊播邊收 → 機器人自聲經 Deepgram **延遲轉錄、漏過 `_live` 閘**（閘只能依「收到時間」判斷，擋不住「播放時收、講完延遲才回」的轉錄）→ `[語音辨識]` 收到自己的 TTS → 自我回授無限迴圈。**無 AEC 無從擋** → code 退回 `e15167a`（Phase 1，播完才開麥；621 綠）。spec/plan 留存為記錄、pineedtodo `git rm`。**結論：無 AEC 時任何邊播邊收（prewarm / barge-in）皆不可行；STT 停在 Phase 1。**

## 架構 / 流程沉澱
- 新模組：`myProgram/stt/`（Deepgram 串流 worker）、`myProgram/sales/phonetic.py`（拼音近音糾錯，pypinyin 注入 + graceful）。
- `parse_products` = 統一 token-parser（精確商品 span + 數量 span + phonetic garbled 兜底 + 鄰近綁定 + dedup 規則 1/2/3）。
- 新依賴（Pi，記於 `requirements/raspberry_pi_setup.md`）：pypinyin（拼音糾錯）、Deepgram（STT，需 API key）。
- 反思採納：cwd-pinned worktree Option B（`worktree.md`）、cp936 中文輸出探針設 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`（`conventions.md`）。

## 下一步（pending）
- ~~STT barge-in Phase 2~~ / ~~Phase 2 turn-taking~~：真搶話經 AEC 收掉；Phase 2 turn-taking 亦 revert（prewarm 自我回授，見里程碑 6）→ **STT 停在 Phase 1**。
- **HTML UI**（`roadmaps/html_ui_plan.md`）｜**期末 demo 準備**（`presentation/` 尚空）。
- deferred edges（已記 watchlist W-14~17 / roadmap）：C1 無分隔雙數量、C3 插字 garble、C4 合音表擴充、D4 daemon warning、D3 通用快取清理工具——demo 真踩到再修。
