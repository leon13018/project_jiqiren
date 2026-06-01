# SubagentStart hook：自動注入標準規範到所有 subagent
#
# 取代原 subagent-dispatch-protocol 步驟 2-3 的「手動塞規則 + karpathy」boilerplate。
# 主 agent 派發 prompt 改成只寫 task description + 任務特化規則（threading / path / etc）。
#
# 規格：
#   - SubagentStart event 支援 hookSpecificOutput.additionalContext（官方確認）
#   - 用 stdout 直出（簡潔；若無效改 JSON output）
#   - 依 agent_type 分流：研究類精簡注入 / 編碼類完整注入
#   - 失敗不影響派發（exit 0 always；只是少注入）

$ErrorActionPreference = 'Continue'

# 修正 PowerShell 5.1 預設 OutputEncoding 為系統 code page（本機 = cp936/GBK，PRC 區域）；
# Claude 讀 hook stdout 預期 UTF-8 — 不修繁中會被當 cp936 解碼成亂碼（注入內容變廢）。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$rawInput = [Console]::In.ReadToEnd()
$payload = $null
if (-not [string]::IsNullOrWhiteSpace($rawInput)) {
    try { $payload = $rawInput | ConvertFrom-Json } catch {}
}

$agentType = if ($payload -and $payload.agent_type) { $payload.agent_type } else { 'unknown' }

# 研究 / 探索 / 規劃類 subagent — 精簡注入（不寫 code，不需完整規範）
$lightAgents = @('claude-code-guide', 'Explore', 'Plan', 'statusline-setup')
if ($agentType -in $lightAgents) {
    Write-Output @"
---
## SubagentStart 注入（agent_type=$agentType）

- 輸出語言：產出物（文件 / 引用 / commit message）一律繁體中文
- 完整 project context：``.claude/CLAUDE.md`` + ``project-01-workflow`` skill + ``.claude/hooks/NOTES.md``
---
"@
    exit 0
}

# 編碼 / general-purpose / 其他類 — 完整規範注入
Write-Output @"
---
## SubagentStart 標準規範注入（agent_type=$agentType；2026-05-25 自動化）

### ⛔ 絕對禁止（PreToolUse hook 已強制執法）

1. **修改 ``myProgram/vendor/ActionGroupControl.py`` / ``myProgram/vendor/Board.py``** — 廠商 Hiwonder TonyPi SDK，改了破壞硬體通訊。只能 Read / import 使用。
2. **在 Windows 安裝任何依賴**（pip / npm / apt）— 執行環境是 Pi，本機只負責編輯與 git。
3. **用 ``git add -A`` / ``git add .``** — 必須明列檔名，避免誤加 ignored / 敏感檔。

### 🌏 強制規範

- **繁體中文**：所有產出物（程式碼註解、字串輸出、文件、commit message、markdown 中文）一律繁體中文（成果在台灣展示）。
- **Commit message**：結尾附 ``Co-Authored-By: Claude Opus <noreply@anthropic.com>``。
- **karpathy-guidelines**：寫程式時遵守 surgical / verifiable / no over-engineering / no premature abstraction / 看到不對立刻修。

### 📚 完整協議與領域知識（載入 project-01-workflow skill）

- 本專案所有 workflow（SDD / worktree / dispatch / 標準收尾 / Pi 端 / incremental-rebuild）+ myProgram 領域知識（廠商 SDK API / 線程 / 路徑 / sales 對話與 TTS 設計）都在 ``project-01-workflow`` skill。
- 編 ``myProgram/**/*.py`` 前：載入該 skill → Read 對應 reference（``reference/myprogram-vendor.md`` / ``myprogram-threading-paths.md`` / ``sales-dialog-design.md`` / ``sdd.md`` 等）。

### 🔗 完整文檔

- ``.claude/CLAUDE.md`` — 專案主規範入口（極簡核心：安全 + 繁中 + skill 觸發表）
- ``project-01-workflow`` skill — 完整 workflow 協議 + myProgram 領域知識（取代舊 ``.claude/rules/``）
- ``.claude/hooks/NOTES.md`` — hooks 自動化系統研究筆記
- ``resources/projectStructure/projectStructure.md`` — 專案目錄結構

### 主 agent 派發時可能塞的「任務特化」規則

如主 agent 在 prompt 內塞了：vendor-files / threading-conventions / 業務規格 / etc，請優先遵守。
---
"@

exit 0
