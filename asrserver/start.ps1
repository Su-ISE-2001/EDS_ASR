$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (!(Test-Path ".venv")) {
  python -m venv .venv
}

& ".\.venv\Scripts\activate.ps1"
python -m pip install -r requirements.txt

if (!$env:ASR_MODEL_PATH) {
  $env:ASR_MODEL_PATH = Join-Path $scriptDir "models\vosk-model-small-cn-0.22"
}

if (!$env:ASR_ENGINE) {
  $env:ASR_ENGINE = "whisper"
}

if (!$env:ASR_WHISPER_MODEL) {
  $env:ASR_WHISPER_MODEL = "small"
}

if (!$env:ASR_WHISPER_DEVICE) {
  $env:ASR_WHISPER_DEVICE = "cpu"
}

if (!$env:ASR_WHISPER_COMPUTE_TYPE) {
  $env:ASR_WHISPER_COMPUTE_TYPE = "int8"
}

if (!$env:ASR_WHISPER_LANGUAGE) {
  $env:ASR_WHISPER_LANGUAGE = "zh"
}

Write-Host "ASR_MODEL_PATH=$env:ASR_MODEL_PATH"
Write-Host "ASR_ENGINE=$env:ASR_ENGINE"
Write-Host "ASR_WHISPER_MODEL=$env:ASR_WHISPER_MODEL"
Write-Host "ASR_WHISPER_DEVICE=$env:ASR_WHISPER_DEVICE"
Write-Host "ASR_WHISPER_COMPUTE_TYPE=$env:ASR_WHISPER_COMPUTE_TYPE"
Write-Host "ASR_WHISPER_LANGUAGE=$env:ASR_WHISPER_LANGUAGE"
python -m uvicorn server:app --host 0.0.0.0 --port 9000
