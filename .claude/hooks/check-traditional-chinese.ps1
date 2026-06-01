# PostToolUse(Edit|Write) hook：掃剛寫入的檔有無常見簡體字（CLAUDE.md 🌏 繁中規範 — 純警示）
#
# 設計：**純警示，絕不 block / 絕不擋任何流程**（exit 0 always，不輸出 decision deny）。
# 只在偵測到常見簡體字時印一段提醒（含檔名 + 命中字），讓主 agent / subagent 自行改繁體。
# 偵測用「簡體專有字」curated set（繁體幾乎不會用到的字），降低誤報；但仍可能偶有誤報，
# 因為純警示不擋流程，誤報成本低（看到提醒判斷一下即可）。
#
# 輸入：stdin JSON（含 tool_input.file_path）
# 輸出：stdout 警示文字（或無）；exit 0 always。

$ErrorActionPreference = 'Continue'

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) { exit 0 }
try { $payload = $rawInput | ConvertFrom-Json } catch { exit 0 }

$filePath = $payload.tool_input.file_path
if ([string]::IsNullOrWhiteSpace($filePath)) { exit 0 }
if (-not (Test-Path -LiteralPath $filePath -PathType Leaf)) { exit 0 }

# 只掃文字檔（副檔名白名單；其他直接跳過）
$ext = [System.IO.Path]::GetExtension($filePath).ToLower()
$textExt = @('.md', '.py', '.txt', '.ps1', '.json', '.js', '.ts', '.html', '.css', '.yml', '.yaml')
if ($ext -notin $textExt) { exit 0 }

try {
    $content = Get-Content -LiteralPath $filePath -Raw -Encoding UTF8 -ErrorAction Stop
} catch { exit 0 }
if ([string]::IsNullOrWhiteSpace($content)) { exit 0 }

# 常見「簡體專有字」集合（繁體對應字不同，繁體文本幾乎不會用到這些字形）。
# 非窮舉，取高頻、誤報低者。命中即提醒；漏網不影響（純警示安全網）。
$simplified = '这个们么见关说话语为对学时过还进种样让动会应该听点经发务实现项题单双习价仅测试门间问闻难顾显业严丰临举决际马鸟鱼车书长东专卖买卖图团园观规觉视讲谁贵宾资费达运过远连边达适迁'

$hits = @{}
foreach ($ch in $content.ToCharArray()) {
    if ($simplified.Contains($ch)) {
        if ($hits.ContainsKey($ch)) { $hits[$ch]++ } else { $hits[$ch] = 1 }
    }
}

if ($hits.Count -gt 0) {
    $list = ($hits.GetEnumerator() | Sort-Object -Property Value -Descending | ForEach-Object { "$($_.Key)×$($_.Value)" }) -join ' '
    Write-Output @"
---
🌏 繁中檢查（純警示，不擋流程）：``$filePath`` 偵測到疑似簡體字 — $list
請確認產出物用繁體中文（CLAUDE.md 🌏 規範，成果在台灣展示）。若為誤報（該字繁簡同形 / 引用原文）可忽略。
---
"@
}

exit 0
