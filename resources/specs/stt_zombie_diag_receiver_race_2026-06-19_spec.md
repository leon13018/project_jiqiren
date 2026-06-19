# STT 殭屍連線診斷埋點 + receiver-start race 修復 — SDD spec

**日期：** 2026-06-19
**類型：** 診斷埋點（measurement）+ 併發 race 修復（`myProgram/stt.py`）

## 背景

Pi 實測（2026-06-19）兩發現：
1. **開頭裁切**已確診（搶快講掉「紅茶」字頭、停頓後 3/3 全中）——warm-arecord 修法另案，本 spec 不做。
2. **殭屍連線 bug（頻繁）**：跑幾輪後某輪「一直講零辨識 → 12s timeout 自動結帳」，且**無重連**（連線被誤認還活著）。兩個嫌疑、修法相反，**先診斷再修**：(A) 連線殭屍（Deepgram 停回應）vs (B) arecord 退化（吐靜音）。

另 `proposals.md` pending 反思 `receiver-start-after-lock-race`（本 spec 落實後改 adopted）：`_ensure_connected` 在 `_lock` 內存 `self._receiver` 但釋鎖後才 `receiver.start()`；shutdown 若在此窗 `join()` 未 start 的 thread → `RuntimeError: cannot join thread before it is started`。

## Part A — 殭屍診斷埋點（`_receive_loop`，env-gated）

`STT_TTS_TIMING` 設時，receiver 把**收到的每一則 Deepgram 訊息**印出（含 interim 即時辨識，現狀只處理 speech_final、interim 被早 continue 掉看不到）。用以判定殭屍輪：有 interim 文字 = Deepgram 聽得到（(B) 嫌疑）；完全無訊息 = 連線真殭屍（(A)）。

`_receive_loop` 內層 try、`data = json.loads(msg)` 之後、現有 speech_final 過濾**之前**插入：
```python
                    data = json.loads(msg)
                    _typ = data.get("type")
                    if _typ == "Results":
                        _alts = data.get("channel", {}).get("alternatives", [])
                        _txt = _alts[0].get("transcript", "") if _alts else ""
                        _timing(f"Deepgram Results final={data.get('speech_final')} cap={self._capturing} '{_txt}'")
                    elif _typ:
                        _timing(f"Deepgram {_typ}")
                    if data.get("type") != "Results" or not data.get("speech_final"):
                        continue
```
（`_timing` 自帶 env 閘門；未設 → 零輸出、零行為改變。）

## Part B — receiver-start race 修復（`shutdown`）

`shutdown` 的 join 迴圈加 `is_alive()` 守衛——未 start 的 thread `is_alive()` 為 False → 跳過 join，不 `RuntimeError`；已 start 者照 join。

改前：
```python
        for th in (receiver, keepalive):
            if th is not None:
                th.join(timeout=1.0)
```
改後：
```python
        for th in (receiver, keepalive):
            if th is not None and th.is_alive():
                th.join(timeout=1.0)
```

> 為何 is_alive 守衛優於「start 移到存 ref 前」：若 shutdown 搶在存 ref 與 start 之間，它已在 `_lock` 內讀到 `conn_stop` 並 `set()`；隨後 `_ensure_connected` 才 `start()` 的 receiver/keepalive 一啟動即見 `conn_stop` 已 set → 立即退出，不留孤兒。守衛只擋「join 未 start thread」的 RuntimeError，其餘自洽。

## 行為不變式
- `STT_TTS_TIMING` 未設 → Part A 零輸出；Part B 對已 start thread 行為不變（is_alive=True 照 join）。
- 不動辨識 / 注入 / 連線生命週期 / disarm Finalize / endpointing / arecord。

## 測試
- `py -3.14 -m pytest tests/stt/ -q`：
  - Part B：`test_shutdown_does_not_join_unstarted_thread`——手動把 `_receiver`/`_keepalive` 設為未 start Thread + `_ws`/`_conn_stop` 就緒 → `shutdown()` 不拋 RuntimeError。
  - Part A：`STT_TTS_TIMING` 設時 feed 一則 interim Results → capsys 含「Deepgram Results final=False」。
  - 既有全綠。
- 全套 `py -3.14 -m pytest tests/ -q`（baseline 672）。
- Pi：`STT_TTS_TIMING=1` 跑多輪重現殭屍輪 → 貼該輪 `[計時] Deepgram ...` log 回來判定 (A)/(B)。

## Out of scope
- 殭屍 bug 的**實際修復**（依診斷結果，下一輪做：(A)→改每輪新連線 / 移除 Finalize；(B)→arecord 重開）。
- warm-arecord（開頭裁切修法）。
- endpointing / drain / 對話文案。

## Commit
- 分 2 commit（Part A 診斷 / Part B race 修復）或合一；明列 `myProgram/stt.py tests/stt/test_worker.py`。
- 末尾 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。
