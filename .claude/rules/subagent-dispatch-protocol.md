# Subagent / Agent Teams 派發協議

我（主對話 agent）是工程部「總負責人」，subagent / agent teams 是底下執行任務的工程師團隊。

**派發時機（預設行為）：** plan mode 完成後 → 一律派 subagent（單一任務）/ agent teams（複雜任務）執行，**除非使用者明確要求主 agent 直接寫**。主 agent 留做規劃 / 審查 / 邊界判斷。

**預設模型：** `Agent({model: "sonnet"})`。Agent 工具不接受 `effort` / `thinking` / context window 參數，要 high effort 必須**在 prompt 內明確要求**「extended thinking、仔細思考、嚴格依規範執行」。

**派發前必做：**

1. **EnterWorktree** — 派發前主 agent 先進 worktree，subagent 繼承 cwd 自動在隔離環境內工作。完整流程見 `.claude/rules/worktree-workflow.md`。
2. **挑選任務特化規則塞進 prompt**（**已大幅精簡 — 標準規範改由 SubagentStart hook 自動注入**）：
   - **不需自己塞：** 廠商 SDK 禁改 / 繁中 / 不用 git add -A / commit Co-Authored-By / karpathy-guidelines — 全由 `.claude/hooks/subagent-inject-rules.ps1` 自動注入
   - **仍需自己塞（任務特化）：** vendor-files API 細節 / threading-conventions / 業務規格 / 任務當下 plan 等
   - 規則：subagent 是全新 context window；自動注入只涵蓋「universal rules」，path-scoped 或任務特化規則仍需手動

**派發後必做：**

- 逐項核對產出是否符合 CLAUDE.md / 任務 plan。
- 小細節不符 → 我自己直接修，省往返。
- 大量偏差 → 退回要求重做。
- **絕不直接把不符合規範的產出交給使用者。**
- **驗證 commit branch（2026-05-26 加，防 Gotcha M）：** subagent 回報 commit SHA 後跑 `git branch --contains <SHA>` 確認落在 `worktree-*` branch；若顯示 `main` 表示 commit 跑錯 branch（已知偶發 bug，見 `.claude/hooks/NOTES.md` Gotcha M），改走 workaround（主 checkout 直接 `git push origin main`，跳過 ff-merge）。

**自動化補充：**

- 🪝 **SubagentStart hook**（2026-05-25 起）自動注入標準規範。Subagent 看到的 context window 開頭會有「SubagentStart 標準規範注入」段，包含 ⛔ 禁止項 / 強制規範 / 文檔指標。
- 🪝 **agent_type 分流**：研究類（claude-code-guide / Explore / Plan）注入精簡版（只含繁中 + 文檔指標）；編碼類（general-purpose / 自訂 agent）注入完整規範。
- 🔗 **完整 hook 文檔：** `.claude/hooks/NOTES.md`

詳細協議 / 規則對應表 / 心態原則 → memory `subagent-dispatch`
