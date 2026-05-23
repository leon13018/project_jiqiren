# Incremental rebuild 流程（架構難收斂時必走）

當現有架構出現「多線程 + 多 queue + 旗號狀態交互產生不穩定 bug」、debug 範圍難以收斂時，**不要繼續打補丁**，改走 incremental rebuild：殺掉重做、每步只加一層複雜度、每步測完才下一步。

---

## 觸發條件

任一條件成立 → 提議 incremental rebuild（不直接動手，先跟使用者對齊）：

1. **同一片邏輯區塊** 連續兩輪以上 patch 後，仍出現相關 bug（不同症狀但根因都繞回該區）
2. **bug 牽涉 ≥3 個 thread / queue / 旗號**（race window 數量級膨脹）
3. **使用者明確說「亂掉、不穩、複雜」** 而非具體單點症狀
4. **廠商 SDK 的隱性狀態**（如 sticky 旗號）跟自寫架構互動，越補越複雜

---

## S1-S7 流程模板

每一步**只加一層**新複雜度，每步走完整 worktree → subagent → 審查 → ff-merge → push → sync → **使用者實機測試** → 通過才開下一步。

| 步驟 | 加入什麼 | 用意 |
|---|---|---|
| **S1** | 純業務邏輯（單線程、無 IO、無 UI、無 timeout） | 確認流程 / 識別 / 狀態機正確 |
| **S2** | 同步語音（speak() 阻塞至播完） | 驗證 TTS pipeline；無 thread 干擾 |
| **S3** | 同步動作（廠商 runAction 阻塞至結束） | 驗證動作 pipeline；確認 vendor 旗號不污染 |
| **S4** | 非阻塞語音（worker thread + FIFO queue，**不中斷**） | dialogue 不被語音卡；連續 say 兩段都完整播 |
| **S5** | 非阻塞動作（worker thread + FIFO queue，**不中斷**） | 動作背景跑；動作 + 語音可並行 |
| **S6** | 非阻塞 input（input_reader thread + **單一 queue**） | customer 可 timeout 自動退出；無分流 race |
| **S7（選擇性）** | 中斷邏輯（新任務覆蓋舊） | 僅在 S6 通過後使用者明確要求「快速切換」才加 |

S3 完成後評估：若體驗已可接受，可暫停 S4-S7，先做其他功能（STT / HTML UI / OpenCV 等）。**不必為了「完整實作」而硬走完所有步驟**。

---

## 核心原則（每步驟都要遵守）

### 1. 每步只一變數
新增一個 thread / 一個 queue / 一個 IO 來源 / 一個中斷機制 — **一輪只加一種**。bug 出現時 99% 跟新加的那一層有關，debug 範圍立即收斂。

### 2. 每步必實機測試
寫完 → push → sync_pi → 使用者在 Pi 上跑 → 回報通過 → 才進下一步。**不要先把後面寫好再一起測**。

### 3. 預設 FIFO，中斷是 nice-to-have
非阻塞 worker 的預設語義是「順序消費、不打斷」。中斷邏輯（新任務覆蓋舊）會引入 race，是 S7 的選擇性升級，不是 S4-S5 的預設。

### 4. 單 queue 單消費者 > 多 queue + 旗號分流
input / event 分流時，**避免用可變狀態旗號做 routing**（如 `has_customer` → cmd_queue / customer_queue）。改用「單 queue + 順序消費」：dialogue 在當下情境決定怎麼處理。dialogue 是順序的（不會同時消費），無 race window。

### 5. 廠商 sticky 旗號要查 runningAction 才呼叫 stopAction
`Act.stopAction()` 設 `stop_action=True` 是 sticky 旗號，**只在 `runAction` 內部迴圈才被消耗**。若空轉時呼叫 → 污染下次 `runAction` 一進入就被打斷。必須 `if Act.runningAction: stopAction()` 守衛。

### 6. 廠商 / 自寫狀態邊界要清楚
廠商 SDK（ActionGroupControl / Board）的全域旗號是「黑盒副作用」，跟自寫的 `threading.Event` 不要混為一談。每次呼叫廠商 stop / cancel API，要明確知道**它影響哪個內部狀態、何時被消耗**。

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
