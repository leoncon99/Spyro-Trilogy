# PAKETIEREN.ps1 - baut "Spyro Trilogy" als eigenstaendiges Windows-Programm.
#
# Ergebnis: dist\Spyro Trilogy\Spyro Trilogy.exe  (+ dist\SpyroTrilogy-<Version>.zip)
# Aufruf im Ordner dieses Skripts:
#   powershell -ExecutionPolicy Bypass -File .\PAKETIEREN.ps1
# Testlauf ohne Paketieren:
#   powershell -ExecutionPolicy Bypass -File .\PAKETIEREN.ps1 -NurStarten

param([switch]$NurStarten)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .venv)) {
    Write-Host "Lege Python-Umgebung an ..." -ForegroundColor Cyan
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { py -m venv .venv }
}
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install --quiet "pywebview>=5.4" "tomlkit>=0.13" "pyinstaller>=6.10"

if ($NurStarten) {
    & $py app.py
    exit $LASTEXITCODE
}

$version = (Select-String -Path backend\api.py -Pattern 'VERSION = "(.*)"').Matches[0].Groups[1].Value
Write-Host "Paketiere Spyro Trilogy $version ..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean --windowed `
    --name "Spyro Trilogy" `
    --icon assets\app.ico `
    --add-data "ui;ui" `
    --add-data "kits;kits" `
    --add-data "assets;assets" `
    --collect-all webview `
    app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller fehlgeschlagen" }

Copy-Item LIESMICH.txt "dist\Spyro Trilogy\" -Force
$zip = "dist\SpyroTrilogy-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\Spyro Trilogy" -DestinationPath $zip
Write-Host ""
Write-Host "Fertig: dist\Spyro Trilogy\Spyro Trilogy.exe" -ForegroundColor Green
Write-Host "        $zip"
