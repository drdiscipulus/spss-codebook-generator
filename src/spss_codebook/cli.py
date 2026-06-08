from __future__ import annotations

import argparse
from pathlib import Path

from .exporters import ExportOptions, export_codebook
from .workflow import load_codebook


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser used by tests and the installed console script."""

    parser = argparse.ArgumentParser(
        prog="spss-codebook",
        description="Generate Excel and CSV codebooks from SPSS .sav/.zsav files.",
    )
    parser.add_argument("input_file", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-name", required=True)
    parser.add_argument("--no-excel", action="store_true", help="Do not write the Excel codebook.")
    parser.add_argument("--no-csv", action="store_true", help="Do not write CSV codebook tables.")
    parser.add_argument("--no-frequencies", action="store_true", help="Leave frequency columns empty.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--preview-rows", type=int, default=500)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the command line workflow and return a process exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)

    export_excel = not args.no_excel
    export_csv = not args.no_csv
    if not export_excel and not export_csv:
        parser.error("At least one export format must be enabled.")

    try:
        result = load_codebook(
            args.input_file,
            calculate_frequencies=not args.no_frequencies,
            preview_rows=args.preview_rows,
        )
        export_result = export_codebook(
            result,
            ExportOptions(
                output_dir=args.output_dir,
                output_name=args.output_name,
                export_excel=export_excel,
                export_csv=export_csv,
                overwrite=args.overwrite,
            ),
        )
    except Exception as exc:
        parser.exit(1, f"error: {exc}\n")

    for path in export_result.written_files:
        print(path)
    return 0
