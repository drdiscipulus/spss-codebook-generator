from __future__ import annotations

from pathlib import Path

import openpyxl
import pandas as pd
import pyreadstat
import pytest

from spss_codebook.cli import main as cli_main
from spss_codebook.core import (
    MISSING_VALUE_COLUMNS,
    VALUE_LABEL_COLUMNS,
    VARIABLE_COLUMNS,
    WARNING_COLUMNS,
    build_codebook,
)
from spss_codebook.exporters import ExportOptions, export_codebook
from spss_codebook.workflow import load_codebook, write_codebook


def write_fixture(path: Path) -> Path:
    df = pd.DataFrame(
        {
            "age": [1, 2, 99, 3, 7],
            "gender": [1, 2, 1, None, 3],
            "comment": ["a", "b", "x", "c", "d"],
        }
    )
    pyreadstat.write_sav(
        df,
        str(path),
        column_labels={
            "age": "Age group",
            "gender": "Gender",
            "comment": "",
        },
        variable_value_labels={
            "age": {
                1: "18-29",
                2: "30-44",
                3: "45-64",
                99: "No answer",
            },
            "gender": {
                1: "male",
                2: "female",
            },
        },
        missing_ranges={"age": [99]},
        variable_measure={"age": "ordinal", "gender": "nominal"},
    )
    return path


def test_codebook_extracts_labels_missing_values_and_warnings(tmp_path):
    sav_path = write_fixture(tmp_path / "fixture.sav")

    result = build_codebook(sav_path)

    assert list(result.variables.columns) == VARIABLE_COLUMNS
    assert list(result.value_labels.columns) == VALUE_LABEL_COLUMNS
    assert list(result.missing_values.columns) == MISSING_VALUE_COLUMNS
    assert list(result.warnings.columns) == WARNING_COLUMNS

    age = result.variables.set_index("variable_name").loc["age"]
    assert age["variable_label"] == "Age group"
    assert bool(age["has_value_labels"]) is True
    assert age["n_missing"] == 1
    assert age["n_observed"] == 4
    assert age["n_distinct_observed"] == 4

    age_missing = result.missing_values.set_index("variable_name").loc["age"]
    assert age_missing["missing_type"] == "discrete"
    assert age_missing["value"] == "99"
    assert age_missing["label"] == "No answer"

    gender_three = result.value_labels[
        (result.value_labels["variable_name"] == "gender") & (result.value_labels["value"] == "3")
    ].iloc[0]
    assert gender_three["source"] == "observed_unlabelled"
    assert gender_three["value_label"] == ""
    assert gender_three["observed_count"] == 1

    warning_messages = result.warnings["message"].tolist()
    assert "Observed value has no value label." in warning_messages
    assert "Variable has no variable label." in warning_messages
    assert not (
        (result.value_labels["variable_name"] == "comment")
        & (result.value_labels["source"] == "observed_unlabelled")
    ).any()


def test_preview_shows_code_and_label(tmp_path):
    sav_path = write_fixture(tmp_path / "fixture.sav")

    result = build_codebook(sav_path, preview_rows=2)

    assert result.preview.loc[0, "age"] == "1 - 18-29"
    assert result.preview.loc[1, "gender"] == "2 - female"
    assert len(result.preview) == 2


def test_frequency_columns_are_empty_when_disabled(tmp_path):
    sav_path = write_fixture(tmp_path / "fixture.sav")

    result = build_codebook(sav_path, calculate_frequencies=False)

    assert result.variables["n_observed"].tolist() == ["", "", ""]
    assert result.value_labels["observed_count"].tolist()
    assert set(result.value_labels["observed_count"]) == {""}
    assert set(result.value_labels["observed_percent"]) == {""}


def test_exports_excel_and_csv_with_expected_files_and_sheets(tmp_path):
    sav_path = write_fixture(tmp_path / "fixture.sav")
    result = build_codebook(sav_path)

    export_result = export_codebook(
        result,
        ExportOptions(output_dir=tmp_path, output_name="study"),
    )

    expected_names = {
        "study_codebook.xlsx",
        "study_variables.csv",
        "study_value_labels.csv",
        "study_missing_values.csv",
        "study_warnings.csv",
    }
    assert {path.name for path in export_result.written_files} == expected_names

    workbook = openpyxl.load_workbook(tmp_path / "study_codebook.xlsx")
    assert workbook.sheetnames == ["variables", "value_labels", "missing_values", "warnings"]
    variables_sheet = workbook["variables"]
    assert variables_sheet.freeze_panes == "A2"
    assert variables_sheet.auto_filter.ref == variables_sheet.dimensions
    assert variables_sheet["A1"].font.bold is True

    variables_header = (
        (tmp_path / "study_variables.csv").read_text(encoding="utf-8").splitlines()[0]
    )
    assert variables_header == ",".join(VARIABLE_COLUMNS)


def test_cli_refuses_overwrite_without_flag(tmp_path):
    sav_path = write_fixture(tmp_path / "fixture.sav")
    argv = [
        str(sav_path),
        "--output-dir",
        str(tmp_path),
        "--output-name",
        "study",
    ]

    assert cli_main(argv) == 0
    with pytest.raises(SystemExit) as exc:
        cli_main(argv)
    assert exc.value.code == 1
    assert cli_main([*argv, "--overwrite"]) == 0


def test_gui_and_cli_share_workflow_pipeline(tmp_path):
    sav_path = write_fixture(tmp_path / "fixture.sav")

    result = load_codebook(sav_path)
    export_result = write_codebook(
        result,
        ExportOptions(output_dir=tmp_path, output_name="workflow"),
    )

    assert (tmp_path / "workflow_codebook.xlsx") in export_result.written_files


def test_rejects_missing_input_file(tmp_path):
    with pytest.raises(FileNotFoundError, match="SPSS file not found"):
        build_codebook(tmp_path / "missing.sav")


def test_rejects_export_without_a_format(tmp_path):
    sav_path = write_fixture(tmp_path / "fixture.sav")
    result = build_codebook(sav_path)

    with pytest.raises(ValueError, match="at least one export format"):
        export_codebook(
            result,
            ExportOptions(
                output_dir=tmp_path,
                output_name="study",
                export_excel=False,
                export_csv=False,
            ),
        )


def test_range_missing_values_are_marked_in_value_labels(tmp_path):
    sav_path = tmp_path / "range_missing.sav"
    df = pd.DataFrame({"score": [1, 95, 99]})
    pyreadstat.write_sav(
        df,
        str(sav_path),
        variable_value_labels={"score": {1: "Valid", 95: "Refused", 99: "Unknown"}},
        missing_ranges={"score": [{"lo": 90, "hi": 99}]},
    )

    result = build_codebook(sav_path)

    labelled = result.value_labels.set_index("value")
    assert bool(labelled.loc["1", "is_user_missing"]) is False
    assert bool(labelled.loc["95", "is_user_missing"]) is True
    assert bool(labelled.loc["99", "is_user_missing"]) is True
