# 廠商 SDK（vendor）— 禁改紅線 + 關鍵 API + silent fail 排查

> **🎯 何時讀本檔**：要 `import` / 呼叫廠商 SDK（`ActionGroupControl` / `Board` / `runAction` 等），或 Pi demo 動作沒出來要排查 silent fail。

`myProgram/vendor/ActionGroupControl.py` 與 `myProgram/vendor/Board.py` 是 Hiwonder TonyPi 廠商提供的 SDK 檔案。本 reference 整合：禁改背景、可直接 import 的關鍵 API 清單、`runAction` 兩種 silent fail 模式與 Pi demo 沒動作的排查 checklist。

---

## ⛔ 絕對禁止修改（hook 強制執法）

**`myProgram/vendor/ActionGroupControl.py` 與 `myProgram/vendor/Board.py` 絕對絕對不能修改內容**，只能 `Read` 引用、`import` 使用。見 [CLAUDE.md](../../../../CLAUDE.md) ⛔ 絕對禁止 #1。

**🔒 hook 強制：** `.claude/hooks/block-vendor-edit.ps1` 的 PreToolUse hook 自動 block 對這兩個檔的 Edit / Write，不依賴主 agent 自律。regex 為 `/myProgram/(?:.+/)?(ActionGroupControl|Board)\.py$`（涵蓋舊路徑防回滾 + 任意子層 future-proof）。

**Why（為何禁改）：** 這兩個檔案裡所有寫死的路徑（`/home/pi/TonyPi/HiwonderSDK`、`/home/pi/TonyPi/ActionGroups/*.d6a`）與 import（`BusServoCmd`、`PWMServo`、`pigpio`、`RPi.GPIO`、`smbus2`）都是 Raspberry Pi 4 上的真實檔案、慣量檔、底層庫。改動會直接破壞與機器人硬體的通訊。

### 2026-05-26 P1 重組

廠商檔從 `myProgram/` root 搬到 `myProgram/vendor/` 子資料夾（commit `a7d434e`）做視覺隔離 + 同層加 `__init__.py` 含 DO NOT MODIFY docstring。`.claude/hooks/block-vendor-edit.ps1` regex 同步更新（見上）。import 路徑改為：
- `from myProgram.vendor import ActionGroupControl as Act`
- `from myProgram.vendor import Board`

### How to apply（使用守則）

- 永遠用 Read / Glob / Grep 引用，不要 Edit、不要 Write、不要重構這兩個檔。
- `git mv` 改位置不算修改內容（byte-for-byte 不變）— hook 不擋（hook 只攔 Edit/Write）；但本輪 P1 搬完後就不該再動位置。
- 自寫程式碼透過 `import` 呼叫即可（路徑：`from myProgram.vendor import ActionGroupControl as Act`），不要包裝太厚或試圖修補它們的「缺陷」。
- 因為這兩個檔有 Pi-only 依賴，**Windows 本機完全無法 import 測試** 任何依賴它們的程式碼。所有實際執行都在 Pi 上由使用者測試 — Claude 不嘗試在本機跑 `.py`。
- 廠商 SDK 隨 Pi 系統映像預裝，不需要寫入 `resources/requirements/raspberry_pi_setup.md`（Pi 已安裝清單）。

---

## 廠商 SDK 提供的關鍵 API（自寫程式可直接 import 使用）

### `ActionGroupControl`（播放 `.d6a` 四肢動作組）

動作組檔案位於 `/home/pi/TonyPi/ActionGroups/`，副檔名 `.d6a`。

- `runAction(actName, lock_servos='')` — 單次播放
- `runActionGroup(actName, times=1, with_stand=False, lock_servos='')` — 多次播放，支援走路 start/end 動作組合
- `stopAction()` — 中止單次動作
- `stopActionGroup()` — 中止動作組

### `Board`（舵機 / 蜂鳴器底層控制）

- `setBusServoPulse(id, pulse, use_time)` — 總線舵機（頭部）；pulse 0–1000，use_time 0–30000 ms
- `setPWMServoPulse(servo_id, pulse, use_time)` — PWM 舵機 1–2；pulse 500–2500
- `setBuzzer(new_state)` — GPIO 31 蜂鳴器
- `setBusServoID` / `getBusServoID`
- `setBusServoDeviation` / `getBusServoDeviation`
- `setBusServoAngleLimit` / `getBusServoAngleLimit`
- `setBusServoVinLimit` / `getBusServoVinLimit`
- `setBusServoMaxTemp` / `getBusServoTempLimit`
- `getBusServoPulse` / `getBusServoTemp` / `getBusServoVin`
- `stopBusServo(id)` / `unloadBusServo(id)` / `getBusServoLoadStatus(id)`

