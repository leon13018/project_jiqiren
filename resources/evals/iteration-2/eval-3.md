# Iteration-2 transcript — eval 3 (threading cluster), model=opus

> round-2 去噪後（threading-paths 去「最終穩定設計 commit 9931605」SHA 戳 + subagent 偏離 meta；incremental-rebuild 去 3 個 2026-05-23 日期戳 + 歷史 commit a95507f/legacy README 指標。vendor 已純淨未動。Part A 約束/Part B 路徑/Part C 4 教訓/單 queue+sticky canonical 範例全留）。場景同 baseline eval-3。

## Navigator 回覆（摘要）
分四類已知坑：
1. 執行緒架構（Part A）：blocking 全推背景；asyncio worker 用 `asyncio.run` 非 `get_event_loop`（tts.py:164 範本）；subprocess 別 fire-and-forget。
2. 單 queue 鐵則（incremental §單 queue 權威）：STT 結果丟單一 queue、producer 端不分流（引用 cmd/customer/has_customer 分流踩雷 canonical 範例）；禁旗號分流；queue.Queue + Event、不手動 Lock。
3. 並行語意（S-step 哲學）：預設 FIFO 不中斷（中斷=S7 反模式）；STT↔TTS 自我回授用自寫 Event gate；polling cadence caller-specific（教訓 1）。
4. 生命週期/shutdown（Part C 4 教訓同構）：daemon 不保證 finalizer 不卡 lock；別主動 unblock blocking read（教訓 4 close deadlock）；shutdown 只清 queue + `os._exit(0)`；三 worker shutdown 對稱（加 stt.shutdown）。
- 流程：屬新 worker + main wire-up 中大改 → 必走 SDD + 派 sales-coder + incremental S 步每步實機測。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：threading-paths.md → incremental-rebuild.md（router 同批命中）→ 2 層 code_map → tts.py → input_reader.py（落地真實 pattern，reference 未要求）。
- reference→reference：否（合理分工）。router 對「多線程 worker」同時點名 threading-paths + incremental-rebuild；threading 結尾亦 cross-link。
- 缺漏（pre-existing，非去噪造成）：(1) STT↔TTS 自我回授坑兩檔皆未明列（只能從「狀態邊界清楚」原則推導）；(2) 麥克風輸入裝置選型無前例；(3) router 無 STT 專屬列。
- 與 baseline 差異：本輪未顯式提 Linux 絕對路徑（assertion 5）與 pycache（assertion 4）——前者 Part B 內容仍完整在檔、屬 navigator 取捨；後者本不在 cluster 3 檔內（baseline 亦未提），非退化。
