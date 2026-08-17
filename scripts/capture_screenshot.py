"""Create the README screenshot with representative, synthetic data."""

from pathlib import Path

import pandas as pd
from PySide6.QtWidgets import QApplication

from spss_codebook.core import CodebookResult
from spss_codebook.gui import MainWindow
from spss_codebook.theme import app_stylesheet


def main() -> None:
    app = QApplication([])
    app.setStyle("Fusion")
    app.setStyleSheet(app_stylesheet())

    window = MainWindow()
    window.input_path.setText("C:/Research/entrepreneurship_survey.sav")
    window.output_name.setText("entrepreneurship_survey")
    window.output_dir.setText("C:/Research/codebooks")
    window._populate_tables(  # noqa: SLF001 - dedicated visual documentation helper
        CodebookResult(
            preview=pd.DataFrame(
                {
                    "venture_id": [101, 102, 103],
                    "venture_stage": ["1 - Idea", "2 - Early revenue", "3 - Growth"],
                    "employees": [2, 8, 24],
                }
            ),
            variables=pd.DataFrame(
                {
                    "variable_name": ["venture_id", "venture_stage", "employees"],
                    "variable_label": ["Venture ID", "Venture stage", "Number of employees"],
                    "storage_type": ["double", "double", "double"],
                }
            ),
            value_labels=pd.DataFrame(
                {
                    "variable_name": ["venture_stage", "venture_stage", "venture_stage"],
                    "value": ["1", "2", "3"],
                    "value_label": ["Idea", "Early revenue", "Growth"],
                }
            ),
            missing_values=pd.DataFrame(
                columns=["variable_name", "missing_type", "value", "lower", "upper"]
            ),
            warnings=pd.DataFrame(
                {
                    "severity": ["info"],
                    "variable_name": ["employees"],
                    "value": [""],
                    "message": ["Variable has observed values but no value labels."],
                }
            ),
        )
    )
    window.status_label.setText(
        "Analysis complete. Review the tables or export the codebook."
    )
    window.tabs.setCurrentIndex(2)
    value_labels_table = window.tabs.widget(2)
    value_labels_table.setColumnWidth(0, 220)
    value_labels_table.setColumnWidth(1, 130)
    window.resize(1180, 780)
    window.show()
    app.processEvents()

    output = Path("docs/assets/application.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output)):
        raise RuntimeError(f"Could not save screenshot to {output}")


if __name__ == "__main__":
    main()
