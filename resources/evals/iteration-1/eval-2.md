# Condensed (iteration-1) transcript — eval 2 (process cluster), model=opus

> cluster 2 精簡後（worktree 102 / standard-workflow 84 / pi-and-structure 106）。場景同 baseline eval-2。

## Navigator 回覆（摘要）
- 判定＝Gotcha M。先 `git branch --contains <SHA>`（main = Gotcha M / worktree-* = 正常）。
- 救援分兩路：4a（改動已在落 main 那 commit、不需後續編輯）→ ExitWorktree(remove) → 主 checkout 跑驗證（Iron Law）→ push → 手動 sync；4b（需後續編輯）→ 新 worktree 編輯 commit → ExitWorktree(keep) → **cherry-pick**（非 ff-merge，diverge 必失敗 `Diverging branches can't be fast-forwarded`）→ push → `branch -D`。徵兆速查齊。
- 正常收尾階段 4-5：ExitWorktree(keep) → merge --ff-only → push → & sync_pi.ps1 → worktree remove + branch -d；Windows file lock fallback（Remove-Item -Force + prune）。
- sync 鐵則：push 後永遠手動（background hook 非 deterministic 不可依賴、idempotent no-op）；Pi git pull 後 hook 清 __pycache__（mtime stale .pyc）。
- 條件性 3a/3b（pineedtodo / code_map）觸發清單在 pi-and-structure，本情境未深入。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：worktree.md + standard-workflow.md（同批平行）。
- reference→reference：**非被迫追跳**——從 SKILL.md 路由表一次判定需兩檔、平行讀完。兩檔互補（worktree 階段 4 sync 一行 + 指 standard-workflow 雙保險理由；屬 see-also 非 load-bearing）。pi-and-structure 未跳讀（本情境不需 3a/3b 細節）。
- 缺漏：Gotcha M 解法完整無缺口；題目未給「改動是否已在落 main commit」故分 4a/4b 兩路答（不需額外檔）。
