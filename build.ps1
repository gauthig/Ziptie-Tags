# Build the single-file Windows executable: dist\ZiptieTags.exe
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Step([string]$Label, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Label failed (exit code $LASTEXITCODE)" }
}

Invoke-Step "pip install" { python -m pip install -r requirements-dev.txt }
Invoke-Step "ruff"        { python -m ruff check . }
Invoke-Step "pytest"      { python -m pytest -q }

$version = (python -c "from ziptag import __version__; print(__version__)").Trim()
Write-Host "Building Ziptie Tags v$version"

# Work files go to %TEMP% because OneDrive can lock a build\ folder inside the repo.
$work = Join-Path $env:TEMP "ziptag_build"
$fonts = Join-Path $PSScriptRoot "fonts"
$templates = Join-Path $PSScriptRoot "templates"
Invoke-Step "PyInstaller" {
    python -m PyInstaller --noconfirm --clean --onefile --windowed --name ZiptieTags `
        --workpath $work --specpath $work --distpath dist `
        --add-data "${fonts};fonts" --add-data "${templates};templates" `
        ziptie_tags.py
}

# The exe must be able to build a project from its bundled resources.
$probe = Join-Path $env:TEMP "ziptag_selftest.3mf"
Remove-Item $probe -ErrorAction SilentlyContinue
Start-Process .\dist\ZiptieTags.exe -ArgumentList "--selftest", "`"$probe`"" -Wait -WindowStyle Hidden
if (-not (Test-Path $probe)) { throw "exe self-test failed: no project written" }

Write-Host "Done: dist\ZiptieTags.exe (v$version)"
