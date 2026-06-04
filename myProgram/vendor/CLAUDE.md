# myProgram/vendor/ — 本層導引

> **本層結構索引：`.claude/code_map.md`——任何「vendor 裡的檔在哪 / 結構」務必第一優先讀它。**

廠商 Hiwonder TonyPi SDK。

- 🔒 權威紅線見 root `CLAUDE.md` ⛔#1（PreToolUse hook 強制擋）。
- 局部細節（為何禁改）：兩檔含 Pi-only 依賴（`pigpio` / `RPi.GPIO` / `BusServoCmd` / `PWMServo` / `smbus2`），改動破壞硬體通訊。SDK API 用法見 `project-01-workflow` skill 的 `myprogram-vendor.md`。
