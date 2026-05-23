# Subagent / Agent Teams 派發協議

我（主對話 agent）是工程部「總負責人」，subagent / agent teams 是底下執行任務的工程師團隊。

**派發時機（預設行為）：** plan mode 完成後 → 一律派 subagent（單一任務）/ agent teams（複雜任務）執行，**除非使用者明確要求主 agent 直接寫**。主 agent 留做規劃 / 審查 / 邊界判斷。

**預設模型：** `Agent({model: "sonnet"})`。Agent 工具不接受 `effort` / `thinking` / context window 參數，要 high effort 必須**在 prompt 內明確要求**「extended thinking、仔細思考、嚴格依規範執行」。

**派發前必做：**
1. **EnterWorktree** — 派發前主 agent 先進 worktree，subagent 繼承 cwd 自動在隔離環境內工作。完整流程見 `.claude/rules/worktree-workflow.md`。
2. **挑選當前任務可能涉及的 CLAUDE.md 規則** 塞進他們的 context — subagent 是全新 context window，預設讀不到本檔。不要全塞，只塞**可能踩到**的部分。原則：寧多勿漏。
3. **附上 `karpathy-guidelines` Skill** — 編寫程式碼的最佳實踐。
4. **明確要求他們嚴格遵守以上全部規範。**

**派發後必做：**
- 逐項核對產出是否符合 CLAUDE.md。
- 小細節不符 → 我自己直接修，省往返。
- 大量偏差 → 退回要求重做。
- **絕不直接把不符合規範的產出交給使用者。**

詳細協議 / 規則對應表 / 心態原則 → memory `subagent-dispatch`
