from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import pyreadstat


SUPPORTED_SUFFIXES = {".sav", ".zsav"}

VARIABLE_COLUMNS = [
    "variable_name",
    "variable_label",
    "storage_type",
    "spss_format",
    "measure",
    "has_value_labels",
    "n_observed",
    "n_missing",
    "n_distinct_observed",
]

VALUE_LABEL_COLUMNS = [
    "variable_name",
    "variable_label",
    "value",
    "value_label",
    "is_user_missing",
    "observed_count",
    "observed_percent",
    "source",
]

MISSING_VALUE_COLUMNS = [
    "variable_name",
    "missing_type",
    "value",
    "lower",
    "upper",
    "label",
]

WARNING_COLUMNS = [
    "severity",
    "variable_name",
    "value",
    "message",
]


@dataclass(frozen=True)
class CodebookResult:
    """In-memory representation of all tables produced from one SPSS file."""

    variables: pd.DataFrame
    value_labels: pd.DataFrame
    missing_values: pd.DataFrame
    warnings: pd.DataFrame
    preview: pd.DataFrame


def build_codebook(
    input_path: str | Path,
    *,
    calculate_frequencies: bool = True,
    preview_rows: int = 500,
) -> CodebookResult:
    """Read an SPSS file and build normalized codebook tables.

    SPSS stores the pieces analysts usually need in separate metadata fields:
    variable labels, value-label maps, and user-missing definitions. This
    function keeps the raw data values intact, then joins those metadata pieces
    into long-form tables that are easy to inspect in Excel or import into R.
    """

    path = Path(input_path)
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValueError(f"Unsupported input format '{path.suffix}'. Supported formats: {supported}.")
    if preview_rows < 0:
        raise ValueError("preview_rows must be zero or greater.")

    df, meta = pyreadstat.read_sav(
        str(path),
        apply_value_formats=False,
        user_missing=True,
    )

    variable_labels = _column_labels(meta)
    value_label_maps = getattr(meta, "variable_value_labels", {}) or {}
    missing_ranges = getattr(meta, "missing_ranges", {}) or {}
    missing_user_values = getattr(meta, "missing_user_values", {}) or {}
    original_types = getattr(meta, "original_variable_types", {}) or {}
    readstat_types = getattr(meta, "readstat_variable_types", {}) or {}
    variable_measure = getattr(meta, "variable_measure", {}) or {}

    variables_rows: list[dict[str, Any]] = []
    value_label_rows: list[dict[str, Any]] = []
    missing_rows: list[dict[str, Any]] = []
    warning_rows: list[dict[str, Any]] = []
    preview = _format_preview(df.head(preview_rows), value_label_maps)

    for variable_name in list(df.columns):
        series = df[variable_name]
        variable_label = variable_labels.get(variable_name, "")
        label_map = value_label_maps.get(variable_name, {}) or {}
        normalized_labels = {_normal_key(value): (value, label) for value, label in label_map.items()}
        missing_specs = _missing_specs(variable_name, missing_ranges, missing_user_values)
        missing_keys = _missing_keys(missing_specs)

        non_system_missing = series.dropna()
        observed_counts = non_system_missing.value_counts(dropna=True)
        observed_keys = {_normal_key(value) for value in observed_counts.index}
        user_missing_mask = non_system_missing.map(lambda value: _is_user_missing(value, missing_specs))
        n_user_missing = int(user_missing_mask.sum()) if len(non_system_missing) else 0
        n_system_missing = int(series.isna().sum())
        n_missing = n_system_missing + n_user_missing
        analysis_values = non_system_missing[~user_missing_mask]
        n_observed = int(len(analysis_values))

        variables_rows.append(
            {
                "variable_name": variable_name,
                "variable_label": variable_label,
                "storage_type": readstat_types.get(variable_name, ""),
                "spss_format": original_types.get(variable_name, ""),
                "measure": variable_measure.get(variable_name, ""),
                "has_value_labels": bool(label_map),
                "n_observed": n_observed if calculate_frequencies else "",
                "n_missing": n_missing if calculate_frequencies else "",
                "n_distinct_observed": int(analysis_values.nunique(dropna=True))
                if calculate_frequencies
                else "",
            }
        )

        if not variable_label:
            warning_rows.append(
                {
                    "severity": "warning",
                    "variable_name": variable_name,
                    "value": "",
                    "message": "Variable has no variable label.",
                }
            )

        if not label_map and observed_keys:
            warning_rows.append(
                {
                    "severity": "info",
                    "variable_name": variable_name,
                    "value": "",
                    "message": "Variable has observed values but no value labels.",
                }
            )

        for missing_spec in missing_specs:
            missing_rows.append(
                {
                    "variable_name": variable_name,
                    "missing_type": missing_spec["missing_type"],
                    "value": _display_value(missing_spec.get("value", "")),
                    "lower": _display_value(missing_spec.get("lower", "")),
                    "upper": _display_value(missing_spec.get("upper", "")),
                    "label": _label_for_missing(missing_spec, normalized_labels),
                }
            )

        denominator = int(len(non_system_missing))
        for label_value, value_label in label_map.items():
            count = _observed_count_for_key(observed_counts, _normal_key(label_value))
            value_label_rows.append(
                {
                    "variable_name": variable_name,
                    "variable_label": variable_label,
                    "value": _display_value(label_value),
                    "value_label": value_label,
                    "is_user_missing": _normal_key(label_value) in missing_keys,
                    "observed_count": count if calculate_frequencies else "",
                    "observed_percent": _percent(count, denominator) if calculate_frequencies else "",
                    "source": "spss_value_label",
                }
            )

        if label_map:
            for observed_value in observed_counts.index:
                observed_key = _normal_key(observed_value)
                if observed_key in normalized_labels:
                    continue
                count = int(observed_counts.loc[observed_value])
                warning_rows.append(
                    {
                        "severity": "warning",
                        "variable_name": variable_name,
                        "value": _display_value(observed_value),
                        "message": "Observed value has no value label.",
                    }
                )
                value_label_rows.append(
                    {
                        "variable_name": variable_name,
                        "variable_label": variable_label,
                        "value": _display_value(observed_value),
                        "value_label": "",
                        "is_user_missing": observed_key in missing_keys,
                        "observed_count": count if calculate_frequencies else "",
                        "observed_percent": _percent(count, denominator) if calculate_frequencies else "",
                        "source": "observed_unlabelled",
                    }
                )

    return CodebookResult(
        variables=pd.DataFrame(variables_rows, columns=VARIABLE_COLUMNS),
        value_labels=pd.DataFrame(value_label_rows, columns=VALUE_LABEL_COLUMNS),
        missing_values=pd.DataFrame(missing_rows, columns=MISSING_VALUE_COLUMNS),
        warnings=pd.DataFrame(warning_rows, columns=WARNING_COLUMNS),
        preview=preview,
    )


