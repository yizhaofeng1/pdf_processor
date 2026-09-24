# ==============================================================================
# ExamSplit AI - Windows PowerShell 打包脚本
# ==============================================================================
$ErrorActionPreference = "Stop"

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$ScriptDir/.."

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " ExamSplit AI - Windows 独立发行版构建程序" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

python scripts/build.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "打包失败，请检查上方日志输出！"
    exit $LASTEXITCODE
}
