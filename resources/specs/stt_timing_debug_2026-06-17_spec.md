# STT 互動延遲診斷計時 instrumentation spec

> 2026-06-17。使用者 Pi 實測:prompt 播完後「有時要等好幾秒才能輸入語音」,但無法判斷卡在哪段。本案加 **env-gated `[計時]` log** 量測三個邊界,使用者跑一次即可定位(synth / wait_idle / arm→辨識)。**診斷工具,非功能變更**;`STT_DEBUG_TIMING` 未設時零輸出、零行為改變。

## 1. 背景與動機
延遲鏈路(見 changelog 里程碑 6 / 本輪排查):`[語音]` 入列 →〔合成 cache miss 才有〕→ 播放 → `wait_idle` 返回(+0.3s drain)→ `arm` 開麥(`timeout=N`)→ 你講 → Deepgram `[語音辨識]`。代碼分析顯示 arm 只比聲音結束晚 ~0.4s,故「好幾秒」必在 (a) 合成 (b) Deepgram 辨識 其一。需實測數據定位 → 加計時 log。

## 2. 設計核心 + 行為規約
**單一增量**:env `STT_DEBUG_TIMING` 為真才印 `[計時] ...`(monotonic 秒差)。三個量測點:

| 量測 | 位置 | log |
|---|---|---|
| 單句 TTS 處理(含合成) | `tts.py` `_process` | `[計時] TTS '<前8字>': <快取/合成>播放 共 N.NNs` |
| wait_idle 耗時(=TTS 合成+播放+drain) | `main.py` `read_customer_input` | `[計時] wait_idle N.NNs` |
| arm→輸入返回(=你開口+Deepgram 辨識) | `main.py` `read_customer_input` | `[計時] arm→輸入 N.NNs` |

- 旗號讀取:`os.environ.get("STT_DEBUG_TIMING")`(call/進入時讀,不在 import 時固化)。
- 未設旗號 → 完全不印、無任何行為差異(prod/demo 乾淨)。
- 不新增 module(inline 旗號檢查,避免結構變動);不動 stt.py(arm→輸入 已涵蓋 Deepgram 段,若需細分另案)。

## 3. 改檔範圍
| 檔 | 改動 | 行數估 |
|---|---|---|
| `myProgram/tts.py` | `_process`:量測總耗時 + 標記快取/合成,env-gated print | ~6 |
| `myProgram/main.py` | `read_customer_input`:量測 wait_idle 與 arm→輸入,env-gated print | ~8 |

## 4. Out of scope
任何延遲「修復」(本案只量測,定位後另案修)｜stt.py 細分 Deepgram vs 開口時間（arm→輸入 夠定位 bucket）｜新 module / 設定檔｜sales/vendor。

## 5. 規範與參考
- 派 sales-coder;預載 karpathy。`tts.py` 已 import `os`/`time`;`main.py` 確認 import `os`/`time`(缺則補)。
- 旗號字串統一 `STT_DEBUG_TIMING`。print 繁中、`[計時]` 前綴(對齊既有 `[語音]`/`[語音辨識]` 風格)。

## 6. 測試指令 + 預期
```
python -m pytest tests/stt/ tests/sales/
```
預期:**625 全綠不變**(instrumentation env-gated,測試環境未設旗號 → 零行為差異;不新增測試——純診斷 log,無行為可斷言)。grep `STT_DEBUG_TIMING` 在 tts.py+main.py = 各 ≥1。

## 7. Commit 規範
單一 commit:`feat(stt): env-gated [計時] 診斷 log（定位互動延遲卡段）`;`git add myProgram/tts.py myProgram/main.py`。worktree 首 commit = 本 spec。

## 8. 流程鳥瞰
```
[approval] → sales-coder → Iron Law（pytest 625 + grep）→ 主 agent 自審 diff（小改動跳 spec-reviewer）
          → code-quality（輕）→ ExitWorktree → ff-merge → push → Pi sync
          → 使用者 STT_DEBUG_TIMING=1 跑一次 → 貼 [計時] 輸出 → 定位 → 另案修
```