---

## `Act.runAction(name)` 兩種 silent fail 模式（Pi demo 沒動作時必查）

`Act.runAction(name)`（廠商 `ActionGroupControl.py`）有兩種 silent fail 模式，Pi demo 沒動作時必查。

### Mode 1：`.d6a` 檔不存在

廠商 `runAction(actName)` line 108-137 流程：
```python
actNum = "/home/pi/TonyPi/ActionGroups/" + actName + ".d6a"  # path 寫死
if os.path.exists(actNum) is True:
    if runningAction is False:
        ...  # 真跑動作
else:
    runningAction = False
    print("未能找到動作组文件", actNum)   # ← silent print，不 raise
```

**症狀：** 機器人不動 + console 印「未能找到動作组文件 /home/pi/TonyPi/ActionGroups/<name>.d6a」

**排查：** Pi 上 `ls /home/pi/TonyPi/ActionGroups/<name>.d6a` 確認檔存在；使用者自訂動作（如 L2/L3）要去 Hiwonder TonyPi 動作編輯器建立 + 匯出到此路徑。

### Mode 2：`runningAction` global 旗號卡 True

`runningAction` 是廠商 `ActionGroupControl.py` 模組級 global，正常流程 runAction entry 設 True、exit 設 False。若程式中斷在動作執行中（KeyboardInterrupt / crash），旗號殘留 True → 下次 runAction 整段 if-true 段被 skip，完全 silent return（連 print 都沒）。

**症狀：** 機器人不動 + console 沒任何輸出（連「未能找到」都沒）

**排查：** 重啟 Python interpreter（重跑 `python3.11 -m myProgram`）讓 global 重置；極端時重啟機器人。

---

## Pi demo 沒動作排查 checklist

依序確認 4 件事：

1. **Pi git HEAD 同步**：`cd /home/pi/Desktop/project_jiqiren && git log -1 --oneline` 是否為最新 commit（見 [pi-and-structure.md](pi-and-structure.md) §Pi 環境陷阱 + [standard-workflow.md](standard-workflow.md) §background session 雙保險）
2. **Pi pycache 清乾淨**：`ssh pi find /home/pi/Desktop/project_jiqiren -name '__pycache__' -type d -exec rm -rf {} +`（見 [standard-workflow.md](standard-workflow.md) §Pi 端 pycache stale；或跑 `scripts/clean-pi-pycache.ps1`）
3. **廠商 baseline**：`cd /home/pi/TonyPi/HiwonderSDK && python3.11 -c "import ActionGroupControl as Act; Act.runAction('wave_hand')"` 跑得動嗎？跑不動 = 廠商 SDK 環境問題（pigpiod / 舵機接線 / GPIO 權限）
4. **我們 import path**：`cd /home/pi/Desktop/project_jiqiren && python3.11 -c "from myProgram.vendor import ActionGroupControl as Act; Act.runAction('wave_hand')"` 跑得動嗎？跑不動 = 我們 wire-up 問題

3 + 4 都通 → 跑主程式看 console 是否印 `[動作] <name>` 訊息：
- 沒印 = callback 沒被觸發到（dialogue / state machine wire-up 漏）
- 印了但機器人不動 → Mode 1 / Mode 2 silent fail（看上面排查）

---

## 廠商 sticky 旗號注意事項

S3 嚴格不呼叫 `Act.stopAction()`（見 [incremental-rebuild.md](incremental-rebuild.md) §sticky 旗號），所以 sticky flag 不會被本專案污染；但若手動 / 其他程式呼叫過 `stopAction`，下次 `runAction` 一進入就被打斷。

`Act.stopAction()` 設的 `stop_action=True` 是 sticky 旗號，**只在 `runAction` 內部迴圈才被消耗**。若空轉時呼叫 → 污染下次 `runAction` 一進入就被打斷。必須 `if Act.runningAction: stopAction()` 守衛（見 [myprogram-threading-paths.md](myprogram-threading-paths.md) worker shutdown 對比表）。

---

**相關 reference：** [myprogram-threading-paths.md](myprogram-threading-paths.md)（線程規範 + worker shutdown）/ [incremental-rebuild.md](incremental-rebuild.md)（sticky 旗號詳解）/ [CLAUDE.md](../../../../CLAUDE.md) ⛔ #1
