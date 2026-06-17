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
- **❌ 已 revert（2026-06-16 Pi 實測）**：prewarm 邊播邊收 → 機器人自聲經 Deepgram **延遲轉錄、漏過 `_live` 閘**（閘只能依「收到時間」判斷，擋不住「播放時收、講完延遲才回」的轉錄）→ `[語音辨識]` 收到自己的 TTS → 自我回授無限迴圈。**無 AEC 無從擋** → code 退回 `e15167a`（Phase 1，播完才開麥；621 綠）。spec/plan 留存為記錄、pineedtodo `git rm`。
- **✅ v2 修正重做（spec/plan `eb8378e`）**：把閘從「結果端」移到**「來源端」**——`prewarm` 只連 ws + 週期送 KeepAlive 維持連線、**完全不送音訊**（`_open_ws`/`_keepalive_loop`），`arm` 才起 sender 送顧客音訊 → Deepgram 從沒收到機器人聲 → 無轉錄 → **無回授**。session tuple→dict、移除 `_live` 結果端閘、ch0 一併加回。增量1 `cc61647`（ch0）+ 增量2 `d8c8d77`（來源端閘）；592→627 綠；spec-reviewer + code-quality ✅（後者查證 websockets sync `send` 持 `protocol_mutex`、keepalive/sender 並發 send 安全）。**Pi 實測無自我回授通過**，但殘留「播完不能馬上講、卡頓」。
- **✅ v3 暖機期送靜音（spec/plan `0e05d08`）**：v2 把 arecord 留在 `arm()` 才起 → 提示音播完仍有 arecord spawn 啟動延遲（Pi 實測「播完不能馬上講、卡頓」）。v3 把 arecord **提前到 `prewarm`** 暖好、暖機期 sender 讀真實聲但送**等長靜音**（`b"\x00"*len(chunk)`，機器人聲永不進 Deepgram、靜音同時維持連線取代 KeepAlive thread），`arm` 翻 `live` Event 解 mute 改送真實 → **零 arm 啟動延遲**。`_open_ws`→`_start_session(live_initial)`（`live.set()` 在 `sender.start()` 前、race-safe）、刪 `_keepalive_loop`、`_send_loop` 加靜音分支、`disarm` dict 版。單一 commit `ea0bd57`；627 綠（35 stt + 592 sales，無增減）；spec-reviewer ✅ + code-quality ✅（查證 flag-before-start race-safe、join 在 lock 外無死鎖、來源端 mute 真實不送）。**Pi 實測（2026-06-17）辨識變不准 + prewarm 無感 → 連同 v2 全 revert（見下）。**
- **❌ v2+v3 全 revert，STT 定版 Phase 1（2026-06-17 Pi 實測）**：v3 辨識變不准（有講沒錄進 / 錄進但轉換錯誤），且播完仍不能馬上講。根因兩條：① **ch0 處理後聲道反而降 ASR 準確度**——ReSpeaker ch0 經 beamforming/NS「聲音怪怪的」，Deepgram 對它的辨識率低於 Phase 1 的 `-c 1` mono 降混（使用者實證：最穩定版本是未導入 ch0 的 Phase 1）；② **prewarm 無感且延遲為結構性**——開麥（arm）刻意排在 `wait_idle`（TTS 播完含 ALSA drain）之後（無 AEC 必然設計），prewarm 只省 ws 連線/arecord spawn 的微小成本，殘留延遲 = Deepgram endpointing(300ms)+轉錄，非 prewarm 可解。→ 4 檔（`stt.py`/`main.py`/`test_worker.py`/`test_main_wireup.py`）restore 至 `e15167a`，`git diff e15167a` 為空（逐位元對齊已驗證的 Phase 1）；`6b20e7f`；621 綠。ch0/prewarm 的 spec/plan 留存為歷史（不刪）。**STT 定版 Phase 1**：`-c 1` mono 降混、`wait_idle` 後才 `arm` 開麥。
- **🔬 prewarm 不加 ch0（spec/plan `63217b6`）**：使用者觀察「ch0 才是辨識元凶、prewarm 機制本身無回授」→ 隔離變數,**只取 v2 式 prewarm、保留 Phase 1 `-c 1` mono（不加 ch0）**。`prewarm()` 在 prompt 播放期背景連 ws + KeepAlive 維持(**不開麥不送音訊**)、`read_customer_input` 在 `wait_idle` **前**呼叫；`arm()` 兩段(確保連線 → `sending` Event 停 KeepAlive → 開 arecord+sender)。目的:把 ws 握手(~0.2–0.5s)藏進播放期、不犧牲準確度(殘留 endpointing 延遲仍結構性、不處理)。機制照已證 v2 `d8c8d77`、音源照 Phase 1(無 ch0)。單一 commit `44ad113`；621→625 綠(+4 prewarm 測試)；spec-reviewer ✅ + code-quality ✅(查證 prewarm 期不送音訊、arm handoff race-free、join 在 lock 外)。**待 Pi 實測**:辨識仍正常 + 播完到能講有無變跟手。
- **🔬 診斷計時 instrumentation（spec/plan `1674af5`）**：Pi 實測回報「播完後有時等好幾秒才能輸入」,代碼排查顯示 arm 只比聲音結束晚 ~0.4s（drain+spawn）、非好幾秒 → 加 **env-gated `[計時]` log**（`STT_DEBUG_TIMING=1` 才印,預設關）量測 prewarm / wait_idle / arm→輸入 / 單句 TTS（快取或合成）四段耗時,使用者跑一次即可定位卡在 synth / Deepgram 哪段。純 additive、旗號未設零行為改變;`main.py`+`tts.py`,`0148041`；625 綠不變。小改動跳 formal reviewer（主 agent 全 diff 自審 + Iron Law）。Pi `[計時]` 數據:prewarm 0.5s(無感)、wait_idle 2.6–9s(機器人在講話)、arm→輸入 1.9–5.2s(你開口+Deepgram)→ 卡頓非開麥時機,而是**辨識錯誤觸發「聽不懂」重講迴圈**。
- **🔬 改抽單一 raw 麥克風聲道（spec/plan `676d21b`）**：`[計時]` 證實卡頓源自辨識錯誤——`-c 1` 降混(6 軌平均,含處理後 ch0 + 播放參考 ch5)音質糊,Deepgram 把「刮刮樂五張」聽成「25/八二五張」(量詞`張`對、產品`刮刮樂`糊成數字)。→ 改 `arecord -c 6` 抓原生 6 軌、抽**單一 raw 麥克風軌**(`_extract_channel` 通用化自 reverted `_extract_ch0`,預設 ch1;ch0 處理後軌已剔除)餵 Deepgram;聲道由 `STT_MIC_CHANNEL` env 可設(非法/越界 fallback ch1),供實測掃 ch1-4 找最清楚軌。只動 `stt.py`+`test_worker.py`(prewarm/Deepgram 參數/main.py 不動)。`f7b16ab`；625→629 綠(+4 抽軌測試);spec-reviewer ✅ + code-quality ✅(查證抽軌數學 round-trip、邊界 fallback、尾幀丟棄無累積誤差、surgical)。Pi 實測:掃 ch1-4 單軌「很難分辨」、訊號比多麥降混弱 → 不如降混。
- **❌ 退回 `-c 1` plughw 全麥降混（定版音源；2026-06-17 Pi 實測）**：單一 raw 麥軌(ch1-4)訊號弱、使用者「很難分辨」,實測不如 `plughw -c 1` 全麥降混(多麥拾音、訊號最強)。→ `stt.py`/`test_worker.py` restore 至 `62e31c6`(prewarm + 計時 log 保留、**僅音源退回降混**),`git diff 62e31c6` 為空;`4301a55`;629→625 綠(移除 4 抽軌測試)。**STT 音源定版 `plughw -c 1` 全麥降混**——聲道試驗收斂:ch0 處理後軌降準確度、單一 raw 麥軌訊號弱,**皆不如全麥降混**。難詞(刮刮樂)若仍不足 → 下一步攻 keyterm/Deepgram 參數(非聲道)。**Pi 端**:裝置須改回 `STT_ARECORD_DEVICE=plughw:CARD=ArrayUAC10`(`-c 1` 降混需 plughw、非 hw)。
- **✅ 暖機 arecord 消開麥裁切（spec/plan `cfaea44`）**：`[計時]` + 使用者實測定位**真因**——arecord 在 `arm`（語音播完）才 spawn,USB 冷啟 ~200–400ms,顧客一播完開口的**開頭被裁掉**（刮刮樂掉「刮」→ 聽成「25/八二五張」,先前以為是聲道/降混問題,其實是開麥裁切）。修:prewarm keepalive-based → **silence-based**——arecord 提前到 `prewarm` 暖機錄音、mute 期 sender 送等長靜音（機器人聲收進卻不送 Deepgram → 無回授、靜音維持連線取代 KeepAlive）、`arm` 翻 `live` 旗號即切真實 → arecord 已暖 + 即時抽乾（pipe 鎖步維持淺）→ **開麥零裁切、零積壓、低延遲**。音源維持 `-c 1` 降混（不碰 ch0/抽軌）。`_open_ws`→`_start_session(live_initial)`（race-safe `live.set` 在 `sender.start` 前）、刪 `_keepalive_loop`、`disarm` dict 版;順手修 `main.py` 因機制變更而 stale 的 prewarm 註解。`cf284c3`;625 綠;spec-reviewer ✅ + code-quality ✅（查證 race-safe gate、lockstep 無積壓、join 在 lock 外、靜音取代 KeepAlive）。**Pi 實測（2026-06-17）反而「收不到音」**——「lockstep 無積壓」假設在真硬體不成立:暖機期 arecord 累積的播放期舊音在 arm 被當真實送出 → 顧客真實語音被埋 / Deepgram 搶先返回舊音結果 → `read_customer_input` 提早返回 → revert（見下）。
- **❌ 放棄 prewarm、退回 pure Phase 1（2026-06-17 Pi 實測，架構性結論）**：prewarm **三輪皆 Pi 實測失敗**——v1 自我回授、warm-arecord（v3 式）暖機積壓「收不到音」、keepalive 版未改善辨識。**架構性問題 → 放棄 prewarm**。4 檔（`stt.py`/`main.py`/`test_worker.py`/`test_main_wireup.py`）restore 至 `e15167a`（pure Phase 1:無 prewarm、`-c 1` plughw 降混、arm 才開麥），`git diff e15167a` 為空（逐位元對齊使用者確認「辨識正常」的版本）;`4fdd9fa`;625→621 綠。**STT 定版 pure Phase 1**。剩餘難詞（刮刮樂）若不足 → 下一步攻 keyterm / Deepgram 參數（prewarm、聲道皆已窮舉剔除）。
- **✅ STT 階段定案（2026-06-17）**：採用 **pure Phase 1**;**開麥裁切**（arecord 冷啟 ~300–500ms、搶快講掉開頭,warm-arecord 修法失敗）→ **接受**,**Demo 操作 = 提示音播完停 ~0.5s 再答**避裁切（記於 roadmap）。移除遺留 `[計時]` 診斷 log（`tts.py`,`d25aea8`）→ myProgram 內 `STT_DEBUG_TIMING`/`[計時]` 全清。STT 探索全程（barge-in/AEC、prewarm 三輪、聲道三軌）收斂記錄於本里程碑 + memory `respeaker-mic-array-v2`,避免重走。難詞精修（keyterm/Deepgram 參數）留待 demo 真需要再開。

