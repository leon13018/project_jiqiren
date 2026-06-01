# clean-pi-pycache.ps1
#
# 手動清除 Pi 端專案樹下所有 __pycache__ 目錄。
#
# 用途：Pi `git pull` 拉到新 commit 後，Python 可能 import stale .pyc 跑舊邏輯
#       （mtime invalidation 失準，見 reference/standard-workflow.md §Pi 端 pycache stale）。
#
# 平常不需手動跑——`.claude/hooks/auto-sync-pi.ps1` 在 sync 後已用獨立 try/catch 自動清。
# 本腳本是「懷疑 Pi 仍跑舊邏輯」時的手動補跑版本（idempotent，沒 pycache 也只是 find 返 0 個）。
#
# 用法（從 skill 內引用，跨安裝位置都正確）：
#   & "${CLAUDE_SKILL_DIR}/scripts/clean-pi-pycache.ps1"

$ErrorActionPreference = 'Continue'
$PiHost = 'pi@raspberrypi.local'
$PiPath = '/home/pi/Desktop/project_jiqiren'

Write-Host ">>> 清除 Pi 端 __pycache__ ($PiHost : $PiPath) ..."
ssh $PiHost "find $PiPath -name '__pycache__' -type d -exec rm -rf {} +"
if ($LASTEXITCODE -eq 0) {
    Write-Host "Done. Pi __pycache__ 已清乾淨。"
} else {
    Write-Host "WARN: ssh 回傳非 0（exit $LASTEXITCODE）——可能 SSH 連線問題，請手動確認。"
}
