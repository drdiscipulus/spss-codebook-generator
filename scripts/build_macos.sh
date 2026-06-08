#!/usr/bin/env bash
set -euo pipefail

python3.12 -m pip install -e ".[dev]"
python3.12 -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --windowed \
  --name "SPSS Codebook Generator" \
  --specpath build/pyinstaller \
  --collect-all pyreadstat \
  --exclude-module pytest \
  --exclude-module py \
  --exclude-module pygments \
  src/spss_codebook/gui_entry.py

echo "Created dist/SPSS Codebook Generator.app"
