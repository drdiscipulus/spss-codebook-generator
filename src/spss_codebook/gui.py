from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd
from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QObject,
    QRunnable,
    Qt,
    QThreadPool,
    QUrl,
    Signal,
)
from PySide6.QtGui import QDesktopServices, QDragEnterEvent, QDropEvent, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import __version__
from .core import SUPPORTED_SUFFIXES, CodebookResult
from .exporters import ExportOptions, expected_output_paths
from .theme import app_stylesheet, resource_path
from .workflow import load_codebook, write_codebook

_INVALID_INDEX = QModelIndex()


class DataFrameModel(QAbstractTableModel):
    """Read-only Qt model with sorting support for a pandas DataFrame."""

    def __init__(self) -> None:
        super().__init__()
        self._dataframe = pd.DataFrame()

    def set_dataframe(self, dataframe: pd.DataFrame) -> None:
        self.beginResetModel()
        self._dataframe = dataframe.copy()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._dataframe)

    def columnCount(self, parent: QModelIndex = _INVALID_INDEX) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._dataframe.columns)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        value = self._dataframe.iat[index.row(), index.column()]
        if role == Qt.DisplayRole:
            return "" if pd.isna(value) else str(value)
        if role == Qt.TextAlignmentRole and isinstance(value, (int, float)):
            return Qt.AlignRight | Qt.AlignVCenter
        return None

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.DisplayRole,
    ):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._dataframe.columns[section])
        return str(section + 1)

    def sort(self, column: int, order: Qt.SortOrder = Qt.AscendingOrder) -> None:
        if self._dataframe.empty or column >= len(self._dataframe.columns):
            return
        self.layoutAboutToBeChanged.emit()
        column_name = self._dataframe.columns[column]
        self._dataframe = self._dataframe.sort_values(
            column_name,
            ascending=order == Qt.AscendingOrder,
            kind="stable",
            na_position="last",
        ).reset_index(drop=True)
        self.layoutChanged.emit()


class _WorkerSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)


class _CodebookWorker(QRunnable):
    """Load an SPSS file away from the UI thread."""

    def __init__(self, path: Path, calculate_frequencies: bool) -> None:
        super().__init__()
        self.path = path
        self.calculate_frequencies = calculate_frequencies
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = load_codebook(
                self.path,
                calculate_frequencies=self.calculate_frequencies,
                preview_rows=500,
            )
        except Exception as exc:  # Convert library failures into a GUI signal.
            self.signals.failed.emit(str(exc))
            return
        self.signals.succeeded.emit(result)


