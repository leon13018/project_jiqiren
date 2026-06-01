# 多線程規範 + 路徑規範 + S6 reader thread 教訓

編 `myProgram/*.py` 時必遵守的多線程約束、Linux 路徑規範，以及 S6 非阻塞 input reader thread 的最終設計與五輪修補教訓。

> 來源整合自 `.claude/rules/threading-conventions.md`、`.claude/rules/path-conventions.md`、memory `s6-non-blocking-input`。

---

# Part A — 多線程規範（編 `myProgram/*.py` 時必遵守）

廠商範例 `resources/examples/機器人動作結合opencv的多線程使用范例.py` 已在機器人上驗證可行。本規範由該範例反推 + 平台限制歸納，所有自寫 Python 程式碼必須遵守。

## 強制約束（違反必壞 / 必 freeze）

### 1. cv2 GUI 呼叫必須在主線程
- `cv2.imshow()` / `cv2.waitKey()` / `cv2.destroyAllWindows()` 只能在主線程跑
- 違反 → window 不顯示 / freeze / segfault

### 2. tkinter mainloop 必須在主線程
- `tk.Tk()` / `root.mainloop()` 只能在主線程
- 違反 → `RuntimeError: main thread is not in main loop`
- 從非主線程操作 widget → 未定義行為（多半 freeze 或 crash）

### 3. `Act.runAction()` / 廠商 SDK 動作 API 是 blocking
- 動作做完才 return（典型 2~5 秒）
- **絕對不要放主線程**：如果主線程有 cv2 / tkinter 視覺迴圈，會被卡死、UI 凍結

## 推薦架構（依模組 mix-and-match）

| 主線程（必須）| 背景線程（worker）|
|---|---|
| cv2 視覺迴圈（`cap.read` / `imshow` / `waitKey`）| `Act.runAction()` 動作執行 |
| tkinter `mainloop()` | TTS 播放（edge-tts + mpg123 subprocess）|
| 未來 HTTP server（FastAPI / Flask）| 偵測 / 推論 / 規則匹配 |

**設計準則：** 主線程留給「必須主線程」的 GUI 框架；blocking 任務全推背景。

## 線程間通信

| 方式 | 適用 | 備註 |
|---|---|---|
| Global 變數 polling | 學生專題級簡單情境（廠商範例做法）| 無 lock、CPU 較吃；能跑 |
| `queue.Queue` | 主→worker 任務 dispatch | thread-safe 內建型別，**推薦** |
| `threading.Event` | 訊號通知（start / stop / done） | 不傳資料只傳狀態時用 |
| 手動 `Lock` / `Condition` | ❌ 本專案用不到 | 死鎖風險高，避免 |

## 注意事項（地雷區）

### asyncio 在非主線程
- `asyncio.run()` 在 worker thread 內 call 理論可行（會建立新 event loop）。
- 但若程式碼用 `asyncio.get_event_loop()`（沒 loop 時不會自動建立），在 worker thread 會 fail：`RuntimeError: There is no current event loop in thread 'X'`
- **正確寫法**：`asyncio.run(coro)`，或顯式 `loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); loop.run_until_complete(coro)`

### Subprocess fire-and-forget
- `subprocess.Popen()` spawn 子程序後不 wait → 母程式繼續，子程序通常獨立繼續跑完
- **但可能被截斷的情境：**
  - 父程序退出 → 子程序被 SIGKILL（除非設定 detach）
  - stdin/stdout pipe 被關 → mpg123 之類讀 stdin 的會跟著退
  - 同 thread 馬上跑另一個 blocking call 搶 IO → 子程序可能 stall
- **安全做法：** `subprocess.run()`（同步等完） / `Popen.wait()` / `Popen.communicate()`

### Thread daemon flag
- 預設 `daemon=False` → 主程式結束時這個 thread 不會自動退，可能卡住整個程序退出
- **Worker thread 通常 `daemon=True`**：主程式退出時一起死，乾淨
- 但若 worker 內有未完成的清理（檔案寫入、subprocess 收尾），daemon=True 會被硬殺 → 視情況設

### Tkinter callback 內呼叫 blocking
- tkinter callback 由 mainloop 同步派發，callback 內若 call 一個 5 秒 blocking → UI 凍結 5 秒
- **解法：** callback 內 `threading.Thread(target=long_task, daemon=True).start()` 把 blocking 丟出去
- worker thread 完成後若要更新 UI，**不能直接** call widget method（不是主線程），用 `root.after(0, callback)` 或 `queue.Queue` + `root.after(100, poll_queue)` 排回主線程

## 參考

廠商範例完整碼：`resources/examples/機器人動作結合opencv的多線程使用范例.py`
- 主線程：`imgRun()` 跑 cv2 視覺迴圈
- 背景線程：`runBot()` while 1 polling `lastCmd` global 變數
- 通信：global 變數讀寫（最樸素 pattern）

架構難收斂時的 S1-S7 incremental rebuild 模板見 [incremental-rebuild.md](incremental-rebuild.md)。

---

# Part B — 路徑規範（寫程式 / 設定檔時必遵守）

