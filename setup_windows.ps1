# Setup thai-customs gateway on Windows (run once per machine).
# Needs: Python 3.11+ installed and on PATH.
# Usage:  powershell -ExecutionPolicy Bypass -File setup_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Need($cmd, $hint) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "MISSING: $cmd -- $hint" -ForegroundColor Red
    exit 1
  }
}

Need python "install Python 3.12 from https://www.python.org/downloads/ (tick 'Add to PATH')"
$ver = (python --version).Split()[1].Split(".")
if ([int]$ver[0] -lt 3 -or ([int]$ver[0] -eq 3 -and [int]$ver[1] -lt 11)) {
  Write-Host "Python 3.11+ required" -ForegroundColor Red
  exit 1
}

if (-not (Test-Path .venv/Scripts/python.exe)) {
  Write-Host "Creating .venv ..."
  python -m venv .venv
} else {
  Write-Host ".venv already exists, reusing it."
}
.venv/Scripts/python.exe -m pip install --upgrade pip
.venv/Scripts/python.exe -m pip install -r requirements.txt -r gateway/requirements.txt

if (-not (Test-Path gateway/.env)) {
  Copy-Item gateway/.env.example gateway/.env
  Write-Host "Created gateway/.env from example -- EDIT IT with real keys."
} else {
  Write-Host "gateway/.env already exists, leaving it."
}

Write-Host ""
Write-Host "Done. To run the web:" -ForegroundColor Green
Write-Host "  1) gcloud auth application-default login  (once; enables Firestore + AI)"
Write-Host "  2) edit gateway/.env  (STRIPE_SECRET_KEY etc.)"
Write-Host "  3) .\.venv\Scripts\uvicorn gateway.main:app --port 8001"
Write-Host "  4) open http://127.0.0.1:8001"
