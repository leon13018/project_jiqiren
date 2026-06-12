# STT 導入 + barge-in 搶話 — 統領設計（Deepgram Nova-3 串流）

> 2026-06-12 brainstorming 定案。本檔為兩 Phase 的統領設計；各 Phase 實作時另開 `stt_p<N>_<date>_spec.md` + plan 走完整 SDD 循環。
> **最高判準（user 原話）：極致的效能、超低的延遲、最先進的技術、最快的算法**——後續所有實作取捨以此為先。

## 1. 背景與動機

- roadmap「下一步候選」STT ⭐ 首選；S6 input queue 前置已就緒。
- user 條件：延遲 <1s（講完→拿到字）、免費額度（總用量 ≤1-2hr）、展示現場網路穩定、zh-TW 短句點餐指令。
- 選型結果（2026-06-12 多方搜尋比較 Google/Azure/Groq/Deepgram/vosk）：**Deepgram Nova-3 串流**——Mandarin Traditional 模型直出繁體、官方串流延遲 <300ms、註冊送 $200（≈200hr+，免綁卡）、純 websocket 無原生依賴（避開 Buster GLIBC/piwheels 雷區）。
- 硬體：廠商套件 **ReSpeaker Mic Array V2**（USB；4 麥陣列 + XMOS XVF-3000 DSP：AEC/波束成形/去混響/降噪/AGC；規格檔 `resources/userPrompt/ReSpeakerMicArrayV2語音模組.md`，gitignored）。
- **AEC 選型結論**：迴聲消除交給 XVF-3000 硬體（同晶片同時鐘域、零主機 CPU、零附加延遲），不自跑軟體演算法（WebRTC AEC3/DTLN-aec 為實測不堪用時的升級保留項，預期用不到）。

## 2. 設計核心與行為規約

### 2.1 資料流（end state＝Phase 2 完成後）

```
狀態機進入新階段 → speak(ack)/speak(提示)/do_action(手勢) 照常進佇列（不變）
  → TtsWorker 開播首段：算 mp3 長度 D，0.25×D 時觸發 on_arm_point → stt.arm()（冪等）
  → 顧客講話：ReSpeaker AEC 消機器人自聲 → arecord PCM → Deepgram ws → speech_final
  → 文字（去頭尾標點空白）→ input_reader.inject() → 既有單一 input queue
  → main.py 讀取 callback（反轉）：播放期間即輪詢（0.1s 間隔）
      ├─ 播放中拿到輸入 → tts.interrupt()（瞬切）+ action.preempt()（軟停）
      │   → 文字立即交狀態機 → 正常狀態轉移（只是提早）
      └─ 播完無輸入 → 倒數計時照現狀（timeout 從播完起算，既有 UX 不變）
```

### 2.2 行為規約

| 項目 | 規約 |
|---|---|
| 開麥點 | 階段**首段**語音播放至 0.25×D（D=該 mp3 實長）；算不出 D → 退化為開播後 1s；讀取點進入時 TTS 已空閒 → 直接 arm |
| arm 範圍 | 僅顧客對話等待點（L2–L4 與跨層 confirm）；商家層（主選單/hawk `read_terminal_key`）純鍵盤不 arm |
| disarm 時機 | 輸入被消費或等待 timeout |
| 搶佔語意 | TTS 砍當前 mpg123＋清佇列（`_pending` 逐項對齊）；動作**只清佇列**、進行中手勢自然做完、**不碰 vendor stopAction**（sticky 雷區整個繞開） |
| 輸入一視同仁 | 鍵盤打字在播放中到達走同一搶佔路徑（單 queue、producer 端零分流） |
| 倒數 UX | 播放中無倒數打印；播完才開始倒數（wait-then-count 既有設計保留） |
| 提前處理語意 | 早到輸入觸發**既有**狀態轉移，無特殊跳層 |

### 2.3 延遲預算

| 路段 | 預算 | 手段 |
|---|---|---|
| ws 連線建立（~200-300ms） | **不佔關鍵路徑** | 藏在 25% 開麥點之後的播放期間 |
| 顧客講完 → speech_final | **<1s（驗收線）** | Deepgram 串流（官方 <300ms）+ endpointing |
| 輸入到達 → TTS 瞬切 | <200ms | 0.1s 輪詢 + mpg123 terminate |
| AEC | ≈0ms、零 Pi CPU | XVF-3000 硬體管線 |

### 2.4 回授防線（疊層；下層實測漏了才啟用上一級）

1. **XVF-3000 硬體 AEC**（主防線）——硬前提：TTS 播放改走 ReSpeaker 輸出（mpg123 指定其 ALSA 裝置、喇叭接其 3.5mm），DSP 才有參考訊號。
2. 文字相似度回聲過濾（應變項，預設不做）：辨識結果 ≈ 正在播放句子的前綴 → 丟棄。
3. speexdsp / DTLN-aec 軟體輔助（升級保留項，預期用不到）。

### 2.5 元件介面（檔案級）

| 檔 | 增量 | 要點 |
|---|---|---|
| `myProgram/stt.py`（新） | `SttWorker` | daemon thread + 常駐 asyncio loop（tts.py 同 pattern）；API：`arm()`/`disarm()`/`shutdown()`；建構子注入 `sink`、`api_key`、音源 factory、ws factory（測試替身）；管線 arecord stdout PCM → ws → `speech_final` → `sink(text)` |
| `myProgram/input_reader.py` | `inject(text)` | 公開注入點（`self._q.put(text)`）；STT 與鍵盤共用單 queue |
| `myProgram/tts.py` | `interrupt()`、25% timer | interrupt：砍當前 mpg123＋清佇列＋`_pending`/Condition 逐項對齊（race 敏感，必派 sales-coder TDD）；播放前以 duration provider（mutagen **lazy import**＋可注入，結果按 hash 快取）排 `threading.Timer(0.25×D)` 觸發 `on_arm_point`，interrupt/shutdown 時 cancel |
| `myProgram/action.py`/`queue_worker.py` | `preempt()` | 呼叫既有 `drain_queue`；不碰 vendor API |
| `myProgram/main.py` | wire-up＋讀取反轉 | 建 SttWorker、註冊 on_arm_point、arm/disarm 呼叫點、`read_customer_input` 播放中輪詢與搶佔、shutdown 鏈加入 stt（`os._exit(0)` 前） |