def _column_labels(meta: Any) -> dict[str, str]:
    labels = getattr(meta, "column_names_to_labels", None)
    if labels:
        return {name: label or "" for name, label in labels.items()}

    names = getattr(meta, "column_names", []) or []
    raw_labels = getattr(meta, "column_labels", []) or []
    return {name: (raw_labels[index] if index < len(raw_labels) and raw_labels[index] else "") for index, name in enumerate(names)}


def _missing_specs(
    variable_name: str,
    missing_ranges: dict[str, list[Any]],
    missing_user_values: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    """Normalize pyreadstat's discrete and range-style user-missing metadata."""

    specs: list[dict[str, Any]] = []
    for item in missing_ranges.get(variable_name, []) or []:
        if isinstance(item, dict):
            lower = item.get("lo")
            upper = item.get("hi")
        else:
            lower = item
            upper = item

        if _normal_key(lower) == _normal_key(upper):
            specs.append({"missing_type": "discrete", "value": lower, "lower": "", "upper": ""})
        else:
            specs.append({"missing_type": "range", "value": "", "lower": lower, "upper": upper})

    for item in missing_user_values.get(variable_name, []) or []:
        specs.append({"missing_type": "discrete", "value": item, "lower": "", "upper": ""})
    return specs


def _missing_keys(missing_specs: list[dict[str, Any]]) -> set[tuple[str, Any]]:
    keys: set[tuple[str, Any]] = set()
    for spec in missing_specs:
        if spec["missing_type"] == "discrete":
            keys.add(_normal_key(spec.get("value")))
    return keys


def _is_user_missing(value: Any, missing_specs: list[dict[str, Any]]) -> bool:
    value_key = _normal_key(value)
    for spec in missing_specs:
        if spec["missing_type"] == "discrete" and value_key == _normal_key(spec.get("value")):
            return True
        if spec["missing_type"] == "range":
            lower = spec.get("lower")
            upper = spec.get("upper")
            try:
                if lower <= value <= upper:
                    return True
            except TypeError:
                continue
    return False


def _label_for_missing(spec: dict[str, Any], normalized_labels: dict[tuple[str, Any], tuple[Any, str]]) -> str:
    if spec["missing_type"] != "discrete":
        return ""
    label = normalized_labels.get(_normal_key(spec.get("value")))
    return label[1] if label else ""


def _observed_count_for_key(observed_counts: pd.Series, key: tuple[str, Any]) -> int:
    for observed_value, count in observed_counts.items():
        if _normal_key(observed_value) == key:
            return int(count)
    return 0


def _format_preview(preview: pd.DataFrame, value_label_maps: dict[str, dict[Any, str]]) -> pd.DataFrame:
    formatted = preview.copy()
    for column in formatted.columns:
        label_map = value_label_maps.get(column, {}) or {}
        if not label_map:
            continue
        normalized_labels = {_normal_key(value): label for value, label in label_map.items()}
        formatted[column] = formatted[column].map(
            lambda value: _preview_value(value, normalized_labels),
            na_action=None,
        )
    return formatted


def _preview_value(value: Any, normalized_labels: dict[tuple[str, Any], str]) -> str:
    if pd.isna(value):
        return ""
    label = normalized_labels.get(_normal_key(value))
    if label is None:
        return _display_value(value)
    return f"{_display_value(value)} - {label}"


def _normal_key(value: Any) -> tuple[str, Any]:
    """Return a stable comparison key for SPSS codes across Python/numpy types."""

    if pd.isna(value):
        return ("missing", "")
    if hasattr(value, "item"):
        try:
            value = value.item()
        except ValueError:
            pass
    if isinstance(value, float) and value.is_integer():
        return ("number", int(value))
    if isinstance(value, (int, float)):
        return ("number", value)
    return ("string", str(value))


def _display_value(value: Any) -> str:
    if value == "":
        return ""
    if pd.isna(value):
        return ""
    if hasattr(value, "item"):
        try:
            value = value.item()
        except ValueError:
            pass
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _percent(count: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((count / denominator) * 100, 4)
