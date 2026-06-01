# Incremental rebuild 流程（架構難收斂時必走）

當現有架構出現「多線程 + 多 queue + 旗號狀態交互產生不穩定 bug」、debug 範圍難以收斂時，**不要繼續打補丁**，
改走 incremental rebuild：殺掉重做、每步只加一層複雜度、每步測完才下一步。

> **使用者偏好（2026-05-23 實測確認）**：多線程重構後出現「按 y 行為不一致、語音 / 動作有時被打斷有時沒、反覆
> 切換 idle/customer 會亂掉」。連續兩輪 patch（中斷邏輯加守衛、shutdown 補強）仍有相關 bug。使用者直接判斷
> 「複雜的 multi-thread queue 與主程式邏輯互動造成的混亂，重做反而省力」。事實證明這個直覺正確 — 整體架構
> race window 太多，補不完。

---

## 觸發條件

任一條件成立 → **主動提議** incremental rebuild（不直接動手，先跟使用者對齊）：

1. **同一片邏輯區塊** 連續兩輪以上 patch 後，仍出現相關 bug（不同症狀但根因都繞回該區）
2. **bug 牽涉 ≥3 個 thread / queue / 旗號**（race window 數量級膨脹）
3. **使用者明確說「亂掉、不穩、複雜」** 這類整體性形容詞，而非具體單點症狀
4. **廠商 SDK 的隱性狀態**（如 sticky 旗號）跟自寫架構互動，越補越複雜

---

## S1-S7 流程模板

每一步**只加一層**新複雜度，每步走完整 worktree → subagent → 審查 → ff-merge → push → sync →
**使用者實機測試** → 通過才開下一步。

| 步驟 | 加入什麼 | 用意 |
|---|---|---|
| **S1** | 純業務邏輯（單線程、無 IO、無 UI、無 timeout） | 確認流程 / 識別 / 狀態機正確 |
| **S2** | 同步語音（speak() 阻塞至播完） | 驗證 TTS pipeline；無 thread 干擾 |
| **S3** | 同步動作（廠商 runAction 阻塞至結束） | 驗證動作 pipeline；確認 vendor 旗號不污染 |
| **S4** | 非阻塞語音（worker thread + FIFO queue，**不中斷**） | dialogue 不被語音卡；連續 say 兩段都完整播 |
| **S5** | 非阻塞動作（worker thread + FIFO queue，**不中斷**） | 動作背景跑；動作 + 語音可並行 |
| **S6** | 非阻塞 input（input_reader thread + **單一 queue**） | customer 可 timeout 自動退出；無分流 race |
| **S7（選擇性）** | 中斷邏輯（新任務覆蓋舊） | 僅在 S6 通過後使用者明確要求「快速切換」才加 |

S3 完成後評估：若體驗已可接受，可暫停 S4-S7，先做其他功能（STT / HTML UI / OpenCV 等）。
**不必為了「完整實作」而硬走完所有步驟**。

---

## 核心原則（每步驟都要遵守）

### 1. 每步只一變數

新增一個 thread / 一個 queue / 一個 IO 來源 / 一個中斷機制 — **一輪只加一種**。bug 出現時 99% 跟新加的那一層
有關，debug 範圍立即收斂。

### 2. 每步必實機測試

寫完 → push（hook 自動 sync Pi） → 使用者在 Pi 上跑 → 回報通過 → 才進下一步。
**不要先把後面寫好再一起測**。

### 3. 預設 FIFO，中斷是 nice-to-have

非阻塞 worker 的預設語義是「順序消費、不打斷」。中斷邏輯（新任務覆蓋舊）會引入 race，是 S7 的選擇性升級，
不是 S4-S5 的預設。

### 4. 單 queue 單消費者 > 多 queue + 旗號分流

