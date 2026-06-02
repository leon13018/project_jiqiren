# Baseline transcript — eval 2 (process cluster), model=opus

> T0 baseline，現行 verbose skill。場景：subagent commit 跑到 main（Gotcha M）怎麼救 + worktree 收尾 + sync。

## Navigator 回覆

判定＝Gotcha M。
- 先確認：`git branch --contains <SHA>` 顯示 main → 確認踩到。
- 救援（4b 需後續編輯路徑）：ExitWorktree(remove) 回主 checkout（worktree branch 無新 commit，安全）→ 主 checkout 跑 pytest 驗證（Iron Law）→ 新 worktree 編輯補檔(code_map/pineedtodo) commit ExitWorktree(keep) → 回主 checkout **cherry-pick**（非 ff-merge，因新 worktree 從舊 base 分出、ff 必報 diverging）→ push → worktree remove + branch **-D**（大寫，因未被 ff-merged）→ 手動 `& sync_pi.ps1`。
- 4a（無後續編輯）：主 checkout 驗證後直接 push + sync。
- 歷史案例：Wave 0 d60798e→2976566→bd77ded。
- 正常收尾（沒踩 M）：ExitWorktree(keep)→git merge worktree-* --ff-only→push→& sync_pi.ps1→worktree remove + branch -d（小寫）。
- 兩坑：Windows file lock（Remove-Item -Recurse -Force fallback + prune）；push 後永遠手動 sync（background hook 非 deterministic，2026-05-27 實證；sync 同時清 Pi pycache）。
- 提醒條件性 3a（pineedtodo）/3b（code_map），判斷在 pi-and-structure.md。

## 導航紀錄
- 載入 skill：project-01-workflow。
- Read：worktree.md + standard-workflow.md（同批平行）。
- reference→reference：不需再跳——SKILL 路由表直接點名兩檔；兩檔交叉引用構成閉環（worktree 階段4 內嵌 standard-workflow push/sync 內核；standard-workflow 指回 worktree 5 階段）。兩檔都指向 pi-and-structure.md，但本任務只需說明步驟、未深入跳讀。
- 缺漏：無缺口。Gotcha M 完整解法 + 正常收尾 + sync 全覆蓋。
