# Instala dependencias de backend y frontend (primera vez).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location "$root\backend"
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e ".[dev]"
Set-Location "$root\frontend"
npm install
Write-Host "Listo. Ejecutá scripts\dev.ps1 para desarrollar."
