$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "AI Glasses setup" -ForegroundColor Cyan
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    & py -3.11 --version
    if ($LASTEXITCODE -ne 0) { throw "Python 3.11 was not found. Install Python 3.11 and enable the Python launcher." }
    & py -3.11 -m venv .venv
} else {
    throw "Python launcher 'py' was not found. Install Python 3.11 and enable the launcher."
}

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "models") | Out-Null
Write-Host "Setup complete. Run .\launch.ps1." -ForegroundColor Green
Write-Host "AI models and physical glasses are NOT configured yet." -ForegroundColor Yellow