程式最終在 **Raspberry Pi 4 (Linux)** 上執行，所有檔案路徑必須符合：

1. **Linux 路徑格式** — 正斜線 `/`，不用反斜線 `\`；大小寫敏感。
2. **絕對路徑** — 從 `/` 開始的完整路徑；**不要**用：
   - Windows 路徑（`C:\Users\...`）
   - 相對路徑（依賴執行時 cwd，容易在不同呼叫方式下失效）
   - `~` 或 `~/`（bash 引號內 / subprocess / 某些 context 不會展開）

## 常用 Pi 端絕對路徑

| 用途 | 路徑 |
|---|---|
| 專案根目錄 | `/home/pi/Desktop/project_jiqiren` |
| 廠商動作檔（`.d6a`） | `/home/pi/TonyPi/ActionGroups/` |
| 廠商 SDK | `/home/pi/TonyPi/HiwonderSDK/` |
| Pi 使用者家目錄 | `/home/pi` |

---

# Part C — S6 非阻塞 input reader thread（設計 + 五輪修補教訓）

**S6 incremental-rebuild 第 6 步**：`myProgram/input_reader.py` daemon reader thread + `queue.Queue` + bytes-level decode，取代 `input()` blocking 卡死主線程。實機落地經 **5 個 commit 修補** 才完全乾淨，記錄完整教訓避免下次再踩。S1-S7 流程模板見 [incremental-rebuild.md](incremental-rebuild.md)。

## 最終穩定設計（commit `9931605` 之後）

```python
# myProgram/input_reader.py
class InputReader:
    def __init__(self, source=None):
        self._source = source or sys.stdin.buffer   # 注入式 for tests
        self._q: queue.Queue[str | None] = queue.Queue()
        threading.Thread(target=self._loop, name="InputReader", daemon=True).start()

    def _loop(self):
        while True:
            try: raw_bytes = self._source.readline()
            except (OSError, ValueError): self._q.put(None); break
            if not raw_bytes: self._q.put(None); break   # EOF sentinel
            line = raw_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
            self._q.put(line)

    def read(self, timeout):
        # latest-wins drain（subagent 偏離 plan 但合理；保留 user 剛打的最新一筆）
        latest, has_residual = None, False
        while True:
            try: latest = self._q.get_nowait(); has_residual = True
            except queue.Empty: break
        if has_residual: return latest
        try: return self._q.get(timeout=timeout)
        except queue.Empty: return None

    def shutdown(self):
        while not self._q.empty():
            try: self._q.get_nowait()
            except queue.Empty: break
        # **不**呼叫 sys.stdin.close() — 會 deadlock（見下方教訓 4）

# main.py finally
def main():
    try: logic.run(**callbacks)
    except SystemExit: pass
    finally:
        tts.shutdown()
        action.shutdown()
        input_reader.shutdown()
        os._exit(0)   # **必須**強退，daemon thread 卡 readline syscall 阻 finalizer
