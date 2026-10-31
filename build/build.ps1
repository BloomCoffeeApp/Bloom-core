# Genera el ejecutable de escritorio en build/output/<exeName>/<exeName>.exe
# y, si Inno Setup está instalado, el instalador en build/output/installer/.
# Nombre, colores y puerto salen de brand.json.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$py = "$root\backend\.venv\Scripts\python.exe"
$brand = Get-Content "$root\brand.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$version = (& $py -c "import sys; sys.path.insert(0, r'$root\backend'); from app.config import APP_VERSION; print(APP_VERSION)").Trim()

Write-Host "1/4 Compilando frontend..." -ForegroundColor Cyan
Push-Location "$root\frontend"
npm run build
if ($LASTEXITCODE -ne 0) { throw "Falló el build del frontend" }
Pop-Location

Write-Host "2/4 Generando ícono..." -ForegroundColor Cyan
& $py "$root\build\make_icon.py"

Write-Host "3/4 Empaquetando con PyInstaller..." -ForegroundColor Cyan
& $py -m PyInstaller "$root\build\cafeteria.spec" --noconfirm --clean `
  --distpath "$root\build\output" --workpath "$root\build\work"
if ($LASTEXITCODE -ne 0) { throw "Falló PyInstaller" }

$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($iscc) {
  Write-Host "4/4 Creando instalador con Inno Setup..." -ForegroundColor Cyan
  & $iscc "/DAppName=$($brand.name)" "/DAppExeName=$($brand.exeName)" "/DAppPublisher=$($brand.publisher)" `
    "/DAppVersion=$version" "$root\build\installer.iss"
} else {
  Write-Host "4/4 Inno Setup no encontrado: se omite el instalador (el .exe ya funciona)." -ForegroundColor Yellow
}
Write-Host "Listo: build\output\$($brand.exeName)\$($brand.exeName).exe" -ForegroundColor Green
