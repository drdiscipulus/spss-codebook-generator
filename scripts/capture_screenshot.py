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
    window.input_path.setText("C:/Research/example_survey.sav")
    window.output_name.setText("example_survey")
    window.output_dir.setText("C:/Research/codebook")
    window._populate_tables(  # noqa: SLF001 - dedicated visual documentation helper
        CodebookResult(
            preview=pd.DataFrame(
                {
                    "founder_id": [101, 102, 103],
                    "gender": ["1 - Woman", "2 - Man", "1 - Woman"],
                    "employees": [4, 12, 7],
                }
            ),
            variables=pd.DataFrame(
                {
                    "variable_name": ["founder_id", "gender", "employees"],
                    "variable_label": ["Founder ID", "Gender", "Number of employees"],
                    "storage_type": ["double", "double", "double"],
                }
            ),
            value_labels=pd.DataFrame(
                {
                    "variable_name": ["gender", "gender"],
                    "value": ["1", "2"],
                    "value_label": ["Woman", "Man"],
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
    window.resize(1180, 780)
    window.show()
    app.processEvents()

    output = Path("docs/assets/application.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    if not window.grab().save(str(output)):
        raise RuntimeError(f"Could not save screenshot to {output}")


if __name__ == "__main__":
    main()
