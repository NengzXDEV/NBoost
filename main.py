"""
Nboost - main.py
Entry point. Loads the dark neon stylesheet, sets the app icon from
resources/nboost.png, and shows the main window.

Run from source:   python main.py
Build a .exe:       see BUILD.md / build_exe.bat
"""

from __future__ import annotations
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from nboost.core.paths import resource_path
from nboost.main_window import MainWindow


def _load_stylesheet() -> str:
    try:
        with open(resource_path("theme.qss"), "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Nboost")
    app.setOrganizationName("NengzXGODZ")
    app.setStyleSheet(_load_stylesheet())
    app.setWindowIcon(QIcon(resource_path("nboost.png")))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
