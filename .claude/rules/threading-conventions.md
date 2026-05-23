---
paths: ["myProgram/**/*.py"]
---

# 多線程規範（編 `myProgram/*.py` 時必遵守）

廠商範例 `resources/examples/機器人動作結合opencv的多線程使用范例.py` 已在機器人上驗證可行。本規範由該範例反推 + 平台限制歸納，所有自寫 Python 程式碼必須遵守。

---

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

---

## 推薦架構（依模組 mix-and-match）

| 主線程（必須）| 背景線程（worker）|
|---|---|
| cv2 視覺迴圈（`cap.read` / `imshow` / `waitKey`）| `Act.runAction()` 動作執行 |
| tkinter `mainloop()` | TTS 播放（edge-tts + mpg123 subprocess）|
| 未來 HTTP server（FastAPI / Flask）| 偵測 / 推論 / 規則匹配 |

**設計準則：** 主線程留給「必須主線程」的 GUI 框架；blocking 任務全推背景。

---

## 線程間通信

| 方式 | 適用 | 備註 |
|---|---|---|
| Global 變數 polling | 學生專題級簡單情境（廠商範例做法）| 無 lock、CPU 較吃；能跑 |
| `queue.Queue` | 主→worker 任務 dispatch | thread-safe 內建型別，**推薦** |
| `threading.Event` | 訊號通知（start / stop / done） | 不傳資料只傳狀態時用 |
| 手動 `Lock` / `Condition` | ❌ 本專案用不到 | 死鎖風險高，避免 |

---

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

---

## 參考

廠商範例完整碼：`resources/examples/機器人動作結合opencv的多線程使用范例.py`
- 主線程：`imgRun()` 跑 cv2 視覺迴圈
- 背景線程：`runBot()` while 1 polling `lastCmd` global 變數
- 通信：global 變數讀寫（最樸素 pattern）
