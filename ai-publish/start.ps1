#Requires -Version 5.1
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $RootDir "backend"
$VenvDir = Join-Path $BackendDir ".venv"
$Port = if ($env:PORT) { $env:PORT } else { "8765" }
$HostAddr = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }

Set-Location $BackendDir

if (-not (Test-Path $VenvDir)) {
  Write-Host "[setup] 创建 Python 虚拟环境..."
  python -m venv $VenvDir
}

$Python = Join-Path $VenvDir "Scripts\python.exe"
$Pip = Join-Path $VenvDir "Scripts\pip.exe"

& $Python -c "import fastapi" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "[setup] 安装依赖..."
  & $Pip install -U pip
  & $Pip install -r requirements.txt
}

New-Item -ItemType Directory -Force -Path "data\materials", "data\cookies" | Out-Null

$EnvFile = Join-Path $RootDir ".env"
if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $pair = $_ -split '=', 2
    if ($pair.Length -eq 2) {
      [System.Environment]::SetEnvironmentVariable($pair[0].Trim(), $pair[1].Trim(), "Process")
    }
  }
}

$env:DATABASE_URL = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "sqlite:///./data/aipublish.db" }
$env:STORAGE_LOCAL_PATH = "./data/materials"
$env:COOKIE_DIR = "./data/cookies"
$SauPath = Resolve-Path (Join-Path $RootDir "..\vendor\social-auto-upload")
$env:SAU_VENDOR_PATH = $SauPath.Path
if (-not $env:PLAYWRIGHT_HEADLESS) { $env:PLAYWRIGHT_HEADLESS = "false" }
if (-not $env:PLAYWRIGHT_CHANNEL) { $env:PLAYWRIGHT_CHANNEL = "chrome" }

Write-Host "=========================================="
Write-Host " AI 多平台内容自动发布系统 — MVP"
Write-Host "=========================================="
Write-Host " API 文档:  http://${HostAddr}:${Port}/docs"
Write-Host " 管理后台:  http://${HostAddr}:${Port}/app/"
Write-Host " 健康检查:  http://${HostAddr}:${Port}/health"
Write-Host " 默认账号:  admin / admin123"
Write-Host " 扫码模式:  PLAYWRIGHT_HEADLESS=$($env:PLAYWRIGHT_HEADLESS)"
Write-Host " 按 Ctrl+C 停止服务"
Write-Host "=========================================="

& (Join-Path $VenvDir "Scripts\uvicorn.exe") app.main:app --reload --host $HostAddr --port $Port
