param(
  [string]$PythonExecutable = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$localPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$assetsPath = Join-Path $repoRoot "assets"

function Assert-NativeSuccess {
  param([string]$Step)
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE."
  }
}

Push-Location $repoRoot
try {
  if (-not $PythonExecutable) {
    if (-not (Test-Path -LiteralPath $localPython)) {
      py -3.12 -m venv .venv
      Assert-NativeSuccess "Creating the virtual environment"
    }
    $PythonExecutable = $localPython
  }

  & $PythonExecutable -m pip install -e ".[dev]"
  Assert-NativeSuccess "Installing dependencies"
  & $PythonExecutable -m pytest -q
  Assert-NativeSuccess "Running tests"
  & $PythonExecutable -m ruff check .
  Assert-NativeSuccess "Running Ruff"
  & $PythonExecutable "scripts/generate_icon.py"
  Assert-NativeSuccess "Generating the Windows icon"
  & $PythonExecutable -m PyInstaller `
    --noconfirm `
    --clean `
    --onedir `
    --windowed `
    --name "SPSS Codebook Rescue" `
    --icon "$assetsPath\app-icon.ico" `
    --add-data "$assetsPath\app-icon.svg;assets" `
    --add-data "$assetsPath\checkbox-checked.svg;assets" `
    --add-data "$assetsPath\checkbox-unchecked.svg;assets" `
    --specpath "build/pyinstaller" `
    --collect-all pyreadstat `
    --exclude-module pytest `
    --exclude-module py `
    --exclude-module pygments `
    "src/spss_codebook/gui_entry.py"
  Assert-NativeSuccess "Building the Windows application"

  $bundlePath = Join-Path $repoRoot "dist\SPSS Codebook Rescue"
  $zipPath = Join-Path $repoRoot "dist\SPSS-Codebook-Rescue-Windows.zip"
  $hashPath = "$zipPath.sha256"
  Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") `
    -Destination (Join-Path $bundlePath "LICENSE.txt") -Force
  Copy-Item -LiteralPath (Join-Path $repoRoot "README.md") `
    -Destination (Join-Path $bundlePath "README.md") -Force
  if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
  }
  if (Test-Path -LiteralPath $hashPath) {
    Remove-Item -LiteralPath $hashPath -Force
  }

  Compress-Archive -LiteralPath $bundlePath -DestinationPath $zipPath
  $hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
  "$hash  $(Split-Path -Leaf $zipPath)" | Set-Content -LiteralPath $hashPath -Encoding ascii

  Write-Host "Created $zipPath"
  Write-Host "Created $hashPath"
}
finally {
  Pop-Location
}
