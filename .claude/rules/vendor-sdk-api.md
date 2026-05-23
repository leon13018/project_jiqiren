---
paths:
  - "myProgram/**/*.py"
---

# 廠商 SDK 關鍵 API（直接 import 使用）

> **禁止修改 `ActionGroupControl.py` / `Board.py`** — 見 [[CLAUDE]] ⛔ 絕對禁止 #1。完整 API 詳細參考見 [[vendor-files]] memory。

**`ActionGroupControl`**（播放 `/home/pi/TonyPi/ActionGroups/*.d6a` 動作）
- `runAction(actName, lock_servos='')`
- `runActionGroup(actName, times=1, with_stand=False, lock_servos='')`
- `stopAction()` / `stopActionGroup()`

**`Board`**（舵機 / 蜂鳴器）
- `setBusServoPulse(id, pulse, use_time)` — 總線舵機，pulse 0–1000
- `setPWMServoPulse(servo_id, pulse, use_time)` — PWM 舵機 1–2，pulse 500–2500
- `setBuzzer(state)`
- 各種 servo getter/setter（deviation / angle limit / temp / vin / pulse）
