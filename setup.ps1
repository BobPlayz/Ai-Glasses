$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "AI Glasses setup" -ForegroundColor Cyan

$py = Get-Command py -ErrorAction SilentlyContinue
if (-not $py) { throw "Python launcher 'py' not found. Install Python 3.11 and enable the launcher." }
& py -3.11 --version
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 not found. Install Python 3.11 before continuing." }

if (-not (Test-Path (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"))) {
    & py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python virtual environment." }
}
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Python dependency installation failed." }

New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "models") | Out-Null

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    Write-Host "Ollama is required for local language-model answers." -ForegroundColor Yellow
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        $install = Read-Host "Install Ollama using Windows Package Manager now? Internet required (Y/N)"
        if ($install -match "^[Yy]$") {
            & winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -ne 0) { throw "Ollama installation failed. Install from ollama.com/download/windows and rerun setup." }
            $ollama = Get-Command ollama -ErrorAction SilentlyContinue
        }
    }
}

Write-Host ""
$cacheWhisper = Read-Host "Download/cache the multilingual Whisper base speech model now? This requires internet and about 150 MB (Y/N)"
if ($cacheWhisper -match "^[Yy]$") {
    $env:GLASSES_MODEL_CACHE = Join-Path $PSScriptRoot "models\whisper"
    & $venvPython -c "from faster_whisper import WhisperModel; import os; WhisperModel('base', device='cpu', compute_type='int8', download_root=os.environ['GLASSES_MODEL_CACHE'])"
    if ($LASTEXITCODE -ne 0) { throw "Whisper model cache failed. Check internet access and rerun setup." }
} else {
    Write-Host "Whisper model cache skipped. Offline speech recognition will not work until cached." -ForegroundColor Yellow
}

if ($ollama) {
    Write-Host "Model downloads happen now, not during questions." -ForegroundColor Cyan
    $pull = Read-Host "Download qwen2.5:1.5b and qwen2.5:0.5b? Several GB may be downloaded (Y/N)"
    if ($pull -match "^[Yy]$") {
        & ollama pull qwen2.5:1.5b
        if ($LASTEXITCODE -ne 0) { throw "Primary model download failed. Rerun setup after fixing the connection." }
        & ollama pull qwen2.5:0.5b
        if ($LASTEXITCODE -ne 0) { throw "Fallback model download failed. Rerun setup after fixing the connection." }
    } else {
        Write-Host "Model downloads skipped. Local answers remain unavailable until models are cached." -ForegroundColor Yellow
    }
    $pullVision = Read-Host "Also download the candidate vision model moondream:1.8b? It may use substantial RAM during vision tasks (Y/N)"
    if ($pullVision -match "^[Yy]$") {
        & ollama pull moondream:1.8b
        if ($LASTEXITCODE -ne 0) { Write-Host "Vision model download failed; text model setup is still usable." -ForegroundColor Yellow }
    }
} else {
    Write-Host "Ollama not installed. Dashboard can open, but local AI answers will not work yet." -ForegroundColor Yellow
}
Write-Host "Python environment and dependencies are ready." -ForegroundColor Green
Write-Host "Before offline testing, ensure Ollama and both model files are installed." -ForegroundColor Yellow
Write-Host "Next command: .\launch.ps1" -ForegroundColor Cyan