Deepgram ws 參數：`model=nova-3`、`language=zh-TW`、`encoding=linear16`、`sample_rate=16000`、`channels=1`、`interim_results=true`（僅消費 `speech_final`）、`endpointing=300`（ms；過短會把句中停頓切成兩句，Phase 1 實測調定）；`smart_format` 初版關閉（防數字格式干擾 qty 解析，實測後再議）。
arecord：`arecord -D <ReSpeaker裝置> -f S16_LE -r 16000 -c 1 -t raw`。
秘密：`DEEPGRAM_API_KEY` 環境變數（Pi 端設定），**絕不進 repo**。

### 2.6 錯誤處理矩陣（原則：STT 壞 ≠ 系統壞，鍵盤永遠可用）

| 故障 | 處理 | 顧客感知 |
|---|---|---|
| 缺 key / 401 | 啟動 log 警告，本次執行停用 STT | 純鍵盤模式照跑 |
| ws 建線失敗 | 重試 1 次→放棄本會話；下次 arm 再試 | timeout 既有 reprompt 兜底 |
| ws 中途斷線 | 同上（該句丟失） | 同上 |
| arecord 死亡 | EOF 偵測自動重啟（有限次） | 最多丟一句 |
| 空白/雜訊辨識 | 空字串不注入；聽不懂走既有 unclear reprompt | 既有文案 |
| 算不出 mp3 長度 | 該段退化 1s 開麥 | 無感 |

## 3. Phase 切分與改檔範圍（高層）

> 每 Phase 各走完整 SDD（worktree → spec/plan → approval → sales-coder → 三段審查 → 實機測通過才下一 Phase）。incremental 鐵則：每步一個變數。

**Phase 1 — STT 基礎（播完才聽）**：`stt.py` 新檔（~180 行）、`input_reader.py` +inject（~5）、`main.py` wire-up＋顧客等待點 arm/disarm（~30，arm 時機暫為 `wait_idle` 後）、`tests/stt/` 新測試。驗證音訊鏈/延遲/繁體/NLU 命中。
**Phase 2 — barge-in**：`tts.py` interrupt＋25% timer（~60）、`action.py`/`queue_worker.py` preempt（~15）、`main.py` 讀取反轉（~40）、tests 擴充。TTS 改線啟用 AEC。
（Phase 3 保留位：手勢硬停 vendor stopAction——目前不做。）

## 4. Out of scope（明示不動）

商家層語音／hawk 叫賣期間收音｜DOA 轉頭｜喚醒詞｜vosk 本地備援｜OpenCC 簡轉繁（應變項）｜回聲文字過濾（應變項）｜vendor stopAction 硬停｜`sales/` 狀態機任何改動（零 diff 是硬約束）。

## 5. 規範與參考

- 實作一律派 sales-coder（worker 結構改動為 sales-tts-ux.md 明文教訓）；預載 karpathy-guidelines。
- 必讀 reference：`myprogram-threading-paths.md`（asyncio in thread／單 queue／daemon shutdown 教訓）、`sales-tts-ux.md`（`_pending`/Condition 原語、wait-then-count）、`incremental-rebuild.md`（單 queue 權威、sticky 旗號權威）。
- 既有 regression 必須原樣通過（含 `test_read_terminal_key_does_not_call_wait_idle`）。

## 6. 測試與驗收

- Windows：`python -m pytest tests/`——既有 516 全綠＋新增 `tests/stt/`（fake 音源/ws：arm 冪等、speech_final 過濾、重試、interrupt 計數一致、timer 取消、讀取反轉、preempt、NLU 煙霧測試）。mutagen 必 lazy import（Windows 不裝依賴紅線）。
- Pi Phase 1 驗收：10 句點餐短句 ≥8 句正確進 NLU；講完→speech_final 體感 <1s；繁體抽查。pineedtodo：pip `websockets`+`mutagen`、`arecord -l` 驗 ReSpeaker、設 API key。
- Pi Phase 2 驗收：(a) 25% 後插話→語音瞬切/手勢做完/直入下一層；(b) 聽完不插話→倒數與現狀逐字相同；(c) 無人講話→不得自我觸發。pineedtodo：mpg123 改線 ReSpeaker、AEC 體檢（播放中錄音殘留明顯衰減）。
- **使用者前置行動**：註冊 Deepgram 取得 API key（可與 Phase 1 實作並行）。

## 7. Commit 規範

各 Phase worktree 首 commit = 該 Phase spec+plan；實作 commit `feat(stt): ...`／`feat(tts): ...` 繁中描述；git add 明列檔名（紅線）；收尾同步 roadmap.md STT 列、`myProgram/.claude/code_map.md`（stt.py 新檔）、changelog。

## 8. 流程鳥瞰

```
[design 核可] → Phase 1 SDD（spec/plan→approval→sales-coder→3 段審→merge→push→Pi 實測）
            → 驗收過 → Phase 2 SDD（同循環）→ 驗收過 → roadmap/code_map/changelog 收尾
```
