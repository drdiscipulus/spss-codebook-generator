from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import CodebookResult


@dataclass(frozen=True)
class ExportOptions:
    """User-selected export destination and output format choices."""

    output_dir: Path
    output_name: str
    export_excel: bool = True
    export_csv: bool = True
    overwrite: bool = False


@dataclass(frozen=True)
class ExportResult:
    """Paths written by one export operation."""

    written_files: list[Path]


def export_codebook(result: CodebookResult, options: ExportOptions) -> ExportResult:
    """Write codebook tables to the selected Excel and/or CSV outputs."""

    output_dir = Path(options.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = _clean_output_name(options.output_name)
    paths = expected_output_paths(output_dir, output_name, options.export_excel, options.export_csv)

    if not options.overwrite:
        existing = [path for path in paths if path.exists()]
        if existing:
            existing_names = ", ".join(path.name for path in existing)
            raise FileExistsError(f"Output file(s) already exist: {existing_names}")

    written_files: list[Path] = []
    if options.export_excel:
        excel_path = output_dir / f"{output_name}_codebook.xlsx"
        with result_to_excel_writer(excel_path) as writer:
            result.variables.to_excel(writer, sheet_name="variables", index=False)
            result.value_labels.to_excel(writer, sheet_name="value_labels", index=False)
            result.missing_values.to_excel(writer, sheet_name="missing_values", index=False)
            result.warnings.to_excel(writer, sheet_name="warnings", index=False)
        written_files.append(excel_path)

    if options.export_csv:
        csv_tables = {
            "variables": result.variables,
            "value_labels": result.value_labels,
            "missing_values": result.missing_values,
            "warnings": result.warnings,
        }
        for suffix, table in csv_tables.items():
            csv_path = output_dir / f"{output_name}_{suffix}.csv"
            table.to_csv(csv_path, index=False, encoding="utf-8")
            written_files.append(csv_path)

    return ExportResult(written_files=written_files)


def expected_output_paths(
    output_dir: Path,
    output_name: str,
    export_excel: bool,
    export_csv: bool,
) -> list[Path]:
    """Return every path that may be written for overwrite checks."""

    output_name = _clean_output_name(output_name)
    paths: list[Path] = []
    if export_excel:
        paths.append(output_dir / f"{output_name}_codebook.xlsx")
    if export_csv:
        paths.extend(
            [
                output_dir / f"{output_name}_variables.csv",
                output_dir / f"{output_name}_value_labels.csv",
                output_dir / f"{output_name}_missing_values.csv",
                output_dir / f"{output_name}_warnings.csv",
            ]
        )
    return paths


def result_to_excel_writer(path: Path):
    import pandas as pd

    return pd.ExcelWriter(path, engine="openpyxl")


def _clean_output_name(output_name: str) -> str:
    """Make a user-supplied output stem safe for Windows and macOS file names."""

    cleaned = output_name.strip()
    if not cleaned:
        raise ValueError("output_name must not be empty.")
    illegal = '<>:"/\\|?*'
    for char in illegal:
        cleaned = cleaned.replace(char, "_")
    return cleaned
