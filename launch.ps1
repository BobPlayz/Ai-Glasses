$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "Environment not found. Run .\setup.ps1 first." }
Write-Host "Starting AI Glasses local dashboard..." -ForegroundColor Cyan
Write-Host "Dashboard: http://127.0.0.1:8765" -ForegroundColor Green
Write-Host "Localhost only; phone/LAN access is intentionally disabled." -ForegroundColor Yellow
Write-Host "Model, speech, vision, and device status are shown in the dashboard." -ForegroundColor Yellow
& $venvPython -m uvicorn laptop.app:app --host 127.0.0.1 --port 8765
