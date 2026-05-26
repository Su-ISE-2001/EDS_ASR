$ErrorActionPreference = "Stop"

param(
  [string]$AudioPath = "..\data\audio\record_20260517_192717.wav",
  [string]$Endpoint = "http://127.0.0.1:9000/recognize"
)

if (!(Test-Path $AudioPath)) {
  throw "Audio file not found: $AudioPath"
}

$form = @{
  audio = Get-Item $AudioPath
}

$response = Invoke-RestMethod -Method Post -Uri $Endpoint -Form $form
$response | ConvertTo-Json -Depth 5
