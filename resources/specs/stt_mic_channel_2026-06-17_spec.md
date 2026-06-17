# STT 單一 raw 麥克風聲道（env 可設定）spec

> 2026-06-17。基線 = main `62e31c6`（Phase 1 `-c 1` mono 降混 + v2 式 prewarm + 計時 log）。Pi 實測:`-c 1` 降混音質糊,Deepgram 把「刮刮樂五張」聽成「25張/八二五張」(難詞糊掉)。改抽**單一 raw 麥克風聲道**(乾淨、未處理、未平均)餵 Deepgram,聲道編號 env 可設定以便實測掃出最佳麥。

## 1. 背景與動機

聲道試驗史(changelog 里程碑 6):**ch0 處理後聲道** → 更差(beamforming/NS 失真,已剔除);**`-c 1` plughw 降混**(現行)→ 把 6 軌(含處理後 ch0、播放參考 ch5)**平均**成一軌 → 偏糊,簡單詞 OK、難詞(刮刮樂)糊掉被聽成數字。**從沒試過單一 raw 麥克風聲道**(ch1-4,純麥克風訊號)。

本案:`arecord -c 6` 抓原生 6 軌、抽**單一 raw 聲道**(預設 ch1)餵 Deepgram。聲道編號由 `STT_MIC_CHANNEL` env 決定(預設 1),使用者一個 session 設一值掃 ch1→2→3→4 找「刮刮樂」最清楚的軌,定案後寫死預設。只換 Deepgram 收到的音訊軌,**其餘全不動**(prewarm / send-recv / Deepgram 參數 / keyterm 不變)。

> 與 ch0 的差異:ch0 = 處理後軌(`_extract_ch0`,失真);本案 = 生麥克風軌(`_extract_channel`,未處理)。同抽軌手法、不同來源軌。

## 2. 設計核心 + 行為規約

**單一增量**:音源工廠 `-c 1` 降混 → `-c 6` 原生 + 抽指定聲道。

- `_CHANNELS = 6`(常數);`_DEFAULT_MIC_CHANNEL = 1`(預設第一支生麥;ch0=處理後已知爛、ch5=播放參考勿用)。
- `_extract_channel(buf, channel, channels=_CHANNELS)`:交錯 S16 buffer 反交錯抽第 `channel` 軌(每幀第 channel 個 16-bit 樣本);不完整尾幀丟棄。
- `_mic_channel()`:讀 `STT_MIC_CHANNEL` env → int;未設/非法/越界(非 0..5)→ fallback `_DEFAULT_MIC_CHANNEL`。
- `_ArecordSource(proc, channel)`:`read(n)` 讀 `n*_CHANNELS` bytes(6ch 交錯)→ 抽 `channel` 軌 → 回 n bytes mono。
- `_default_audio_factory`:`arecord ... -c 6 ...`(取代 `-c 1`)+ 傳 `_mic_channel()` 給 `_ArecordSource`。
- **不動**:`SttWorker`(prewarm/arm/keepalive/send/recv/disarm)、`main.py`、Deepgram URL/keyterm、計時 log。

| 場景 | 行為 |
|---|---|
| 未設 STT_MIC_CHANNEL | 抽 ch1(第一支生麥) |
| STT_MIC_CHANNEL=2/3/4 | 抽對應生麥(實測掃描用) |
| 非法值(abc / 9 / -1) | fallback ch1(不炸) |
| arecord 讀 6ch | 抽 1 軌 mono → Deepgram(粒度同舊:read(3200)→讀 19200 抽 3200) |

## 3. 改檔範圍

| 檔 | 改動 | 行數估 |
|---|---|---|
| `myProgram/stt.py` | 加 `_CHANNELS`/`_DEFAULT_MIC_CHANNEL`/`_extract_channel`/`_mic_channel`;`_ArecordSource.__init__`+`read` 改(抽軌);`_default_audio_factory` 改 `-c 6`+傳 channel | ~30 |
| `tests/stt/test_worker.py` | 更新 `test_default_audio_factory_command`(`-c 1`→`-c 6` + channel);加 `_extract_channel` / `_mic_channel` / `_ArecordSource` 抽軌測試 | ~40 |

`main.py` / `test_main_wireup.py`:**不動**。

## 4. Out of scope

ch0 處理後軌(已剔除)｜保留降混 fallback(不做,直接換單軌)｜Deepgram 參數 / keyterm 調校(另案,若換軌仍不準再議)｜prewarm / 計時 log(不動)｜多軌融合 / 自製 beamforming｜`sales/` / `vendor/`。

## 5. 規範與參考

- 派 sales-coder;預載 karpathy。
- **手法參考**:reverted 的 `_extract_ch0`(commit `cc61647`/`a908209`)= 本案 `_extract_channel` 的特例(channel=0);本案通用化 + 生麥預設。
- 既有 reuse:`tests/stt/conftest.py`(`FakeWs`/`wait_until`);`_extract_channel` 純函式可直接單元測(struct.pack 造 6ch buffer)。
- **Pi 端**:裝置 env 改回 `STT_ARECORD_DEVICE=hw:CARD=ArrayUAC10`(原生 6ch,`-c 6` 需要;ch0/v2 證實可行)。`STT_MIC_CHANNEL=1` 起掃。喇叭插樹莓派板載。無新依賴。

## 6. 測試指令 + 預期

```
python -m pytest tests/stt/ tests/sales/
```
預期:sales 592 + stt(625 基線 - 0 + 新增抽軌測試)全綠。`test_default_audio_factory_command` 改為驗 `-c 6`。Windows 全 fake。

## 7. Commit 規範

- commit 1(code):`feat(stt): 改抽單一 raw 麥克風聲道（-c 6 + STT_MIC_CHANNEL，取代 -c 1 降混）`;`git add myProgram/stt.py tests/stt/test_worker.py`。
- commit 2(docs,收尾):roadmap/changelog/pineedtodo(掃聲道實測)。
- worktree 首 commit = 本 spec + plan。

## 8. 流程鳥瞰

```
[approval] → commit spec/plan → sales-coder → Iron Law（pytest+branch+grep -c 6）
          → spec-reviewer → code-quality → 收尾:roadmap/changelog + pineedtodo（掃 ch1-4）
          → ExitWorktree → ff-merge → push → Pi sync
          → Pi 實測:STT_ARECORD_DEVICE=hw: + STT_MIC_CHANNEL=1..4 各測「刮刮樂五張」,回報哪軌最清楚 → 寫死預設
```
