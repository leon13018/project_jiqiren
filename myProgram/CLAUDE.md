# myProgram/ — 本層導引

> **本層結構索引：`.claude/code_map.md`——任何「myProgram 裡的檔在哪 / 結構」務必第一優先讀它。**
> 下沉：深入子目錄 → 讀 `<子目錄>/.claude/code_map.md`（不存在則以本層 code_map 說明為準）。

機器人主程式（Raspberry Pi 上執行）：點餐 / 收款規則匹配系統的進入點、worker 與銷售業務邏輯。

- 改本層任何 `.py` → 走 **SDD 流程**、遵守 **vendor 禁改紅線**（`vendor/ActionGroupControl.py` / `Board.py` 🔒）。
- 完整安全紅線 + 繁中規範 + 領域知識見 root `CLAUDE.md` 與 `project-01-workflow` skill，本檔不重複。