input / event 分流時，**避免用可變狀態旗號做 routing**（如 `has_customer` → cmd_queue / customer_queue）。
改用「單 queue + 順序消費」：dialogue 在當下情境決定怎麼處理。dialogue 是順序的（不會同時消費），無 race window。
（完整機制與守衛見下方 [§單 queue 偏好](#單-queue-偏好詳解)。）

### 5. 廠商 sticky 旗號要查 runningAction 才呼叫 stopAction

`Act.stopAction()` 設 `stop_action=True` 是 sticky 旗號，**只在 `runAction` 內部迴圈才被消耗**。若空轉時呼叫 →
污染下次 `runAction` 一進入就被打斷。必須 `if Act.runningAction: stopAction()` 守衛。
（完整機制與守衛見下方 [§廠商 stop_action sticky 旗號](#廠商-stop_action-sticky-旗號詳解)。）

### 6. 廠商 / 自寫狀態邊界要清楚

廠商 SDK（ActionGroupControl / Board）的全域旗號是「黑盒副作用」，跟自寫的 `threading.Event` 不要混為一談。
每次呼叫廠商 stop / cancel API，要明確知道**它影響哪個內部狀態、何時被消耗**。
廠商 SDK 禁改背景見 [`myprogram-vendor.md`](myprogram-vendor.md)；多線程規範見
[`myprogram-threading-paths.md`](myprogram-threading-paths.md)。

---

## 反模式（看到就拒絕）

- ❌ 一輪重構就把 worker / queue / 中斷 / 分流 / GUI 全部同時加入
- ❌ 寫完三層才開始測，bug 出現時範圍跨多層
- ❌ 用旗號分流 input（如 `has_customer` 路由），race window 隱性放大
- ❌ 中斷邏輯預設開啟（每個任務都 terminate + 清 queue），與 vendor sticky 旗號互動失控
- ❌ tkinter / GUI 在無實際需求時保留，硬把整個 thread 架構繞著主線程限制設計

---

## 何時不必走 incremental rebuild

- 純邏輯 bug（識別錯、計算錯、字串錯）→ 直接 patch
- 單一層的小 race（明確定位、修改範圍 <1 檔）→ 直接 patch
- 使用者偏好繼續 patch 並接受複雜度 → 尊重使用者，但要把風險講清楚

---

## 單 queue 偏好詳解

> 這次 rebuild 觸發的兩個技術教訓之一（另一個是下方 [§廠商 stop_action sticky 旗號](#廠商-stop_action-sticky-旗號詳解)）。

**規則：** 多消費者場景下，**不要**用可變狀態旗號（如 `has_customer` / `is_idle` / `mode`）把同一份 input
路由到不同 queue。改用**單一 queue + 順序消費**：消費者在當下情境決定怎麼處理。

**Why（2026-05-23 多線程重構）：** 引入 `cmd_queue`（y/q 指令）+ `customer_queue`（顧客話）+ `has_customer`
旗號分流：

```python
def input_reader():
    while True:
        line = input()
        if has_customer:
            customer_queue.put(line)
        else:
            cmd_queue.put(line)
```

實測「按 y 行為不一致」的根因：

- 使用者打字的時間點剛好在 `customer_mode` timeout 退出後幾毫秒
- 此時 `has_customer` 已被設回 `False`，但使用者覺得自己仍在 customer mode
- 字進了 `cmd_queue` 而非 `customer_queue`（或反之）
- 下一次模式切換時 queue 殘留字被當「新輸入」消費 → 行為亂掉

**洞察：** 大部分 dialogue 應用裡，消費者是**順序的**（主迴圈等 y → customer → 退出 → 主迴圈），同時間只有一個
地方在 get。所以**單 queue 單消費者完全足夠**，每個地方在自己的時機 `queue.get(timeout=...)` 即可。

**How to apply:**

1. **第一直覺**：input / event 從外部進來時，先丟到一個 queue，**不要在 producer 端做分流**。
2. **消費者在自己的情境決定怎麼解讀**：
   - 主迴圈拿到 `'y'` → 啟動 customer flow
   - customer flow 拿到任何字 → 當成顧客話處理
3. **若真有併發消費需求**（兩個 thread 同時等不同事件），優先考慮：
   - 把 dialogue 改成順序（一個 thread 跑完 flow，狀態機切換）
   - 用 event subscriber pattern（一份事件分發給多個訂閱者）
   - 而非用 routing flag 分流
4. **判斷標準**：若分流邏輯依賴可變狀態 + 該狀態變化點與輸入點有 race window → **架構錯**，重新設計成單 queue。

---

## 廠商 stop_action sticky 旗號詳解

> 這次 rebuild 觸發的兩個技術教訓之二（另一個是上方 [§單 queue 偏好](#單-queue-偏好詳解)）。

廠商 `ActionGroupControl.stopAction()` 設的 `stop_action = True` 是 **sticky 旗號**，**只在 `runAction()`
內部播放迴圈才被消耗**（消耗時印 `'stop'` 並 break）。

如果在 vendor 動作沒在跑時呼叫 `stopAction()`，旗號會「保留」到下次 `runAction()` 進入 → 一進迴圈第一幀就看到
旗號 → **立即 break、印 stop、動作根本沒跑**。

**Why（2026-05-23 第一輪多線程重構）：** `hawking_loop` 每輪都無條件呼叫 `Act.stopAction()`（為了清理舊任務）。
結果每次 vendor 動作（`wave_hand` / `bow` / `point_screen`）一進去就被旗號打斷，只看到頭部舵機動但身體完全沒動。
讀 `ActionGroupControl.py:118` 才發現 sticky 旗號機制。

**How to apply:**

1. **任何呼叫 `Act.stopAction()` / `Act.stopActionGroup()` 之前**，必須用 `Act.runningAction` 守衛：
   ```python
   if Act.runningAction:
       Act.stopAction()
       Act.stopActionGroup()
   ```
2. **`Act.runningAction`** 是 vendor 在 `runAction` 開頭設 `True`、結尾設 `False` 的模組級全域變數。可直接讀，
   但**不要寫**。
3. **守衛仍有微小 race window**（檢查為 True 後 runAction 剛好完成 → stopAction 設 True 仍會污染下次）。實務上這個
   window <1ms，且實際情境（每幾秒一個任務）幾乎遇不到。可接受。
4. **不要在 vendor 動作完成等待中呼叫 stopAction**「以防萬一清狀態」— 沒在跑就不要清。
5. **跟自寫的 `threading.Event` cancel 機制分開思考**：vendor 旗號是黑盒副作用，跟 Python 端的 event 不要混淆。

詳細歷史：`resources/examples/legacy_threading_v1/README.md`（若存在）+ commit `a95507f`（守衛修復點）。
廠商 SDK 禁改背景與完整 API 見 [`myprogram-vendor.md`](myprogram-vendor.md)。

---

**相關 reference**：[bdd-tdd.md](bdd-tdd.md)（S1 階段的業務邏輯開發流程）/
[myprogram-vendor.md](myprogram-vendor.md) / [myprogram-threading-paths.md](myprogram-threading-paths.md) /
[sdd.md](sdd.md)
