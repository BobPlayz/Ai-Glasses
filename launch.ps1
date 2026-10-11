$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "Python environment missing. Run .\setup.ps1 and let it finish." }
if (-not (Test-Path (Join-Path $PSScriptRoot "data\.setup-complete"))) { throw "Full setup has not completed. Run .\setup.ps1 and let all model downloads and firmware compilation finish." }
if (-not (Test-Path (Join-Path $PSScriptRoot ".dashboard-pin"))) { throw "Dashboard PIN missing. Run .\setup.ps1." }
if (-not (Test-Path (Join-Path $PSScriptRoot ".device-token"))) { throw "Device token missing. Run .\setup.ps1." }

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) { throw "Ollama is unavailable in this PowerShell session. Reopen PowerShell and run .\setup.ps1." }
$models = (& ollama list | Out-String)
foreach ($required in @("qwen2.5:1.5b", "qwen2.5:0.5b", "moondream:1.8b")) {
    if ($models -notmatch [regex]::Escape($required)) { throw "Required local model $required is missing. Run .\setup.ps1." }
}
if (-not (Test-Path (Join-Path $PSScriptRoot "models\whisper"))) { throw "Whisper model cache missing. Run .\setup.ps1." }
foreach ($voice in @("en_GB-alan-medium.onnx", "en_GB-alan-medium.onnx.json", "te_IN-venkatesh-medium.onnx", "te_IN-venkatesh-medium.onnx.json")) {
    if (-not (Test-Path (Join-Path $PSScriptRoot ("models\tts\" + $voice)))) { throw "Offline voice asset $voice is missing. Run .\setup.ps1." }
}
$tesseract = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $tesseract -and -not (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) { throw "Local Tesseract OCR is missing. Run .\setup.ps1." }
foreach ($lang in @("eng", "tel")) {
    if (-not (Test-Path (Join-Path $PSScriptRoot ("models\tesseract\tessdata\" + $lang + ".traineddata")))) { throw "OCR language data $lang is missing. Run .\setup.ps1." }
}

Write-Host "All software/model preflight checks passed." -ForegroundColor Green
Write-Host "Dashboard: http://127.0.0.1:8765" -ForegroundColor Cyan
Write-Host "Localhost mode only. Use launch-lan.ps1 for PIN-protected phone access on a trusted network." -ForegroundColor Yellow
& $venvPython -m uvicorn laptop.app:app --host 127.0.0.1 --port 8765
