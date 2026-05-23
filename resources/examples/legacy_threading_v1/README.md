# Legacy threading v1（歸檔，純參考）

## 是什麼

這是 2026-05-23 第一輪「導入多線程」重構的成果（commit `42291c8` + `a95507f`），於同日 incremental rebuild 時整批歸檔到此處。

四個檔案：

| 檔 | 設計重點 |
|---|---|
| `myProgram.py` | 主迴圈、ActionWorker、input_reader、command_dispatcher、雙 queue 分流 |
| `tts.py` | TtsWorker class，中斷式 `say()`（terminate mpg123 + 清 queue + put）|
| `robot_actions.py` | 組合動作（action_greet / action_pay 等）+ cancel event 機制 |
| `screen_display.py` | tkinter POSScreen（訂單 + QR code）+ thread-safe `schedule()` queue |

## 為何歸檔（不是刪掉）

裡面的**個別模式**仍有參考價值（例如 TtsWorker 用 Popen handle + lock + terminate 的 pattern；ActionWorker 的 cancel event + vendor stopAction 守衛；tkinter 跨線程 `_poll_queue` 安全更新）。但**整體架構**有不可調和的 race。

未來如果要實作中斷式 worker 或 tkinter 跨線程更新，可參考具體寫法 — 不要參考整體 5 thread + 2 queue + 旗號分流的組合。

## 踩到的坑（必讀，未來避免重蹈）

### 1. 廠商 `Act.stopAction()` 旗號是 sticky
`stopAction()` 設 `stop_action = True`，**只在 `runAction()` 內部播放迴圈才被消耗**（消耗時印 `'stop'`）。如果空轉時呼叫，旗號保留到下次 `runAction` 一進入就被打斷。

**修補**（commit `a95507f`）：在 `ActionWorker.do()` 內加 `if Act.runningAction:` 守衛，只在動作執行中才呼叫 stopAction。但即使修了，跟下面的雙 queue race 疊加仍會出現「亂掉」。

**memory**：`vendor_stop_action_sticky`

### 2. 雙 queue + `has_customer` 分流有 race window
```python
def input_reader():
    while True:
        line = input()
        if has_customer:
            customer_queue.put(line)
        else:
            cmd_queue.put(line)
```

使用者打字的時間點剛好在 customer_mode timeout 退出後幾毫秒 → 字進錯 queue → 殘留下次 → 「按 y 不理我」/「亂掉」。

**根因**：dialogue 是順序的（主迴圈 XOR customer_mode 在等 input），永遠只有一個消費者，**不應該**用旗號做分流。**應用單一 input_queue + 順序消費**。

**memory**：`single_queue_preference`

### 3. 5 條 thread + 2 worker state + sticky 旗號 → debug 範圍跨多層
單一 bug（如「動作被打斷」）可能源自：
- vendor 旗號污染
- worker queue 中斷邏輯
- has_customer 分流 race
- tkinter mainloop 與 input thread 競爭

加上每次只能在 Pi 上測（push → sync → 跑），補丁節奏太慢。

**結論**：架構複雜度超出可 debug 範圍 → 必須走 incremental rebuild。

**memory**：`incremental_rebuild_pattern`

## 重做方向（2026-05-23 plan）

見 plan 檔 `ktinter-c-users-lin-hong-desktop-projec-cryptic-eclipse.md`。要點：

- tkinter 砍掉、hawking_loop 砍掉
- 單一 input_queue、單一消費者
- 預設 FIFO worker，中斷邏輯是 S7 選擇性
- S1-S7 incremental，每步測完才下一步

## 看裡面的 code 之前

請先讀：

1. `.claude/rules/incremental-rebuild.md` — 為什麼這份歸檔了 + 重做的方法論
2. memory: `vendor_stop_action_sticky` / `single_queue_preference` / `incremental_rebuild_pattern`
3. `.claude/rules/threading-conventions.md` — 多線程通用規範

讀完再進來看 code，才知道哪些 pattern 可以抄、哪些是反例。
