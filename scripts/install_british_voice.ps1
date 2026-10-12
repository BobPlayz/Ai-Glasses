$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$ttsDir = Join-Path (Get-Location) "models\tts"
New-Item -ItemType Directory -Force -Path $ttsDir | Out-Null
$voiceFiles = @(
    @{ Name = "en_GB-alan-medium.onnx"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx?download=true" },
    @{ Name = "en_GB-alan-medium.onnx.json"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json?download=true" },
    @{ Name = "te_IN-venkatesh-medium.onnx"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/te/te_IN/venkatesh/medium/te_IN-venkatesh-medium.onnx?download=true" },
    @{ Name = "te_IN-venkatesh-medium.onnx.json"; Url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/te/te_IN/venkatesh/medium/te_IN-venkatesh-medium.onnx.json?download=true" }
)
foreach ($voiceFile in $voiceFiles) {
    $destination = Join-Path $ttsDir $voiceFile.Name
    if (-not (Test-Path $destination) -or (Get-Item $destination).Length -lt 1000) {
        Write-Host ("Downloading " + $voiceFile.Name) -ForegroundColor Cyan
        Invoke-WebRequest -Uri $voiceFile.Url -OutFile $destination -UseBasicParsing
    }
    if ((Get-Item $destination).Length -lt 1000) { throw ("Voice file looks incomplete: " + $voiceFile.Name) }
}
$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) { throw "Python environment missing. Run setup.ps1 first." }
& $venvPython (Join-Path $PSScriptRoot "verify_voice_assets.py")
if ($LASTEXITCODE -ne 0) { throw "English/Telugu voice verification failed." }
Write-Host "Offline conversational English and Telugu neural voice assets are installed and verified." -ForegroundColor Green
Write-Host "Restart AI Glasses to use it." -ForegroundColor Green
