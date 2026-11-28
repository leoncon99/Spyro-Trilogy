# package.ps1 - builds "Spyro Recomp Trilogy" as a standalone Windows program.
#
# Result: dist\Spyro Recomp Trilogy\Spyro Recomp Trilogy.exe  (+ dist\SpyroRecompTrilogy-<version>.zip)
# Run in this script's folder:
#   powershell -ExecutionPolicy Bypass -File .\package.ps1
# Test run without packaging:
#   powershell -ExecutionPolicy Bypass -File .\package.ps1 -RunOnly

param([switch]$RunOnly)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Python {
    # pywebview (pythonnet) needs Python 3.11 to 3.13.
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
        Write-Host "No suitable Python (3.11 to 3.13) found." -ForegroundColor Red
        Write-Host "Installed versions:"
        & py -0p 2>$null
        Write-Host ""
        Write-Host "Please install Python 3.12 and run this script again:" -ForegroundColor Yellow
        Write-Host "  winget install Python.Python.3.12"
        exit 1
    }
    Write-Host "Creating Python environment with $base ..." -ForegroundColor Cyan
    & $base -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create the virtual environment" }
}
$py = ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install --quiet "pywebview>=5.4" "tomlkit>=0.13" "pyinstaller>=6.10"

if ($RunOnly) {
    & $py app.py
    exit $LASTEXITCODE
}

$version = (Select-String -Path backend\api.py -Pattern 'VERSION = "(.*)"').Matches[0].Groups[1].Value
Write-Host "Packaging Spyro Recomp Trilogy $version ..." -ForegroundColor Cyan
& $py -m PyInstaller --noconfirm --clean --windowed `
    --name "Spyro Recomp Trilogy" `
    --icon assets\app.ico `
    --add-data "ui;ui" `
    --add-data "kits;kits" `
    --add-data "assets;assets" `
    --collect-all webview `
    app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Copy-Item README.txt "dist\Spyro Recomp Trilogy\" -Force
# Lets .NET load the app's DLLs even if Windows marked them as downloaded
# (second line of defence next to unblock_own_files() in app.py).
$config = @"
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <runtime>
    <loadFromRemoteSources enabled="true"/>
  </runtime>
</configuration>
"@
Set-Content -Path "dist\Spyro Recomp Trilogy\Spyro Recomp Trilogy.exe.config" -Value $config -Encoding utf8
$zip = "dist\SpyroRecompTrilogy-$version.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path "dist\Spyro Recomp Trilogy" -DestinationPath $zip
# Checksum for the in-app updater: upload BOTH files to the GitHub release.
$hash = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
Set-Content -Path "$zip.sha256" -Value "$hash  SpyroRecompTrilogy-$version.zip" -Encoding ascii -NoNewline
Write-Host ""
Write-Host "Done: dist\Spyro Recomp Trilogy\Spyro Recomp Trilogy.exe" -ForegroundColor Green
Write-Host "      $zip"
Write-Host "      $zip.sha256"
Write-Host ""
Write-Host "For a GitHub release upload both files (the app updater needs the .sha256)." -ForegroundColor Yellow
