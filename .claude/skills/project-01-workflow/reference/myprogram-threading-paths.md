# 多線程規範 + 路徑規範 + S6 reader thread 教訓

> **🎯 何時讀本檔**：要在 `myProgram/*.py` 寫多線程 / queue / thread，用到檔案路徑（須 Linux 絕對路徑），或碰 stdin 鍵盤輸入。

## 目錄
- Part A 多線程規範（強制約束 / 推薦架構 / 通信 / 地雷區）
- Part B 路徑規範（Linux 絕對路徑）
- Part C S6 非阻塞 input reader（最終設計 + 4 教訓）

---

# Part A — 多線程規範

廠商範例 `resources/examples/機器人動作結合opencv的多線程使用范例.py` 已在機器人驗證可行；本規範由其反推 + 平台限制歸納。

## 強制約束（違反必壞 / freeze）
1. **cv2 GUI（`imshow`/`waitKey`/`destroyAllWindows`）必須在主線程** — 違反 → 不顯示 / freeze / segfault。
2. **tkinter（`tk.Tk()`/`mainloop()`/widget 操作）必須在主線程** — 違反 → `RuntimeError: main thread is not in main loop`。
3. **`Act.runAction()` 等廠商動作 API 是 blocking（2~5 秒）** — **絕不放主線程**（會卡死 cv2/tkinter 視覺迴圈）。

## 推薦架構
| 主線程（必須） | 背景 worker |
|---|---|
| cv2 視覺迴圈 / tkinter mainloop / 未來 HTTP server | `Act.runAction()` 動作 / TTS（edge-tts+mpg123） / 偵測推論規則匹配 |

準則：主線程留給「必須主線程」的 GUI 框架；blocking 全推背景。

## 線程間通信
| 方式 | 適用 | 備註 |
|---|---|---|
| Global polling | 學生專題級簡單情境（廠商範例做法） | 無 lock、CPU 吃；能跑 |
| `queue.Queue` | 主→worker 任務 dispatch | thread-safe，**推薦** |
| `threading.Event` | 訊號通知（start/stop/done） | 不傳資料只傳狀態 |
| 手動 `Lock`/`Condition` | ❌ 本專案不用 | 死鎖風險高 |

## 地雷區
- **asyncio 在非主線程**：用 `asyncio.run(coro)` 或顯式 `new_event_loop()+set_event_loop()`；別用 `get_event_loop()`（worker thread 無 loop 會 `RuntimeError: no current event loop`）。
- **subprocess fire-and-forget**：`Popen` 不 wait 可能被截斷（父程序退 → SIGKILL / stdin pipe 關 → mpg123 退 / 同 thread 馬上另一 blocking 搶 IO → stall）。安全：`subprocess.run()` / `Popen.wait()` / `communicate()`。
- **daemon flag**：worker 通常 `daemon=True`（主程式退一起死）；但有未完成清理（檔案寫入 / subprocess 收尾）時 daemon 會被硬殺 → 視情況設。
- **tkinter callback 內 blocking**：callback 由 mainloop 同步派發，內含 5 秒 blocking → UI 凍 5 秒。解法：callback 內 `threading.Thread(target=..., daemon=True).start()`；worker 要更新 UI 不能直接 call widget（非主線程）→ 用 `root.after(0, cb)` 或 queue + `root.after(100, poll)` 排回主線程。
- **STT↔TTS 自我回授**（未來加 STT 收音 worker 時）：麥克風會把 TTS 喇叭聲聽回去當顧客輸入 → TTS 播放期間用 `tts.wait_idle()`/`_pending` gate 住 STT 收音或丟棄識別（自寫 Event，與 vendor sticky 旗號分開思考）。

> 架構難收斂時的 S1-S7 模板見 [incremental-rebuild.md](incremental-rebuild.md)。廠範完整碼 `resources/examples/機器人動作結合opencv的多線程使用范例.py`（主線程 cv2 迴圈 + 背景 polling global）。

---

# Part B — 路徑規範

