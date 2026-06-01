# PreToolUse hook：擋 Windows 本機安裝依賴指令（CLAUDE.md ⛔#2 確定性強制執法）
#
# 守的範圍：Bash / PowerShell tool 內的 pip / npm / apt / yarn / pnpm install 類指令。
# 執行環境是 Pi，本機只負責編輯與 git；本機裝依賴沒意義且污染環境。
# 例外：pytest 已全域裝（純測試框架），本 hook 不攔 pytest / python -m pytest。
#
# 輸入：stdin JSON（含 tool_input.command）
# 輸出：JSON 決策（deny）；通過則 exit 0 無輸出。

$ErrorActionPreference = 'Stop'

# 修正 PowerShell 5.1 預設 OutputEncoding 為系統 code page（本機 = cp936/GBK）；
# Claude 讀 hook stdout 預期 UTF-8 — 不修繁中 deny reason 會亂碼。
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) { exit 0 }

try { $payload = $rawInput | ConvertFrom-Json } catch { exit 0 }

$cmd = $payload.tool_input.command
if ([string]::IsNullOrWhiteSpace($cmd)) { exit 0 }

# 命中：pip/pip3 install、python -m pip install、npm install/i/ci/add、
# pnpm/yarn install/add、apt/apt-get install（含 sudo 前綴）。
# 不攔：pytest、python -m pytest、pip list/show/freeze 等唯讀子命令。
$pattern = '(?i)(\bpip3?\s+install\b|\bpython3?(\.\d+)?\s+-m\s+pip\s+install\b|\bnpm\s+(install|i|ci|add)\b|\b(pnpm|yarn)\s+(install|add)\b|\bapt(-get)?\s+install\b)'

if ($cmd -match $pattern) {
    $decision = @{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'deny'
            permissionDecisionReason = "⛔ 禁止在 Windows 本機安裝依賴（CLAUDE.md ⛔#2）。執行環境是 Raspberry Pi，本機只負責編輯與 git；本機裝套件沒意義。若 Pi 端需要套件，寫入 resources/pineedtodo/ 由使用者在 Pi 上執行。（pytest 已全域裝為例外，不受此限）"
        }
    }
    $decision | ConvertTo-Json -Depth 10 -Compress
    exit 0
}

exit 0
