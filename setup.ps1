$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$readyMarker = Join-Path $PSScriptRoot "data\.setup-complete"
if (Test-Path $readyMarker) { Remove-Item $readyMarker -Force }
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " AI Glasses full setup" -ForegroundColor Cyan
Write-Host " This prepares software, local models, and candidate firmware."
Write-Host "========================================" -ForegroundColor Cyan

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
& $venvPython -m pip install -r requirements-firmware.txt
if ($LASTEXITCODE -ne 0) { throw "PlatformIO installation failed." }

New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data\temp") | Out-Null

# Generate local secrets once. These files are excluded from Git.
$pinPath = Join-Path $PSScriptRoot ".dashboard-pin"
if (-not (Test-Path $pinPath)) {
    $pin = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 16 | ForEach-Object { [char]$_ })
    Set-Content -Path $pinPath -Value $pin -NoNewline
    Write-Host "Created local dashboard PIN: $pin" -ForegroundColor Yellow
    Write-Host "Save it privately. It is not committed to Git." -ForegroundColor Yellow
}
$deviceTokenPath = Join-Path $PSScriptRoot ".device-token"
if (-not (Test-Path $deviceTokenPath)) {
    $bytes = New-Object byte[] 32
    $rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
    $rng.GetBytes($bytes)
    $rng.Dispose()
    $token = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+','-').Replace('/','_')
    Set-Content -Path $deviceTokenPath -Value $token -NoNewline
    Write-Host "Created local device pairing token in .device-token." -ForegroundColor Yellow
}

$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw "Ollama is missing and winget is unavailable. Install Ollama from https://ollama.com/download/windows, reopen PowerShell, and rerun setup." }
    & winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Ollama installation failed." }
    $ollama = Get-Command ollama -ErrorAction SilentlyContinue
    if (-not $ollama) { throw "Ollama was installed. Close and reopen PowerShell, then rerun .\setup.ps1 to continue model setup." }
}

Write-Host "Caching multilingual Whisper speech model..." -ForegroundColor Cyan
$env:GLASSES_MODEL_CACHE = Join-Path $PSScriptRoot "models\whisper"
& $venvPython -c "from faster_whisper import WhisperModel; import os; WhisperModel('base', device='cpu', compute_type='int8', download_root=os.environ['GLASSES_MODEL_CACHE'])"
if ($LASTEXITCODE -ne 0) { throw "Whisper model download failed. Fix the connection and rerun setup." }

Write-Host "Caching offline neural English and Telugu voices..." -ForegroundColor Cyan
$ttsDir = Join-Path $PSScriptRoot "models\tts"
New-Item -ItemType Directory -Force -Path $ttsDir | Out-Null
$voiceFiles = @(
    @{ Name = "en_US-lessac-medium.onnx"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx?download=true" },
    @{ Name = "en_US-lessac-medium.onnx.json"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json?download=true" },
    @{ Name = "te_IN-maya-medium.onnx"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/te/te_IN/maya/medium/te_IN-maya-medium.onnx?download=true" },
    @{ Name = "te_IN-maya-medium.onnx.json"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/te/te_IN/maya/medium/te_IN-maya-medium.onnx.json?download=true" }
)
foreach ($voiceFile in $voiceFiles) {
    $destination = Join-Path $ttsDir $voiceFile.Name
    if (-not (Test-Path $destination)) {
        Invoke-WebRequest -Uri $voiceFile.Url -OutFile $destination -UseBasicParsing
        if ($LASTEXITCODE -ne 0) { throw "Voice download failed: $($voiceFile.Name)" }
    }
    if ((Get-Item $destination).Length -lt 1000) { throw "Voice file looks incomplete: $($voiceFile.Name). Delete it and rerun setup." }
}

Write-Host "Caching local text models..." -ForegroundColor Cyan
& ollama pull qwen2.5:1.5b
if ($LASTEXITCODE -ne 0) { throw "Primary language model download failed." }
& ollama pull qwen2.5:0.5b
if ($LASTEXITCODE -ne 0) { throw "Fallback language model download failed." }
Write-Host "Caching local vision model..." -ForegroundColor Cyan
& ollama pull moondream:1.8b
if ($LASTEXITCODE -ne 0) { throw "Vision model download failed." }

Write-Host "Installing local OCR engine..." -ForegroundColor Cyan
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) { throw "Windows Package Manager is required to install the local OCR engine." }
& winget install --id UB-Mannheim.TesseractOCR -e --accept-package-agreements --accept-source-agreements
if ($LASTEXITCODE -ne 0) {
    $tesseractExisting = Get-Command tesseract -ErrorAction SilentlyContinue
    if (-not $tesseractExisting -and -not (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) { throw "Tesseract installation failed." }
}
$tesseractExisting = Get-Command tesseract -ErrorAction SilentlyContinue
if (-not $tesseractExisting -and -not (Test-Path "C:\Program Files\Tesseract-OCR\tesseract.exe")) { throw "Tesseract binary is missing after installation." }
$tessdataDir = Join-Path $PSScriptRoot "models\tesseract\tessdata"
New-Item -ItemType Directory -Force -Path $tessdataDir | Out-Null
foreach ($lang in @("eng", "tel")) {
    $langPath = Join-Path $tessdataDir ($lang + ".traineddata")
    if (-not (Test-Path $langPath)) {
        Invoke-WebRequest -Uri ("https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/" + $lang + ".traineddata") -OutFile $langPath -UseBasicParsing
    }
    if ((Get-Item $langPath).Length -lt 100000) { throw "OCR language model $lang looks incomplete." }
}

Write-Host "Verifying both offline neural voices can synthesize audio..." -ForegroundColor Cyan
& $venvPython (Join-Path $PSScriptRoot "scripts\verify_voice_assets.py")
if ($LASTEXITCODE -ne 0) { throw "Offline neural voice verification failed." }

Write-Host "Compiling candidate ESP32-S3 firmware..." -ForegroundColor Cyan
& (Join-Path $PSScriptRoot ".venv\Scripts\pio.exe") run -d (Join-Path $PSScriptRoot "firmware\xiao-esp32s3-sense")
if ($LASTEXITCODE -ne 0) { throw "Candidate firmware compile failed. Do not launch the full project until the compile error is fixed." }

Write-Host "Verifying cached Whisper model works offline..." -ForegroundColor Cyan
& $venvPython -c "from faster_whisper import WhisperModel; import os; WhisperModel('base', device='cpu', compute_type='int8', download_root=os.environ['GLASSES_MODEL_CACHE'], local_files_only=True)"
if ($LASTEXITCODE -ne 0) { throw "Offline Whisper cache verification failed." }

& ollama list
New-Item -ItemType File -Force -Path (Join-Path $PSScriptRoot "data\.setup-complete") | Out-Null
Write-Host ""
Write-Host "Setup finished: Python dependencies, local model assets, secrets, and candidate firmware compile are ready." -ForegroundColor Green
Write-Host "The first app launch is now gated on these checks." -ForegroundColor Green
Write-Host "Keep .dashboard-pin and .device-token private." -ForegroundColor Yellow
