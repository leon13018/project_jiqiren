# Claude Code `/goal` 指令操作筆記

> **這是什麼**：使用 Claude Code `/goal`（autonomous loop，evaluator 每回合判斷條件是否滿足）的操作教訓。
> **為何在 resources/ 而非 skill**：`/goal` 是 Claude Code 通用工具特性、非 Project_01 領域知識或專屬 workflow，現行流程（SDD → sales-coder → worktree → reviewer）也不走 `/goal`。原寫在 `.claude/skills/.../reference/conventions.md`「工作原則」段，2026-06-03 移出以保持 skill 聚焦；知識保留於此，真要再跑 `/goal` 批次任務時回查。
> **來源**：2026-05-26 Wave 4 NLU 邊界批次修復實戰（見 `resources/changelog.md` 同日 Wave 0 / hotfix 紀錄）。

---

## `/goal` 條件設計

`/goal` 的 evaluator（小型快速模型，預設 Haiku）每回合後讀對話判斷條件是否滿足；條件太剛性會誤判沒完成、反覆開新回合。三條：

1. **用「>=」「至少」「無 X」描述，不用精確數字**。❌「pytest 顯示 226 passed」（subagent 加 test 後誤判）→ ✅「無 failed、無 error、無 xfailed；passed >= 226」。（2026-05-26 Wave 4 實際 231 passed，精確數字會讓 evaluator 判未滿足。）
2. **跨 Wave 的 invariant 依存在 prompt 明示**：本 Wave 改動若影響後續 Wave 既有 caller 行為（如 Wave 3 改 `parse_quantity("0 瓶")==0` → Wave 4 `add_item` 要 silent skip qty<=0 而非 raise），在後續 Wave prompt 預先指示處理路徑。
3. **明示「subagent 主動更新既有 fixture」合理**：prompt 加「若發現既有 test 規格/fixture 跟本 Wave 修法語意衝突，可主動更新並在 commit message 說明理由，主 agent 會審查」。

**額外觀察**：`/goal` evaluator 對主 LLM 透明（不收「Goal set」訊息，形式同普通使用者訊息，LLM 只是「持續工作直到沒新使用者訊息」）；Task reminder 對線性自動任務是 noise，忽略即可；turn 上限配合 Wave 數（4 wave≈40 / 5-6 wave≈50 / >7 wave 別連跑，reviewable 邊界）；Gotcha M 偶發、不代表每次 subagent commit 都踩，但 `git branch --contains <SHA>` 驗證仍保留。
