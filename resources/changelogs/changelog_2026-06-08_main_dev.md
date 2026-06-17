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
- **🔬 診斷計時 instrumentation（spec/plan `1674af5`）**：Pi 實測回報「播完後有時等好幾秒才能輸入」,代碼排查顯示 arm 只比聲音結束晚 ~0.4s（drain+spawn）、非好幾秒 → 加 **env-gated `[計時]` log**（`STT_DEBUG_TIMING=1` 才印,預設關）量測 prewarm / wait_idle / arm→輸入 / 單句 TTS（快取或合成）四段耗時,使用者跑一次即可定位卡在 synth / Deepgram 哪段。純 additive、旗號未設零行為改變;`main.py`+`tts.py`,`0148041`；625 綠不變。小改動跳 formal reviewer（主 agent 全 diff 自審 + Iron Law）。**待 Pi `STT_DEBUG_TIMING=1` 跑一次貼 [計時] 輸出定位**。

## 架構 / 流程沉澱
- 新模組：`myProgram/stt/`（Deepgram 串流 worker）、`myProgram/sales/phonetic.py`（拼音近音糾錯，pypinyin 注入 + graceful）。
- `parse_products` = 統一 token-parser（精確商品 span + 數量 span + phonetic garbled 兜底 + 鄰近綁定 + dedup 規則 1/2/3）。
- 新依賴（Pi，記於 `requirements/raspberry_pi_setup.md`）：pypinyin（拼音糾錯）、Deepgram（STT，需 API key）。
- 反思採納：cwd-pinned worktree Option B（`worktree.md`）、cp936 中文輸出探針設 `PYTHONIOENCODING=utf-8 PYTHONUTF8=1`（`conventions.md`）。

## 下一步（pending）
- ~~STT barge-in Phase 2~~ / ~~Phase 2 turn-taking~~：真搶話經 AEC 收掉；ch0 經實測降準確度已剔除（見里程碑 6）。**現況：Phase 1 `-c 1` mono + v2 式 prewarm（不含 ch0）已實作**，待 Pi 實測 prewarm 跟手度（辨識正常已確認）。
- **HTML UI**（`roadmaps/html_ui_plan.md`）｜**期末 demo 準備**（`presentation/` 尚空）。
- deferred edges（已記 watchlist W-14~17 / roadmap）：C1 無分隔雙數量、C3 插字 garble、C4 合音表擴充、D4 daemon warning、D3 通用快取清理工具——demo 真踩到再修。
