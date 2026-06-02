# myProgram/vendor/ — 本層導引

> **本層結構索引：`.claude/code_map.md`——任何「vendor 裡的檔在哪 / 結構」務必第一優先讀它。**

廠商 Hiwonder TonyPi SDK。

- 🔒 **絕對禁止修改** `ActionGroupControl.py` / `Board.py`——含 Pi-only 依賴（`pigpio` / `RPi.GPIO` / `BusServoCmd` / `PWMServo` / `smbus2`），改了破壞硬體通訊（PreToolUse hook 自動 block）。只能 `Read` 引用、`import` 使用。
- 完整紅線見 root `CLAUDE.md` ⛔ #1；廠商 SDK API 用法見 `project-01-workflow` skill 的 `myprogram-vendor.md`。
