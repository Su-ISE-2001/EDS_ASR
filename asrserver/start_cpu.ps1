$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (!(Test-Path ".venv")) {
  python -m venv .venv
}

& ".\.venv\Scripts\activate.ps1"
python -m pip install -r requirements.txt

if (!$env:ASR_ENGINE) { $env:ASR_ENGINE = "whisper" }
if (!$env:ASR_WHISPER_MODEL) { $env:ASR_WHISPER_MODEL = "g:\suzhou\asrserver\models\faster-whisper-small" }
if (!$env:ASR_WHISPER_DEVICE) { $env:ASR_WHISPER_DEVICE = "cpu" }
if (!$env:ASR_WHISPER_COMPUTE_TYPE) { $env:ASR_WHISPER_COMPUTE_TYPE = "int8" }
if (!$env:ASR_WHISPER_LANGUAGE) { $env:ASR_WHISPER_LANGUAGE = "zh" }
if (!$env:ASR_WHISPER_ALLOW_CPU_FALLBACK) { $env:ASR_WHISPER_ALLOW_CPU_FALLBACK = "true" }

Write-Host "ASR_ENGINE=$env:ASR_ENGINE"
Write-Host "ASR_WHISPER_MODEL=$env:ASR_WHISPER_MODEL"
Write-Host "ASR_WHISPER_DEVICE=$env:ASR_WHISPER_DEVICE"
Write-Host "ASR_WHISPER_COMPUTE_TYPE=$env:ASR_WHISPER_COMPUTE_TYPE"
Write-Host "ASR_WHISPER_LANGUAGE=$env:ASR_WHISPER_LANGUAGE"
Write-Host "ASR_WHISPER_ALLOW_CPU_FALLBACK=$env:ASR_WHISPER_ALLOW_CPU_FALLBACK"

python -m uvicorn server:app --host 0.0.0.0 --port 9000
