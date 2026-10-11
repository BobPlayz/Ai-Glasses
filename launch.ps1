$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "Environment not found. Run .\setup.ps1 first." }
Write-Host "Local dashboard: http://127.0.0.1:8765" -ForegroundColor Cyan
Write-Host "No local LLM, speech engine, camera, or microphone is connected yet." -ForegroundColor Yellow
& $venvPython -m uvicorn laptop.app:app --host 127.0.0.1 --port 8765
