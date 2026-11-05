# Genera el ejecutable de escritorio en build/output/<exeName>/<exeName>.exe y, si Inno Setup
# está instalado, el instalador build/output/installer/<exeName>-Setup-<version>.exe más el
# manifiesto de actualización build/output/installer/latest.json (SIN firmar: se firma aparte,
# ver README → "Publicar una versión").
# Nombre, versión, colores y puerto salen de brand.json.
# -OutputDir <carpeta>: generar en otra carpeta (p. ej. si el .exe de build\output está abierto).
param([string]$OutputDir)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputDir) { $OutputDir = "$root\build\output" }
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$py = "$root\backend\.venv\Scripts\python.exe"
$brand = Get-Content "$root\brand.json" -Raw -Encoding UTF8 | ConvertFrom-Json
$version = "$($brand.version)".Trim()
if ($version -notmatch '^\d+(\.\d+){1,3}$') { throw "brand.json: version inválida '$version' (usá 1.2.3)" }
Write-Host "$($brand.name) $version" -ForegroundColor Cyan

Write-Host "1/4 Compilando frontend..." -ForegroundColor Cyan
Push-Location "$root\frontend"
npm run build
if ($LASTEXITCODE -ne 0) { throw "Falló el build del frontend" }
Pop-Location

# Avisos de licencias de terceros (lo que realmente se distribuye: bundle de Vite + dependencias de
# runtime de Python). Se incluyen en el .exe y se ven en Configuración → Acerca de.
& $py "$root\build\third_party_notices.py" --out "$root\build\generated"
if ($LASTEXITCODE -ne 0) { throw "No se pudieron generar los avisos de terceros" }

Write-Host "2/4 Generando ícono..." -ForegroundColor Cyan
& $py "$root\build\make_icon.py"

Write-Host "3/4 Empaquetando con PyInstaller..." -ForegroundColor Cyan
& $py -m PyInstaller "$root\build\cafeteria.spec" --noconfirm --clean `
  --distpath "$OutputDir" --workpath "$root\build\work"
if ($LASTEXITCODE -ne 0) { throw "Falló PyInstaller" }

# Inno Setup 6: instalación para todos (Program Files) o por usuario (winget --scope user).
$iscc = @(
  "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
  "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
  "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
if (-not $iscc) {
  $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($cmd) { $iscc = $cmd.Source }
}
if ($iscc) {
  Write-Host "4/4 Creando instalador con Inno Setup..." -ForegroundColor Cyan
  & $iscc /Q "/DAppName=$($brand.name)" "/DAppExeName=$($brand.exeName)" "/DAppPublisher=$($brand.publisher)" `
    "/DAppVersion=$version" "/DAppMutexName=$($brand.appId)-app-running" "/DSourceDir=$OutputDir\$($brand.exeName)" "/O$OutputDir\installer" `
    "$root\build\installer.iss"
  if ($LASTEXITCODE -ne 0) { throw "Falló Inno Setup" }
  $setupName = "$($brand.exeName)-Setup-$version.exe"
  $setup = "$OutputDir\installer\$setupName"
  & $py "$root\build\make_manifest.py" --installer $setup --version $version --brand "$root\brand.json" `
    --out "$OutputDir\installer\latest.json"
  if ($LASTEXITCODE -ne 0) { throw "No se pudo generar latest.json" }
  Write-Host "Instalador: $setup" -ForegroundColor Green
} else {
  Write-Host "4/4 Inno Setup no encontrado: se omite el instalador (el .exe ya funciona)." -ForegroundColor Yellow
}
Write-Host "Listo: $OutputDir\$($brand.exeName)\$($brand.exeName).exe" -ForegroundColor Green
