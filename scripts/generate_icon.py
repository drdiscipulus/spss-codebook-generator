"""Render the vector application icon to the Windows ICO build asset."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def main() -> None:
    _app = QGuiApplication.instance() or QGuiApplication([])

    source = Path("assets/app-icon.svg")
    ico_destination = Path("assets/app-icon.ico")
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(Qt.transparent)

    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise RuntimeError(f"Could not load {source}")
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    if not image.save(str(ico_destination), "ICO"):
        raise RuntimeError(f"Could not write {ico_destination}")


if __name__ == "__main__":
    main()