## 架構 / 流程沉澱
- 新模組：`myProgram/stt/`（Deepgram 串流 worker）、`myProgram/sales/phonetic.py`（拼音近音糾錯，pypinyin 注入 + graceful）。
- `parse_products` = 統一 token-parser（精確商品 span + 數量 span + phonetic garbled 兜底 + 鄰近綁定 + dedup 規則 1/2/3）。
- 新依賴（Pi，記於 `requirements/raspberry_pi_setup.md`）：pypinyin（拼音糾錯）、Deepgram（STT，需 API key）。
- 反思採納：cwd-pinned worktree Option B（`worktree.md`）、cp936 中文輸出探針設 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`（`conventions.md`）。

## 下一步（pending）
- ~~STT barge-in Phase 2 / turn-taking / 聲道試驗 / prewarm 三輪~~：全試過皆收斂 → **STT 定案 pure Phase 1**（見里程碑 6）；開麥裁切接受、demo 以「播完停 0.5s 再答」應對。難詞精修（keyterm/Deepgram 參數）demo 真需要再開。
- **HTML UI**（`roadmaps/html_ui_plan.md`）｜**期末 demo 準備**（`presentation/` 尚空）。
- deferred edges（已記 watchlist W-14~17 / roadmap）：C1 無分隔雙數量、C3 插字 garble、C4 合音表擴充、D4 daemon warning、D3 通用快取清理工具——demo 真踩到再修。
