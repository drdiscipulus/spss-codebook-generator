# SPSS Codebook Generator

Portable Windows/macOS app and CLI for generating R-friendly codebooks from SPSS
`.sav` and `.zsav` files.

SPSS datasets often contain the metadata analysts need, but that information is
stored in the file's variable labels, value labels, and user-missing definitions
instead of in a readable codebook. This project extracts those metadata fields
and writes them as explicit Excel and CSV tables that are easy to inspect and
straightforward to import into R.

## Features

- Read SPSS `.sav` and `.zsav` files without SPSS.
- Export a human-readable Excel codebook.
- Export UTF-8 CSV tables with stable English column names for R workflows.
- Preserve raw SPSS codes while attaching variable labels and value labels.
- Mark SPSS user-missing values.
- Calculate optional observed frequencies.
- Show warnings for missing variable labels and partially labelled variables.
- Provide a basic desktop viewer for data preview and codebook tables.

## Output files

For an output name such as `study_codebook`, the app can write:

- `study_codebook_codebook.xlsx`
- `study_codebook_variables.csv`
- `study_codebook_value_labels.csv`
- `study_codebook_missing_values.csv`
- `study_codebook_warnings.csv`

The Excel workbook contains the same four codebook sheets as the CSV exports:

- `variables`
- `value_labels`
- `missing_values`
- `warnings`

## Output schema

`variables`

```text
variable_name, variable_label, storage_type, spss_format, measure,
has_value_labels, n_observed, n_missing, n_distinct_observed
```

`value_labels`

```text
variable_name, variable_label, value, value_label, is_user_missing,
observed_count, observed_percent, source
```

`missing_values`

```text
variable_name, missing_type, value, lower, upper, label
```

`warnings`

```text
severity, variable_name, value, message
```

## GUI usage

Start the desktop app:

```powershell
spss-codebook-gui
```

Then:

1. Select an input `.sav` or `.zsav` file.
2. Enter an output name.
3. Select an output folder.
4. Choose Excel and/or CSV export.
5. Optionally disable frequency calculation for very large files.
6. Load the preview or export the codebook.

The data preview shows the first 500 rows. If a value label exists, cells are
displayed as `code - label`; otherwise the raw value is shown.

## CLI usage

```powershell
spss-codebook input.sav --output-dir . --output-name study_codebook
```

Useful flags:

- `--no-excel`
- `--no-csv`
- `--no-frequencies`
- `--overwrite`
- `--preview-rows 500`

## Development

Use Python 3.12.

```powershell
py -3.12 -m pip install -e ".[dev]"
py -3.12 -m pytest
```

The test suite creates a small synthetic `.sav` fixture, so no private SPSS data
is required for automated tests.

## Windows build

```powershell
.\scripts\build_windows.ps1
```

The Windows build creates `dist/SPSS-Codebook-Generator-Windows.zip`.

## macOS build

```bash
./scripts/build_macos.sh
```

The macOS build creates `dist/SPSS Codebook Generator.app`. Signing,
notarization, and DMG packaging are intentionally left for a later release step.

## Limitations

- Raw dataset export is intentionally out of scope for V1.
- Multiple-response sets and advanced SPSS metadata are not handled yet.
- Frequency calculation reads the dataset and can take time for large files.
- CodeRabbit CLI review requires WSL on Windows; native Windows PowerShell is
  not enough for the official CodeRabbit CLI installer.
- No project license has been selected yet.
