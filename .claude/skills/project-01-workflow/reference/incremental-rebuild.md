# Incremental rebuild 流程（架構難收斂時必走）

> **🎯 何時讀本檔**：多線程 + 多 queue + 旗號交互產生難收斂的不穩定 bug、打補丁無效時。

## 目錄
- 觸發條件 / 何時不必走
- S1-S7 流程模板
- 核心原則 6 條
- 反模式
- 單 queue 偏好詳解（權威）
- 廠商 stop_action sticky 旗號詳解（權威）

架構出現「多線程 + 多 queue + 旗號狀態交互產生不穩定 bug」、debug 難收斂時，**不要繼續打補丁**，改走 incremental rebuild：殺掉重做、每步只加一層、每步測完才下一步。

---

## 觸發條件（任一成立 → **主動提議**、先對齊不直接動手）
1. 同一片邏輯連續 ≥2 輪 patch 後仍出現相關 bug（症狀不同但根因都繞回該區）。
2. bug 牽涉 ≥3 個 thread/queue/旗號（race window 數量級膨脹）。
3. 使用者說「亂掉 / 不穩 / 複雜」這類整體性形容詞。
4. 廠商 SDK 隱性狀態（sticky 旗號）跟自寫架構互動，越補越複雜。

**何時不必走**：純邏輯 bug（識別/計算/字串錯）直接 patch｜單層小 race（明確定位、<1 檔）直接 patch｜使用者明確要繼續 patch 並接受複雜度（尊重，但講清風險）。

---

## S1-S7 流程模板

每步**只加一層**，每步走完整 worktree → subagent → 審查 → ff-merge → push → sync → **使用者實機測** → 通過才下一步。

| 步驟 | 加入 | 用意 |
|---|---|---|
| S1 | 純業務邏輯（單線程、無 IO/UI/timeout） | 確認流程/識別/狀態機正確 |
| S2 | 同步語音（speak() 阻塞至播完） | 驗 TTS pipeline，無 thread 干擾 |
| S3 | 同步動作（runAction 阻塞至結束） | 驗動作 pipeline，確認 vendor 旗號不污染 |
| S4 | 非阻塞語音（worker + FIFO queue，**不中斷**） | dialogue 不被語音卡 |
| S5 | 非阻塞動作（worker + FIFO queue，**不中斷**） | 動作背景跑，可與語音並行 |
| S6 | 非阻塞 input（reader thread + **單一 queue**） | customer 可 timeout 退出，無分流 race |
| S7（選擇性） | 中斷邏輯（新任務覆蓋舊） | 僅 S6 通過後使用者明確要「快速切換」才加 |

> S3 完成後評估：體驗可接受就可暫停 S4-S7、先做其他功能（STT/HTML/OpenCV）。**不必為「完整」硬走完**。

---

## 核心原則（每步遵守）
1. **每步只一變數**（一輪只加一 thread/queue/IO/中斷）。
2. **每步必實機測**（push → hook sync Pi → 使用者跑 → 通過才下一步），不要先寫好後面才一起測。
3. **預設 FIFO、中斷是 nice-to-have**（中斷會引入 race，屬 S7 選擇性升級）。
4. **單 queue 單消費者 > 多 queue + 旗號分流**（見下 §單 queue 偏好）。
5. **廠商 sticky 旗號要查 runningAction 才呼叫 stopAction**（見下 §sticky 旗號）。
6. **廠商 / 自寫狀態邊界清楚**：廠商全域旗號是黑盒副作用，跟自寫 `threading.Event` 不要混；每次呼叫廠商 stop/cancel API 要知道它影響哪個內部狀態、何時被消耗。

## 反模式（看到就拒絕）
❌ 一輪把 worker/queue/中斷/分流/GUI 全部同時加｜❌ 寫完三層才測｜❌ 用旗號分流 input（race 隱性放大）｜❌ 中斷邏輯預設開啟（與 vendor sticky 互動失控）｜❌ 無需求硬留 tkinter/GUI 繞著主線程限制設計。

---

## 單 queue 偏好詳解（權威）

**規則**：多消費者場景下**不要**用可變狀態旗號（`has_customer`/`is_idle`/`mode`）把同一份 input 路由到不同 queue；改用**單一 queue + 順序消費**，消費者在當下情境決定怎麼處理。

**Why**：曾用 `cmd_queue` + `customer_queue` + `has_customer` 在 producer 端分流（`if has_customer: customer_queue.put() else cmd_queue.put()`）。「按 y 行為不一致」根因：使用者打字時間點剛好落在 `customer_mode` timeout 退出後幾 ms，`has_customer` 已設回 False 但使用者以為仍在 customer mode → 字進錯 queue → 下次切換時殘留字被當新輸入。

**洞察**：dialogue 消費者多為**順序**（主迴圈等 y → customer → 退出 → 主迴圈），同時間只一處在 get → 單 queue 單消費者足夠，各處在自己時機 `queue.get(timeout=...)`。

**How to apply**：(1) input 進來先丟單一 queue，**producer 端不分流**；(2) 消費者在自己情境解讀（主迴圈拿 `'y'` 啟動 customer flow / customer flow 拿任何字當顧客話）；(3) 真有併發消費需求 → 優先把 dialogue 改順序、或 event subscriber pattern，**而非 routing flag**；(4) 判準：分流邏輯依賴可變狀態 + 該狀態變化點與輸入點有 race window → **架構錯**，重設計成單 queue。

---

## 廠商 stop_action sticky 旗號詳解（權威）

廠商 `stopAction()` 設的 `stop_action=True` 是 **sticky 旗號**，**只在 `runAction()` 內部播放迴圈才被消耗**（消耗時印 `'stop'` 並 break）。若 vendor 動作沒在跑時呼叫 `stopAction()` → 旗號保留到下次 `runAction()` 進入 → 第一幀就 break、動作根本沒跑。

**Why**：`hawking_loop` 每輪無條件 `Act.stopAction()` 清舊任務 → 每次 vendor 動作（wave_hand/bow/point_screen）一進去就被旗號打斷，只有頭部舵機動、身體沒動。讀 `ActionGroupControl.py:118` 才發現 sticky 機制。

**How to apply**：
```python
if Act.runningAction:      # 必守衛：runningAction 是 vendor 模組級全域（entry True/exit False），可讀不可寫
    Act.stopAction()
    Act.stopActionGroup()
```
- 守衛仍有 **<1ms race window**（檢查為 True 後 runAction 剛好完成），實際情境（每幾秒一任務）幾乎遇不到，可接受。
- 沒在跑就不要「以防萬一」清狀態；vendor 旗號（黑盒副作用）跟自寫 `threading.Event` 分開思考。
- 廠商禁改與 API 見 [myprogram-vendor.md](myprogram-vendor.md)。
