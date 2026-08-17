"""Visual theme and packaged-resource lookup for the desktop application.

Keeping the stylesheet separate keeps GUI behavior easy to review and avoids a
third-party theme dependency in the portable build.
"""

import sys
from pathlib import Path


def resource_path(relative_path: str) -> Path:
    """Resolve an asset in both source checkouts and PyInstaller bundles."""

    bundle_root = getattr(sys, "_MEIPASS", None)
    root = Path(bundle_root) if bundle_root else Path(__file__).resolve().parents[2]
    return root / relative_path


def app_stylesheet() -> str:
    """Return the stylesheet with absolute paths for checkbox assets."""

    unchecked = resource_path("assets/checkbox-unchecked.svg").as_posix()
    checked = resource_path("assets/checkbox-checked.svg").as_posix()
    return _APP_STYLESHEET.replace("__UNCHECKED__", unchecked).replace("__CHECKED__", checked)


_APP_STYLESHEET = """
QWidget {
    color: #17202a;
    background: #f4f7fa;
    font-family: "Segoe UI";
    font-size: 10pt;
}
QLabel#pageTitle {
    color: #102a43;
    font-size: 22pt;
    font-weight: 700;
}
QLabel { background: transparent; }
QLabel#pageSubtitle, QLabel#summaryCaption, QLabel#versionLabel {
    color: #627d98;
}
QFrame#panel, QFrame#summaryCard {
    background: #ffffff;
    border: 1px solid #d9e2ec;
    border-radius: 9px;
}
QFrame#summaryCard { min-width: 130px; }
QLabel#summaryValue {
    background: transparent;
    color: #102a43;
    font-size: 17pt;
    font-weight: 650;
}
QLabel#summaryCaption, QLabel#statusLabel, QLabel#versionLabel {
    background: transparent;
}
QLineEdit {
    min-height: 35px;
    padding: 0 10px;
    background: #ffffff;
    border: 1px solid #bcccdc;
    border-radius: 6px;
    selection-background-color: #2f6fed;
}
QLineEdit:focus { border: 2px solid #2f6fed; }
QPushButton {
    min-height: 35px;
    padding: 0 15px;
    background: #ffffff;
    border: 1px solid #bcccdc;
    border-radius: 6px;
    font-weight: 600;
}
QPushButton:hover { background: #eef4fb; }
QPushButton:pressed { background: #d9e8f7; }
QPushButton:disabled { color: #9fb3c8; background: #f0f4f8; }
QPushButton#primaryButton {
    color: #ffffff;
    background: #2457c5;
    border-color: #2457c5;
}
QPushButton#primaryButton:hover { background: #1d4aa9; }
QPushButton#secondaryButton { color: #2457c5; border-color: #7b9ed9; }
QPushButton#linkButton {
    color: #2457c5;
    background: transparent;
    border: none;
    padding: 0 8px;
}
QCheckBox { spacing: 7px; background: transparent; }
QCheckBox::indicator {
    width: 18px;
    height: 18px;
}
QCheckBox::indicator:unchecked { image: url("__UNCHECKED__"); }
QCheckBox::indicator:checked { image: url("__CHECKED__"); }
QTabWidget::pane {
    background: #ffffff;
    border: 1px solid #d9e2ec;
    border-radius: 7px;
    top: -1px;
}
QTabBar::tab {
    color: #486581;
    background: transparent;
    border: none;
    padding: 9px 14px;
}
QTabBar::tab:selected {
    color: #2457c5;
    font-weight: 700;
    border-bottom: 2px solid #2457c5;
}
QTableView {
    background: #ffffff;
    alternate-background-color: #f7f9fc;
    border: none;
    selection-background-color: #dce8fb;
    selection-color: #102a43;
}
QHeaderView::section {
    color: #334e68;
    background: #edf2f7;
    border: none;
    border-right: 1px solid #d9e2ec;
    border-bottom: 1px solid #d9e2ec;
    padding: 8px;
    font-weight: 650;
}
QProgressBar {
    max-height: 6px;
    border: none;
    border-radius: 3px;
    background: #d9e2ec;
}
QProgressBar::chunk { background: #2f6fed; border-radius: 3px; }
QMessageBox { background: #f4f7fa; }
"""
