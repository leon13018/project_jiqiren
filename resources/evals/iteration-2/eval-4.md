# Iteration-2 transcript — eval 4 (sales cluster), model=opus

> round-2 後（sales-dialog-design：C-2 去日期/commit 反轉史、**L4 段整段重寫為 v3 準確版**——36s 雙計時器 + QR 12s 循環 + 暫停補償 + 客服 yes reset；sales-tts-ux：去 v1/v2/v3 SHA 演化史留陷阱、清 L4 budget 歷史備註、UX 哲學 Why 去日期戳）。場景同 baseline eval-4。

## Navigator 回覆（摘要）
- 正確釐清：L3「沒有了」命中 `_KEYWORDS_REJECT` 短詞，但 L3 normal mode 下不當拒絕、回傳「結帳」意圖（nlu.py:221-225）→ 走 C-2 → `_dialog_checkout_confirm`（12s + 5 次容忍）→ yes 進 L4。**不經 cancel/service confirm**。
- cancel_confirm：`_cancel_confirm.py`，`CANCEL_CONFIRM_TIMEOUT=6.0`s wall-clock（speak_and_wait 從 TTS 播完算），True=取消/False=NO，NO 先 check；8 gate；L3 要明確退出詞（REJECT_L3_STRICT）才觸發。
- service_confirm：`_service_confirm.py`，`L4_C_CONFIRM_TIMEOUT=24`s 一次性、亂答不重置，"yes"|"no"|"scan"，NO 先 check。
- inverse 對稱表（6s/24s、YES 語意、silent→取消）+ 保守 default 鐵則。
- 提醒改 sales code 走 SDD、未動檔。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：SKILL.md → sales-dialog-design.md（路由「cancel/service confirm」直接命中）→ grep myProgram → nlu.py（驗「沒有了」實際路由）。
- reference→reference：**否**。sales-dialog-design 一份即涵蓋 cancel/service confirm 完整行為 + 計時，未跳 sales-tts-ux（比 iteration-1 更自足，iteration-1 還開了 sales-tts-ux）。讀 nlu.py 屬「驗證使用者前提」非文件不足。
- 計時秒數來源：**cancel 6s / service 24s 都直接從 reference 讀到，無需 grep code**（line 99/114/121-126 白紙黑字）。文件做得好。
- 缺漏（pre-existing，非去噪造成；iteration-1 baseline 亦標同條）：sales-dialog-design 未收錄「L3 reject 短詞=不追加→結帳（非取消）」設計（只在 nlu.py 註解）；照 reference 導航者易誤以為「沒有了」會進 cancel_confirm。建議補一段交叉引用（屬補內容、本輪 de-noise scope 外）。
