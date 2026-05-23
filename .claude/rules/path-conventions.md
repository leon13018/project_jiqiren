---
paths:
  - "myProgram/**/*.py"
  - "**/*.ps1"
  - ".gitignore"
  - "resources/requirements/**/*.md"
  - "resources/pineedtodo/**/*.md"
---

# 路徑規範（寫程式 / 設定檔時必遵守）

程式最終在 **Raspberry Pi 4 (Linux)** 上執行，所有檔案路徑必須符合：

1. **Linux 路徑格式** — 正斜線 `/`，不用反斜線 `\`；大小寫敏感。
2. **絕對路徑** — 從 `/` 開始的完整路徑；**不要**用：
   - Windows 路徑（`C:\Users\...`）
   - 相對路徑（依賴執行時 cwd，容易在不同呼叫方式下失效）
   - `~` 或 `~/`（bash 引號內 / subprocess / 某些 context 不會展開）

## 常用 Pi 端絕對路徑

| 用途 | 路徑 |
|---|---|
| 專案根目錄 | `/home/pi/Desktop/project_jiqiren` |
| 廠商動作檔（`.d6a`） | `/home/pi/TonyPi/ActionGroups/` |
| 廠商 SDK | `/home/pi/TonyPi/HiwonderSDK/` |
| Pi 使用者家目錄 | `/home/pi` |
