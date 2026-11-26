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

function Find-Python {
    # pywebview (pythonnet) braucht Python 3.11 bis 3.13.
    $ErrorActionPreference = "Continue"
    foreach ($v in @("3.13", "3.12", "3.11")) {
        $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return $exe.Trim() }
    }
    foreach ($cmd in @("python", "python3")) {
        $exe = & $cmd -c "import sys; print(sys.executable) if (3,11) <= sys.version_info[:2] <= (3,13) else sys.exit(1)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe -and $exe -notmatch "WindowsApps") { return $exe.Trim() }
    }
    return $null
}

if (-not (Test-Path .venv\Scripts\python.exe)) {
    $base = Find-Python
    if (-not $base) {
        Write-Host "Kein passendes Python (3.11 bis 3.13) gefunden." -ForegroundColor Red
        Write-Host "Gefundene Versionen:"
        & py -0p 2>$null
        Write-Host ""
        Write-Host "Bitte Python 3.12 installieren und das Skript erneut starten:" -ForegroundColor Yellow
        Write-Host "  winget install Python.Python.3.12"
        exit 1
    }
    Write-Host "Lege Python-Umgebung an mit $base ..." -ForegroundColor Cyan
    & $base -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "venv konnte nicht angelegt werden" }
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