```

**Caller side：**
- `read_terminal_key(timeout=None)`：**default `None` 阻塞**（給主選單 / standby 用）；hawk 主迴圈才**顯式傳 `timeout=0.1`** 走 polling
- `read_customer_input(timeout)`：仍走 6s WAIT_NO_RESPONSE / 12s DnC/DyC 等既有 timeout
- bytes-level decode 取代 main.py `sys.stdin.reconfigure(errors="replace")` hack（已移除）

## 五輪修補時序（commit 順序）

| commit | 修什麼 | 結果 |
|---|---|---|
| `c3563b3` | S6 主功能 — reader thread + queue + bytes-level decode | 引入 4 個 bug |
| `3625d56` | L1 busy loop fix — read_terminal_key default 從 `0.1` 改 `None` | bug 1 修好（主選單不再 100ms 重印 banner）|
| `25e8bb9` | (失敗嘗試) `sys.stdin.close()` 抑制 Fatal Python error 訊息 | 訊息壓掉但**底層 hang 沒解** |
| `d1fa68a` | hawk q-confirm polling reset bug — polling 空 read 不 reset pending | bug 2 修好（連按 q 兩次能退出）|
| `880936e` | finally 加 `os._exit(0)` 強退 — 跳過 Python finalizer | 寫對但**沒生效**（被下面 #5 卡住）|
| `9931605` | **移除** `sys.stdin.close()` — 才讓 `os._exit` 真跑到 | bug 3+4 真正修好 |

## 4 個踩到的教訓

### 教訓 1：polling 模式下 default timeout 不能設 0.1

**症狀**：L1 主選單每 100ms 重印 banner 洗版。
**根因**：`read_terminal_key(timeout=0.1)` default 對主選單 / standby 兩個 caller 是**錯設計** — 它們期待「阻塞等鍵」語意。`""` 空 read 落入 `_reset_q_confirm() + break` → outer while 重印 banner → 100ms 又跑一次。
**修法**：default 改 `None` 無限阻塞；**只有需要 polling 並行 OpenCV** 的 caller（hawk 主迴圈）才顯式 `timeout=0.1`。
**經驗**：polling cadence 是 caller-specific，不該 default。

### 教訓 2：polling 模式下 `_reset_q_confirm()` 不能被 timeout 觸發

**症狀**：hawk 模式按 q 兩次都沒退出，連按 7 次「[L1] 確定退出？」反覆。
**根因**：hawk 主迴圈每 100ms `read_terminal_key(timeout=0.1)` 返回 `""` → 走到 `_reset_q_confirm()` → 第一次 q 設的 `_q_confirm_pending=True` 被立刻 reset → user 真按的第二個 q 又被當第一次。
**修法**：hawk loop 內 `_reset_q_confirm()` 只在 `key != ""` 時跑（polling 空 read 不動 pending state）。
**經驗**：阻塞 → polling 改造時，所有「假設無輸入不會被觸發」的 state machine 都要 audit。

### 教訓 3：daemon thread 卡 stdin readline syscall → finalizer hang

**症狀**：「[系統] 程式結束」印出後 process 不退；user 必須按一個鍵才返回 shell prompt。
**根因**：daemon reader thread 卡在 `sys.stdin.buffer.readline()` 的 kernel `read(fd)` syscall。Python interpreter 退出時 finalizer 等 stdin lock 釋放 → daemon thread C-level 卡住釋放不了 → 整個 finalize hang。daemon=True 設計**只**保證隨 process die 自動被殺，不保證 finalizer 不卡 lock。
**修法**：`main()` finally 加 `os._exit(0)` 強退 process，跳過 Python finalizer。所有 worker（tts / action / input_reader）的 shutdown 已跑完，daemon thread 隨 process die 是 daemon=True 設計目的。
**經驗**：daemon thread + C-level blocking syscall（特別是 stdin/stdout）= interpreter shutdown 不乾淨。需要 `os._exit` 強退。

### 教訓 4：`sys.stdin.close()` 不解 readline syscall，反而 lock deadlock

**症狀**：以為加 `sys.stdin.close()` 能讓 readline 拿到 `ValueError` 解 hang，實際上 process 仍卡（並非 Fatal Python error，是 silent hang）。
**根因**：
1. Linux kernel `close(fd)` **不會 unblock** 已 in-syscall read 的 thread — 只 mark fd 不可用，next read 才 EBADF。
2. Python `TextIOWrapper.close()` 需要 acquire 底層 `BufferedReader` 的 internal lock。
3. daemon reader thread 此刻正 hold 那個 lock 在 readline 內。
4. main thread close() 永遠拿不到 lock → main thread 卡 → `os._exit(0)` 永遠跑不到。
5. user 按一個鍵 → kernel deliver byte → reader readline 返回釋放 lock → main 才能 close → 才到 os._exit。

**修法**：**移除** `sys.stdin.close()`。input_reader.shutdown 只 clear queue（instant，不卡）。daemon reader 隨 `os._exit` 殺 process 一起 die。
**經驗**：close() 對 in-syscall blocking read 是 implementation-defined 行為（Linux 不 unblock）；嘗試「主動 unblock」反而引入 lock acquire 順序 deadlock。直接 `os._exit` 強退最簡單可靠。

## 設計 caveat — Fatal Python error 訊息

舊版（25e8bb9 之前）退出時印：
```
Fatal Python error: _enter_buffered_busy: could not acquire lock for
<_io.BufferedReader name='<stdin>'> at interpreter shutdown,
possibly due to daemon threads
```

實際上**程式已正常退出**（process die），只是 finalizer 印錯誤訊息嚇人。`os._exit(0)` 跳過 finalizer 後此訊息消失。

## Subagent latest-wins drain 偏離 plan

主 plan 寫 drain 是「殺光所有殘留」（while get_nowait until Empty）。實機 subagent 改 **latest-wins**（撈光殘留但 return 最後一筆）。

**Subagent 解釋**：「全清」會在 race window 殺合法輸入（user 剛打的字也被當殘留丟）；latest-wins 保留「user 剛打完還沒被 caller 消費」的最新輸入。

**主 agent 審查接受**：場景「user 剛按一鍵 race」比「商家亂打 spam」常見得多；latest-wins 不會殺合法輸入是 net positive。

## 與其他 worker 對比

| Worker | shutdown 行為 | 為何 |
|---|---|---|
| `tts.py` | terminate mpg123 subprocess + 清 queue | mpg123 是子程序，需顯式 SIGTERM |
| `action.py` | 守衛 `if Act.runningAction: Act.stopAction()` + 清 queue | vendor sticky 旗號處理（見 [myprogram-vendor.md](myprogram-vendor.md) / memory `vendor-stop-action-sticky`）|
| `input_reader.py` | **只**清 queue | 不 close stdin（教訓 4）；daemon 隨 process die |

`os._exit(0)` 在 `main()` finally 最末 — 三個 worker shutdown 跑完才強退。

## 相關 memory

- memory `single-queue-preference` — 單 queue 順序消費，避免旗號分流 race
- memory `python-pycache-stale-on-pull` — Pi 端 sync 後要清 pycache
- [myprogram-vendor.md](myprogram-vendor.md) — 廠商 SDK API + sticky 旗號守衛
