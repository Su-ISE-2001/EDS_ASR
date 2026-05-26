$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (!(Test-Path ".venv")) {
  python -m venv .venv
}

& ".\.venv\Scripts\activate.ps1"
python -m pip install -r requirements.txt

python -m uvicorn app:app --host 0.0.0.0 --port 9100
