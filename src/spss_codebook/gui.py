from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .core import CodebookResult
from .exporters import ExportOptions, expected_output_paths
from .workflow import load_codebook, write_codebook


class DataFrameModel(QAbstractTableModel):
    """Small Qt table model for displaying pandas DataFrames in preview tabs."""

    def __init__(self):
        super().__init__()
        self._dataframe = None

    def set_dataframe(self, dataframe):
        self.beginResetModel()
        self._dataframe = dataframe
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        if parent.isValid() or self._dataframe is None:
            return 0
        return len(self._dataframe)

    def columnCount(self, parent=QModelIndex()) -> int:
        if parent.isValid() or self._dataframe is None:
            return 0
        return len(self._dataframe.columns)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid() or self._dataframe is None or role != Qt.DisplayRole:
            return None
        value = self._dataframe.iat[index.row(), index.column()]
        return "" if value is None else str(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if self._dataframe is None or role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._dataframe.columns[section])
        return str(section + 1)


class MainWindow(QMainWindow):
    """Main desktop window for loading, previewing, and exporting codebooks."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("SPSS Codebook Generator")
        self.resize(1100, 720)
        self._result: CodebookResult | None = None

        self.input_path = QLineEdit()
        self.output_name = QLineEdit()
        self.output_dir = QLineEdit()
        self.excel_checkbox = QCheckBox("Export Excel")
        self.csv_checkbox = QCheckBox("Export CSV")
        self.frequencies_checkbox = QCheckBox("Calculate frequencies")
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        self.status_label = QLabel("Select an SPSS file to begin.")

        self.excel_checkbox.setChecked(True)
        self.csv_checkbox.setChecked(True)
        self.frequencies_checkbox.setChecked(True)

        self.tabs = QTabWidget()
        self.models = {
            "Data Preview": DataFrameModel(),
            "Variables": DataFrameModel(),
            "Value Labels": DataFrameModel(),
            "Missing Values": DataFrameModel(),
            "Warnings": DataFrameModel(),
        }
        for title, model in self.models.items():
            view = QTableView()
            view.setModel(model)
            view.setSortingEnabled(True)
            view.setAlternatingRowColors(True)
            self.tabs.addTab(view, title)

        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.addWidget(self._build_form())
        root_layout.addWidget(self.tabs)
        root_layout.addWidget(self.status_label)
        self.setCentralWidget(root)

    def _build_form(self) -> QWidget:
        group = QGroupBox("Export settings")
        layout = QGridLayout(group)

        input_button = QPushButton("Browse")
        input_button.clicked.connect(self._select_input)
        output_dir_button = QPushButton("Browse")
        output_dir_button.clicked.connect(self._select_output_dir)
        load_button = QPushButton("Load Preview")
        load_button.clicked.connect(self._load_preview)
        export_button = QPushButton("Export Codebook")
        export_button.clicked.connect(self._export)

        layout.addWidget(QLabel("Input SPSS file"), 0, 0)
        layout.addWidget(self.input_path, 0, 1)
        layout.addWidget(input_button, 0, 2)
        layout.addWidget(QLabel("Output name"), 1, 0)
        layout.addWidget(self.output_name, 1, 1, 1, 2)
        layout.addWidget(QLabel("Output location"), 2, 0)
        layout.addWidget(self.output_dir, 2, 1)
        layout.addWidget(output_dir_button, 2, 2)

        options = QHBoxLayout()
        options.addWidget(self.excel_checkbox)
        options.addWidget(self.csv_checkbox)
        options.addWidget(self.frequencies_checkbox)
        options.addWidget(self.overwrite_checkbox)
        options.addStretch()
        options.addWidget(load_button)
        options.addWidget(export_button)
        layout.addLayout(options, 3, 0, 1, 3)
        return group

    def _select_input(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select SPSS file",
            "",
            "SPSS files (*.sav *.zsav)",
        )
        if not path:
            return
        self.input_path.setText(path)
        input_path = Path(path)
        if not self.output_name.text().strip():
            self.output_name.setText(input_path.stem)
        if not self.output_dir.text().strip():
            self.output_dir.setText(str(input_path.parent))

    def _select_output_dir(self):
        path = QFileDialog.getExistingDirectory(self, "Select output location")
        if path:
            self.output_dir.setText(path)

    def _load_preview(self):
        try:
            self._result = load_codebook(
                self._input_path(),
                calculate_frequencies=self.frequencies_checkbox.isChecked(),
                preview_rows=500,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Could not load file", str(exc))
            return
        self._populate_tables(self._result)
        self.status_label.setText("Preview loaded.")

    def _export(self):
        if self._result is None:
            self._load_preview()
            if self._result is None:
                return

        export_excel = self.excel_checkbox.isChecked()
        export_csv = self.csv_checkbox.isChecked()
        if not export_excel and not export_csv:
            QMessageBox.warning(self, "No export selected", "Select at least one export format.")
            return

        options = ExportOptions(
            output_dir=self._output_dir(),
            output_name=self._output_name(),
            export_excel=export_excel,
            export_csv=export_csv,
            overwrite=self.overwrite_checkbox.isChecked(),
        )

        if not options.overwrite:
            output_paths = expected_output_paths(
                options.output_dir,
                options.output_name,
                export_excel,
                export_csv,
            )
            existing = [path for path in output_paths if path.exists()]
            if existing:
                names = "\n".join(path.name for path in existing)
                answer = QMessageBox.question(
                    self,
                    "Overwrite files?",
                    f"The following files already exist:\n\n{names}\n\nOverwrite them?",
                )
                if answer != QMessageBox.Yes:
                    return
                options = ExportOptions(
                    output_dir=options.output_dir,
                    output_name=options.output_name,
                    export_excel=options.export_excel,
                    export_csv=options.export_csv,
                    overwrite=True,
                )

        try:
            export_result = write_codebook(self._result, options)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        files = ", ".join(path.name for path in export_result.written_files)
        self.status_label.setText(f"Export complete: {files}")

    def _populate_tables(self, result: CodebookResult):
        self.models["Data Preview"].set_dataframe(result.preview)
        self.models["Variables"].set_dataframe(result.variables)
        self.models["Value Labels"].set_dataframe(result.value_labels)
        self.models["Missing Values"].set_dataframe(result.missing_values)
        self.models["Warnings"].set_dataframe(result.warnings)

    def _input_path(self) -> Path:
        value = self.input_path.text().strip()
        if not value:
            raise ValueError("Select an input SPSS file.")
        return Path(value)

    def _output_dir(self) -> Path:
        value = self.output_dir.text().strip()
        if not value:
            raise ValueError("Select an output location.")
        return Path(value)

    def _output_name(self) -> str:
        value = self.output_name.text().strip()
        if not value:
            raise ValueError("Enter an output name.")
        return value


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
