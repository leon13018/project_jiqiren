# 廠商 SDK（vendor）— 禁改紅線 + 關鍵 API + silent fail 排查

> **🎯 何時讀本檔**：要 `import` / 呼叫廠商 SDK（`ActionGroupControl` / `Board` / `runAction` 等），或 Pi demo 動作沒出來要排查 silent fail。

## 目錄
- ⛔ 絕對禁止修改（hook 強制執法）
- 關鍵 API（可直接 import）
- `runAction` 兩種 silent fail
- Pi demo 沒動作排查 checklist

`myProgram/vendor/ActionGroupControl.py` 與 `Board.py` 是 Hiwonder TonyPi 廠商 SDK。本檔：禁改紅線、可直接 import 的 API 清單、`runAction` 兩種 silent fail、Pi demo 沒動作排查 checklist。

---

## ⛔ 絕對禁止修改（hook 強制執法）

**這兩檔絕對不能改內容**，只能 `Read` / `import`。見 [CLAUDE.md](../../../../CLAUDE.md) ⛔#1。
- **🔒 hook**：`.claude/hooks/block-vendor-edit.ps1`（PreToolUse）自動 block 對這兩檔的 Edit/Write，regex `/myProgram/(?:.+/)?(ActionGroupControl|Board)\.py$`（涵蓋舊路徑 + 任意子層）。
- **Why**：檔內寫死的路徑（`/home/pi/TonyPi/...`）與 import（`BusServoCmd`/`PWMServo`/`pigpio`/`RPi.GPIO`/`smbus2`）都是 Pi 4 上真實硬體底層，改動破壞硬體通訊。
- **import 路徑**：`from myProgram.vendor import ActionGroupControl as Act` / `from myProgram.vendor import Board`。
- **守則**：永遠 Read/import 用，不 Edit/Write/重構、不包裝太厚、不修補它的「缺陷」。Pi-only 依賴 → **Windows 本機無法 import 測試**任何依賴它的 code，實際執行一律 Pi 上由使用者測。廠商 SDK 隨 Pi 映像預裝，不寫入 setup 清單。

---

## 關鍵 API（自寫程式可直接 import 使用）

**`ActionGroupControl`（播放 `.d6a` 四肢動作組，檔在 `/home/pi/TonyPi/ActionGroups/`）**
- `runAction(actName, lock_servos='')` — 單次播放
- `runActionGroup(actName, times=1, with_stand=False, lock_servos='')` — 多次 + 走路 start/end 組合
- `stopAction()` / `stopActionGroup()` — 中止

**`Board`（舵機 / 蜂鳴器底層）**
- `setBusServoPulse(id, pulse, use_time)` — 總線舵機（頭部）pulse 0–1000 / use_time 0–30000ms
- `setPWMServoPulse(servo_id, pulse, use_time)` — PWM 舵機 1–2，pulse 500–2500
- `setBuzzer(new_state)` — GPIO 31 蜂鳴器
- ID / Deviation / AngleLimit / VinLimit / MaxTemp 的 set/get；`getBusServoPulse`/`Temp`/`Vin`；`stopBusServo`/`unloadBusServo`/`getBusServoLoadStatus`

---

## `Act.runAction(name)` 兩種 silent fail（Pi demo 沒動作必查）

**Mode 1 — `.d6a` 檔不存在**（runAction line 108-137）：path 寫死 `/home/pi/TonyPi/ActionGroups/<name>.d6a`，不存在則 `print("未能找到動作组文件 ...")` 但**不 raise**。
- 症狀：機器人不動 + console 印「未能找到動作组文件 ...」。
- 排查：Pi 上 `ls .../ActionGroups/<name>.d6a`；自訂動作（L2/L3）要去 Hiwonder 動作編輯器建立 + 匯出到此路徑。

**Mode 2 — `runningAction` global 卡 True**：模組級 global，entry 設 True / exit 設 False。若中斷在動作執行中（KeyboardInterrupt/crash）旗號殘留 True → 下次 runAction 整段 if-true 被 skip，完全 silent return（連 print 都沒）。
- 症狀：機器人不動 + console **無任何輸出**。
- 排查：重啟 Python interpreter（重跑 `python3.11 -m myProgram`）讓 global 重置；極端時重啟機器人。

---

## Pi demo 沒動作排查 checklist（依序）

1. **Pi git HEAD 同步**：`cd /home/pi/Desktop/project_jiqiren && git log -1 --oneline` 是否最新（見 [pi-and-structure.md](pi-and-structure.md) §Pi 環境陷阱 / [standard-workflow.md](standard-workflow.md) sync 雙保險）。
2. **Pi pycache 清乾淨**：`ssh pi find .../project_jiqiren -name __pycache__ -type d -exec rm -rf {} +`（見 standard-workflow §pycache；或 `scripts/clean-pi-pycache.ps1`）。
3. **廠商 baseline**：`cd /home/pi/TonyPi/HiwonderSDK && python3.11 -c "import ActionGroupControl as Act; Act.runAction('wave_hand')"` 跑得動？跑不動 = 廠商環境問題（pigpiod / 舵機接線 / GPIO 權限）。
4. **我們 import path**：`cd .../project_jiqiren && python3.11 -c "from myProgram.vendor import ActionGroupControl as Act; Act.runAction('wave_hand')"` 跑得動？跑不動 = wire-up 問題。

3+4 都通 → 跑主程式看是否印 `[動作] <name>`：沒印 = callback 沒觸發（dialogue/state machine wire-up 漏）；印了但不動 → Mode 1/2 silent fail。

> **sticky 旗號**：`Act.stopAction()` 設的 `stop_action=True` 是 sticky、只在 `runAction` 內部迴圈消耗；空轉時呼叫會污染下次 runAction → 必須 `if Act.runningAction: stopAction()` 守衛。完整機制見 [incremental-rebuild.md](incremental-rebuild.md) §廠商 stop_action sticky 旗號。

---

**相關 reference**：[myprogram-threading-paths.md](myprogram-threading-paths.md) / [incremental-rebuild.md](incremental-rebuild.md) / [CLAUDE.md](../../../../CLAUDE.md) ⛔#1
