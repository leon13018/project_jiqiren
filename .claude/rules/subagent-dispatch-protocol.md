# Subagent / Agent Teams 派發協議

我（主對話 agent）是工程部「總負責人」，subagent / agent teams 是底下執行任務的工程師團隊。

**派發時機（預設行為）：** plan mode 完成後 → 一律派 subagent（單一任務）/ agent teams（複雜任務）執行，**除非使用者明確要求主 agent 直接寫**。主 agent 留做規劃 / 審查 / 邊界判斷。

**派發方式（依任務類型選 subagent_type）：**

| 任務類型 | subagent_type | 為何 |
|---|---|---|
| 編 `myProgram/sales/*.py` / `tests/sales/*.py` / `myProgram/{main,tts,action,input_reader}.py` 等寫 code 任務 | **`sales-coder`**（自訂，frontmatter 預載 karpathy + TDD SKILL 完整內容） | 啟動時官方機制注入 SKILL 全文 vs prompt 內塞 reference summary 的薄弱對比 — 2026-05-28 由 user 提示研究後採用 |
| 純研究 / 探索 / 文件查詢 | `claude-code-guide` / `Explore` / `Plan`（built-in，sonnet） | 不寫 code，輕量化省成本 |
| 其他寫 code（暫無 custom subagent 對應）| `general-purpose` + `model: "opus"` | fallback，需在 prompt 內塞「extended thinking + xhigh effort 仔細思考、嚴格依規範執行、寧可慢、不要錯」字串 |

**為何不用 inline `Agent({skills: [...]})`：** 官方文檔（[subagents.md](https://code.claude.com/docs/en/subagents.md)）證實 Agent tool inline parameters **不接受 `skills` / `effort` / `thinking`**；必須走 `.claude/agents/<name>.md` frontmatter 預定義路徑。CLI `--agents` JSON flag 支援 skills 但屬 startup 級設定，session 內派發不適用。

**為何模型預設 opus xhigh：** [[wave-workflow-6-protections]] 實測 sonnet v1 Wave 7-10 連續踩 4 坑（Gotcha M / 雙寫 main / pytest 失準 / 漏更新 test）vs opus xhigh v2 零坑，既然 opus xhigh 是「跨檔 refactor 安全選項」乾脆預設化。**sales-coder frontmatter 已內建 `model: opus` + `effort: xhigh`**，主 agent 派發不必再傳。**例外：** 純研究 / Explore 類仍可手動指定 sonnet（成本考量）。

**派發前必做：**

1. **EnterWorktree** — 派發前主 agent 先進 worktree，subagent 繼承 cwd 自動在隔離環境內工作。完整流程見 `.claude/rules/worktree-workflow.md`。
2. **挑選任務特化規則塞進 prompt**（**已大幅精簡 — 標準規範由 frontmatter `skills:` 預載 + SubagentStart hook 補注入**）：
   - **不需自己塞（sales-coder 用 frontmatter 預載 SKILL 全文）：** karpathy-guidelines / test-driven-development — `.claude/agents/sales-coder.md` 的 `skills:` 欄位啟動時自動注入完整 SKILL.md
   - **不需自己塞（SubagentStart hook 注入 reference）：** 廠商 SDK 禁改 / 繁中 / 不用 git add -A / commit Co-Authored-By
   - **仍需自己塞（任務特化）：** vendor-files API 細節 / 業務規格 / 設計決定（已 AskUserQuestion 對齊的 ambiguity）/ 既有 helper reuse 點 / git add 範圍 + commit message 範本
   - 規則：subagent 是全新 context window；frontmatter + hook 只涵蓋「universal rules」，path-scoped + 任務特化規則仍需手動

**派發後必做：**

- 逐項核對產出是否符合 CLAUDE.md / 任務 plan。
- 小細節不符 → 我自己直接修，省往返。
- 大量偏差 → 退回要求重做。
- **絕不直接把不符合規範的產出交給使用者。**
- **驗證 commit branch（2026-05-26 加，防 Gotcha M）：** subagent 回報 commit SHA 後跑 `git branch --contains <SHA>` 確認落在 `worktree-*` branch；若顯示 `main` 表示 commit 跑錯 branch（已知偶發 bug），完整處理鏈：

  | 步驟 | 動作 |
  |---|---|
  | 1 | `ExitWorktree(action="remove")` — 切回主 checkout（worktree branch 無新 commit，安全 remove） |
  | 2 | 在主 checkout 跑 pytest / 審查新檔（main HEAD 已是 subagent commit） |
  | 3a | **不需後續編輯** → 直接 `git push origin main` + hook 自動 sync，結束 |
  | 3b | **需要主 agent 後續編輯**（projectStructure / pineedtodo 等）→ 進新 worktree + 編輯 + commit + ExitWorktree(keep) → **`git cherry-pick <SHA>`**（不能 ff-merge — 必失敗 diverging，因新 worktree 從舊 base 分出）→ push → `git worktree remove` + `git branch -D worktree-*`（用 `-D` 大寫因 branch 未被 ff-merged） |

  **歷史案例**：2026-05-26 Wave 0：subagent commit `d60798e` 落 main → projectStructure 更新 commit `2976566` 在新 worktree branch → ff-merge fail diverging → cherry-pick 成 main `bd77ded`。**完整文檔**：memory [[gotcha-m-post-commit-workflow]]。

**自動化補充：**

- 📦 **`sales-coder` 自訂 subagent**（2026-05-28 起）`.claude/agents/sales-coder.md` 透過 frontmatter `skills:` 預載 karpathy-guidelines + test-driven-development **SKILL 完整內容**（非 reference summary）。新增 / 改 subagent 檔需重啟 session 才生效（除非用 `/agents` interface 立即生效）；built-in subagent（Explore / Plan / general-purpose / claude-code-guide / statusline-setup）不支援 frontmatter 預載。
- 🪝 **SubagentStart hook**（2026-05-25 起）自動注入標準規範。Subagent 看到的 context window 開頭會有「SubagentStart 標準規範注入」段，包含 ⛔ 禁止項 / 強制規範 / 文檔指標。
- 🪝 **agent_type 分流**：研究類（claude-code-guide / Explore / Plan）注入精簡版（只含繁中 + 文檔指標）；編碼類（general-purpose / sales-coder / 其他自訂 agent）注入完整規範。
- 🔗 **完整 hook 文檔：** `.claude/hooks/NOTES.md`

詳細協議 / 規則對應表 / 心態原則 → memory `subagent-dispatch`
