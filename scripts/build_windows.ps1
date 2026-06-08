$ErrorActionPreference = "Stop"

py -3.12 -m pip install -e ".[dev]"
py -3.12 -m PyInstaller `
  --noconfirm `
  --clean `
  --onedir `
  --windowed `
  --name "SPSS Codebook Generator" `
  --specpath "build/pyinstaller" `
  --collect-all pyreadstat `
  --exclude-module pytest `
  --exclude-module py `
  --exclude-module pygments `
  "src/spss_codebook/gui_entry.py"

$zipPath = "dist/SPSS-Codebook-Generator-Windows.zip"
if (Test-Path $zipPath) {
  Remove-Item $zipPath -Force
}
Compress-Archive -Path "dist/SPSS Codebook Generator" -DestinationPath $zipPath
Write-Host "Created $zipPath"
