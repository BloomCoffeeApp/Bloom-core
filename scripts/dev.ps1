# Levanta backend (FastAPI con recarga) y frontend (Vite) en modo desarrollo.
# El puerto del backend sale de brand.json (o de la variable CAFE_PORT).
$root = Split-Path -Parent $PSScriptRoot
$brand = Get-Content "$root\brand.json" -Raw | ConvertFrom-Json
$port = if ($env:CAFE_PORT) { $env:CAFE_PORT } else { $brand.port }
Write-Host "$($brand.name): backend en http://127.0.0.1:$port  |  frontend en http://localhost:5173" -ForegroundColor Cyan
$reload = @("--reload-dir", "$root\backend\app")
# Pro edition linked (../pro/scripts/link.ps1): reload on its changes too.
if (Test-Path "$root\backend\bloom_pro") { $reload += @("--reload-dir", (Get-Item "$root\backend\bloom_pro").Target) }
Start-Process -NoNewWindow -FilePath "$root\backend\.venv\Scripts\python.exe" `
  -ArgumentList (@("-m", "uvicorn", "app.main:app", "--reload", "--port", "$port", "--app-dir", "$root\backend") + $reload)
Set-Location "$root\frontend"
npm run dev