程式最終在 **Raspberry Pi 4 (Linux)** 執行，所有路徑：
1. **Linux 格式** — 正斜線 `/`、不用 `\`、大小寫敏感。
2. **絕對路徑**（從 `/` 起）；**禁用** Windows 路徑（`C:\...`）、相對路徑（依賴 cwd）、`~`/`~/`（bash 引號內 / subprocess 不展開）。

| 用途 | 路徑 |
|---|---|
| 專案根 | `/home/pi/Desktop/project_jiqiren` |
| 廠商動作檔 `.d6a` | `/home/pi/TonyPi/ActionGroups/` |
| 廠商 SDK | `/home/pi/TonyPi/HiwonderSDK/` |
| Pi 家目錄 | `/home/pi` |

---

# Part C — S6 非阻塞 input reader（最終設計 + 4 教訓）

**S6**：`myProgram/input_reader.py` daemon reader thread + `queue.Queue` + bytes-level decode，取代 `input()` blocking。實機修補多次才乾淨；下方記最終設計 + 4 個要避免的 bug。

## 最終穩定設計
```python
# myProgram/input_reader.py
class InputReader:
    def __init__(self, source=None):
        self._source = source or sys.stdin.buffer   # 注入式 for tests
        self._q = queue.Queue()
        threading.Thread(target=self._loop, name="InputReader", daemon=True).start()
    def _loop(self):
        while True:
            try: raw = self._source.readline()
            except (OSError, ValueError): self._q.put(None); break
            if not raw: self._q.put(None); break   # EOF sentinel
            self._q.put(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
    def read(self, timeout):
        latest, has = None, False                  # latest-wins drain
        while True:
            try: latest = self._q.get_nowait(); has = True
            except queue.Empty: break
        if has: return latest
        try: return self._q.get(timeout=timeout)
        except queue.Empty: return None
    def shutdown(self):
        while not self._q.empty():
            try: self._q.get_nowait()
            except queue.Empty: break
        # **不**呼叫 sys.stdin.close() — 會 deadlock（教訓 4）

# main.py finally：tts.shutdown(); action.shutdown(); input_reader.shutdown(); os._exit(0)
```
- **Caller**：`read_terminal_key(timeout=None)` default **阻塞**（主選單/standby）；hawk 主迴圈才顯式 `timeout=0.1` polling。`read_customer_input(timeout)` 走既有 timeout。bytes-level decode 取代舊 `sys.stdin.reconfigure` hack。

## 4 個踩到的 bug（教訓）
1. **polling default timeout 不能設 0.1**：主選單每 100ms 重印 banner。根因：`read_terminal_key` default `0.1` 對「期待阻塞等鍵」的主選單/standby 是錯設計。修：default `None`，只有 polling 並行 cv2 的 caller 才顯式 `0.1`。polling cadence 是 caller-specific。
2. **polling 下 `_reset_q_confirm()` 不能被 timeout 觸發**：hawk 按 q 兩次不退。根因：每 100ms 空 read 返回 `""` → reset 掉第一個 q 的 pending。修：reset 只在 `key != ""` 時跑。阻塞→polling 改造時所有「假設無輸入不被觸發」的 state machine 都要 audit。
3. **daemon thread 卡 stdin readline syscall → finalizer hang**：「程式結束」印出後 process 不退、要按鍵才回 shell。根因：daemon reader 卡 kernel `read(fd)`，interpreter 退出時 finalizer 等 stdin lock、daemon C-level 釋放不了。`daemon=True` 只保證隨 process die，不保證 finalizer 不卡 lock。修：`main()` finally 加 `os._exit(0)` 強退跳過 finalizer。
4. **`sys.stdin.close()` 不解 readline、反而 lock deadlock**：根因鏈：Linux `close(fd)` 不 unblock in-syscall read；`TextIOWrapper.close()` 要 acquire `BufferedReader` internal lock；daemon reader 此刻正 hold 該 lock 在 readline 內 → main thread close() 永遠拿不到 lock → `os._exit` 跑不到。修：**移除** `sys.stdin.close()`，shutdown 只清 queue，daemon 隨 `os._exit` 殺。教訓：別嘗試「主動 unblock」blocking read，直接 `os._exit` 強退最可靠。

> 註：`read()` 用 latest-wins drain（撈光殘留但 return 最後一筆）而非全清——保留 user 剛打、caller 還沒消費的最新輸入，避免 race window 殺合法輸入。

## worker shutdown 對比
| Worker | shutdown | 為何 |
|---|---|---|
| `tts.py` | terminate mpg123 subprocess + 清 queue | 子程序需顯式 SIGTERM |
| `action.py` | `if Act.runningAction: Act.stopAction()` + 清 queue | vendor sticky 旗號（見 [incremental-rebuild.md](incremental-rebuild.md) §sticky） |
| `input_reader.py` | **只**清 queue | 不 close stdin（教訓 4）；daemon 隨 process die |

`os._exit(0)` 在 `main()` finally 最末——三 worker shutdown 跑完才強退。
