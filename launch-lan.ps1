$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "Environment not found. Run .\setup.ps1 first." }
if (-not (Test-Path (Join-Path $PSScriptRoot ".dashboard-pin"))) { throw "Dashboard PIN missing. Run .\setup.ps1 first." }
if (-not (Test-Path (Join-Path $PSScriptRoot ".device-token"))) { throw "Device pairing token missing. Run .\setup.ps1 first." }

Write-Host "LAN mode exposes the dashboard to devices on your current network." -ForegroundColor Yellow
Write-Host "Use only a trusted private Wi-Fi/hotspot. Do not use public Wi-Fi." -ForegroundColor Yellow
$confirm = Read-Host "Continue with PIN-protected dashboard? (Y/N)"
if ($confirm -notmatch "^[Yy]$") { exit 0 }

$env:GLASSES_LAN_MODE = "1"
Write-Host "Dashboard: http://<THIS-LAPTOP-LAN-IP>:8765" -ForegroundColor Cyan
Write-Host "Use ipconfig to find this laptop's IPv4 address." -ForegroundColor Cyan
Write-Host "Dashboard API requires the generated PIN; device API requires .device-token." -ForegroundColor Green
& $venvPython -m uvicorn laptop.app:app --host 0.0.0.0 --port 8765
