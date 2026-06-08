from __future__ import annotations

from pathlib import Path

from .core import CodebookResult, build_codebook
from .exporters import ExportOptions, ExportResult, export_codebook


def load_codebook(
    input_file: str | Path,
    *,
    calculate_frequencies: bool = True,
    preview_rows: int = 500,
) -> CodebookResult:
    """Load one SPSS file into the shared in-memory codebook representation."""

    return build_codebook(
        input_file,
        calculate_frequencies=calculate_frequencies,
        preview_rows=preview_rows,
    )


def write_codebook(result: CodebookResult, options: ExportOptions) -> ExportResult:
    """Write a prepared codebook using the shared exporter implementation."""

    return export_codebook(result, options)


def generate_and_export(
    input_file: str | Path,
    options: ExportOptions,
    *,
    calculate_frequencies: bool = True,
    preview_rows: int = 500,
) -> ExportResult:
    """Convenience wrapper for non-GUI callers that do not need preview state."""

    result = load_codebook(
        input_file,
        calculate_frequencies=calculate_frequencies,
        preview_rows=preview_rows,
    )
    return write_codebook(result, options)