class MainWindow(QMainWindow):
    """Desktop workflow for inspecting SPSS metadata and exporting a codebook."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("SPSS Codebook Rescue")
        self.setMinimumSize(940, 680)
        self.resize(1180, 780)
        self.setAcceptDrops(True)

        self._result: CodebookResult | None = None
        self._loaded_signature: tuple[Path, bool] | None = None
        self._pending_export = False
        self._last_output_dir: Path | None = None
        self._worker: _CodebookWorker | None = None

        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Choose a .sav or .zsav file")
        self.output_name = QLineEdit()
        self.output_name.setPlaceholderText("e.g. survey_wave_1")
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("Folder for the generated codebook")

        self.excel_checkbox = QCheckBox("Excel workbook")
        self.csv_checkbox = QCheckBox("CSV tables")
        self.frequencies_checkbox = QCheckBox("Calculate observed frequencies")
        self.overwrite_checkbox = QCheckBox("Overwrite existing files")
        self.excel_checkbox.setChecked(True)
        self.csv_checkbox.setChecked(True)
        self.frequencies_checkbox.setChecked(True)

        self.analyse_button = QPushButton("Analyse file")
        self.analyse_button.setObjectName("secondaryButton")
        self.analyse_button.clicked.connect(self._load_preview)
        self.export_button = QPushButton("Export codebook")
        self.export_button.setObjectName("primaryButton")
        self.export_button.clicked.connect(self._export)
        self.open_folder_button = QPushButton("Open output folder")
        self.open_folder_button.setObjectName("linkButton")
        self.open_folder_button.clicked.connect(self._open_output_folder)
        self.open_folder_button.hide()

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(120)
        self.progress.hide()
        self.status_label = QLabel("Choose an SPSS file or drop it onto this window.")
        self.status_label.setObjectName("statusLabel")

        self.summary_value_labels: dict[str, QLabel] = {}
        self.summary_cards = {
            "variables": self._summary_card("variables", "Variables", "—"),
            "labels": self._summary_card("labels", "Value labels", "—"),
            "warnings": self._summary_card("warnings", "Warnings", "—"),
        }

        self.tabs = QTabWidget()
        self.models: dict[str, DataFrameModel] = {}
        for key, title in (
            ("preview", "Data preview"),
            ("variables", "Variables"),
            ("value_labels", "Value labels"),
            ("missing_values", "Missing values"),
            ("warnings", "Warnings"),
        ):
            model = DataFrameModel()
            self.models[key] = model
            self.tabs.addTab(self._table_view(model), title)

        self.form_panel = self._build_form_panel()
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)
        layout.addLayout(self._build_header())
        layout.addWidget(self.form_panel)
        layout.addLayout(self._build_summary())
        layout.addWidget(self.tabs, 1)
        layout.addLayout(self._build_status_bar())
        self.setCentralWidget(central)

        self.input_path.textChanged.connect(self._invalidate_result)
        self.frequencies_checkbox.toggled.connect(self._invalidate_result)

    def _build_header(self) -> QVBoxLayout:
        layout = QVBoxLayout()
        layout.setSpacing(4)
        title = QLabel("SPSS Codebook Rescue")
        title.setObjectName("pageTitle")
        subtitle = QLabel("Turn embedded SPSS metadata into a transparent, reusable codebook.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        return layout

    def _build_form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        layout = QGridLayout(panel)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)
        layout.setColumnStretch(1, 1)

        input_button = QPushButton("Browse…")
        input_button.clicked.connect(self._select_input)
        output_dir_button = QPushButton("Browse…")
        output_dir_button.clicked.connect(self._select_output_dir)

        layout.addWidget(QLabel("SPSS file"), 0, 0)
        layout.addWidget(self.input_path, 0, 1)
        layout.addWidget(input_button, 0, 2)
        layout.addWidget(QLabel("Output name"), 1, 0)
        layout.addWidget(self.output_name, 1, 1, 1, 2)
        layout.addWidget(QLabel("Output folder"), 2, 0)
        layout.addWidget(self.output_dir, 2, 1)
        layout.addWidget(output_dir_button, 2, 2)

        options = QHBoxLayout()
        options.setSpacing(18)
        for checkbox in (
            self.excel_checkbox,
            self.csv_checkbox,
            self.frequencies_checkbox,
            self.overwrite_checkbox,
        ):
            options.addWidget(checkbox)
        options.addStretch()

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addStretch()
        actions.addWidget(self.analyse_button)
        actions.addWidget(self.export_button)
        layout.addLayout(options, 3, 0, 1, 3)
        layout.addLayout(actions, 4, 0, 1, 3)
        return panel

    def _build_summary(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)
        for card in self.summary_cards.values():
            layout.addWidget(card)
        return layout

    def _summary_card(self, key: str, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("summaryCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(1)
        value_label = QLabel(value)
        value_label.setObjectName("summaryValue")
        caption = QLabel(label)
        caption.setObjectName("summaryCaption")
        layout.addWidget(value_label)
        layout.addWidget(caption)
        self.summary_value_labels[key] = value_label
        return card

    def _build_status_bar(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addWidget(self.status_label, 1)
        layout.addWidget(self.progress)
        layout.addWidget(self.open_folder_button)
        version = QLabel(f"v{__version__}")
        version.setObjectName("versionLabel")
        layout.addWidget(version)
        return layout

    @staticmethod
    def _table_view(model: DataFrameModel) -> QTableView:
        view = QTableView()
        view.setModel(model)
        view.setSortingEnabled(True)
        view.setAlternatingRowColors(True)
        view.setEditTriggers(QTableView.NoEditTriggers)
        view.setSelectionBehavior(QTableView.SelectRows)
        view.setShowGrid(False)
        view.verticalHeader().setDefaultSectionSize(30)
        view.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        view.horizontalHeader().setMinimumSectionSize(90)
        view.horizontalHeader().setStretchLastSection(True)
        return view

    def _select_input(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Choose an SPSS file",
            self.input_path.text(),
            "SPSS data files (*.sav *.zsav)",
        )
        if path:
            self._set_input_path(Path(path))

    def _set_input_path(self, path: Path) -> None:
        self.input_path.setText(str(path))
        if not self.output_name.text().strip():
            self.output_name.setText(path.stem)
        if not self.output_dir.text().strip():
            self.output_dir.setText(str(path.parent))

    def _select_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Choose an output folder",
            self.output_dir.text(),
        )
        if path:
            self.output_dir.setText(path)

    def _invalidate_result(self) -> None:
        if self._loaded_signature != self._current_signature(silent=True):
            self._result = None
            self.open_folder_button.hide()

    def _load_preview(self) -> None:
        self._pending_export = False
        self._start_load()

    def _start_load(self) -> None:
        try:
            path = self._input_file()
        except (ValueError, FileNotFoundError) as exc:
            QMessageBox.warning(self, "Choose an SPSS file", str(exc))
            return

        self._set_busy(True, f"Reading {path.name}…")
        worker = _CodebookWorker(path, self.frequencies_checkbox.isChecked())
        worker.signals.succeeded.connect(self._load_succeeded)
        worker.signals.failed.connect(self._load_failed)
        self._worker = worker
        QThreadPool.globalInstance().start(worker)

    def _load_succeeded(self, result: CodebookResult) -> None:
        self._result = result
        self._loaded_signature = self._current_signature()
        self._populate_tables(result)
        self._set_busy(False, "Analysis complete. Review the tables or export the codebook.")
        self._worker = None
        if self._pending_export:
            self._pending_export = False
            self._write_export()

    def _load_failed(self, message: str) -> None:
        self._result = None
        self._pending_export = False
        self._worker = None
        self._set_busy(False, "The file could not be analysed.")
        QMessageBox.critical(self, "Could not analyse file", message)

    def _export(self) -> None:
        if not self.excel_checkbox.isChecked() and not self.csv_checkbox.isChecked():
            QMessageBox.warning(
                self,
                "Choose an export format",
                "Select Excel, CSV, or both.",
            )
            return
        try:
            self._output_folder()
            self._output_stem()
        except ValueError as exc:
            QMessageBox.warning(self, "Check export settings", str(exc))
            return

        if self._result is None or self._loaded_signature != self._current_signature():
            self._pending_export = True
            self._start_load()
            return
        self._write_export()

    def _write_export(self) -> None:
        if self._result is None:
            return

        options = ExportOptions(
            output_dir=self._output_folder(),
            output_name=self._output_stem(),
            export_excel=self.excel_checkbox.isChecked(),
            export_csv=self.csv_checkbox.isChecked(),
            overwrite=self.overwrite_checkbox.isChecked(),
        )
        output_paths = expected_output_paths(
            options.output_dir,
            options.output_name,
            options.export_excel,
            options.export_csv,
        )
        existing = [path for path in output_paths if path.exists()]
        if existing and not options.overwrite:
            names = "\n".join(f"• {path.name}" for path in existing)
            answer = QMessageBox.question(
                self,
                "Replace existing files?",
                f"These files already exist:\n\n{names}\n\nReplace them?",
            )
            if answer != QMessageBox.Yes:
                self.status_label.setText("Export cancelled; no files were changed.")
                return
            options = replace(options, overwrite=True)

        try:
            export_result = write_codebook(self._result, options)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return

        self._last_output_dir = options.output_dir
        self.open_folder_button.show()
        count = len(export_result.written_files)
        self.status_label.setText(
            f"Export complete — {count} file{'s' if count != 1 else ''} written to "
            f"{options.output_dir}."
        )

    def _populate_tables(self, result: CodebookResult) -> None:
        tables = {
            "preview": result.preview,
            "variables": result.variables,
            "value_labels": result.value_labels,
            "missing_values": result.missing_values,
            "warnings": result.warnings,
        }
        for index, (key, table) in enumerate(tables.items()):
            self.models[key].set_dataframe(table)
            base_title = self.tabs.tabText(index).split(" (", maxsplit=1)[0]
            self.tabs.setTabText(index, f"{base_title} ({len(table):,})")

        self._set_summary_value("variables", len(result.variables))
        self._set_summary_value("labels", len(result.value_labels))
        self._set_summary_value("warnings", len(result.warnings))

    def _set_summary_value(self, key: str, value: int) -> None:
        self.summary_value_labels[key].setText(f"{value:,}")

    def _set_busy(self, busy: bool, message: str) -> None:
        self.form_panel.setEnabled(not busy)
        self.progress.setVisible(busy)
        self.status_label.setText(message)

    def _open_output_folder(self) -> None:
        if self._last_output_dir:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output_dir)))

    def _input_file(self) -> Path:
        value = self.input_path.text().strip()
        if not value:
            raise ValueError("Choose a .sav or .zsav file first.")
        path = Path(value)
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError("The selected file must use the .sav or .zsav extension.")
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path

    def _output_folder(self) -> Path:
        value = self.output_dir.text().strip()
        if not value:
            raise ValueError("Choose an output folder.")
        return Path(value)

    def _output_stem(self) -> str:
        value = self.output_name.text().strip()
        if not value:
            raise ValueError("Enter an output name.")
        return value

    def _current_signature(self, *, silent: bool = False) -> tuple[Path, bool] | None:
        try:
            raw_path = self.input_path.text().strip()
            if not raw_path:
                return None
            path = Path(raw_path)
            if not silent and not path.is_file():
                return None
            return (path.resolve(), self.frequencies_checkbox.isChecked())
        except OSError:
            return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        urls = event.mimeData().urls()
        if any(Path(url.toLocalFile()).suffix.lower() in SUPPORTED_SUFFIXES for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.suffix.lower() in SUPPORTED_SUFFIXES:
                self._set_input_path(path)
                event.acceptProposedAction()
                return


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SPSS Codebook Rescue")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("SPSS Codebook Rescue")
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(resource_path("assets/app-icon.svg"))))
    app.setStyleSheet(app_stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
