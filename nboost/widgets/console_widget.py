"""
Nboost - widgets/console_widget.py
Real-time cleaning log console: monospace, color-tagged by line prefix.
"""

from __future__ import annotations
import datetime
from PyQt6.QtWidgets import QPlainTextEdit
from PyQt6.QtGui import QTextCursor, QFont
from PyQt6.QtCore import pyqtSlot


_COLORS = {
    "[error]": "#ff5d73",
    "[clean]": "#00f5d4",
    "[scan]": "#8ab4ff",
    "[Junk]": "#ffd166",
    "[Logs]": "#ffd166",
    "[Apps]": "#ffd166",
    "[RAM]": "#ffd166",
    "[Registry]": "#ffd166",
    "[Duplicates]": "#ffd166",
    "[Startup]": "#ffd166",
}


class ConsoleWidget(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setObjectName("consoleWidget")
        f = QFont("Cascadia Mono", 9)
        f.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(f)
        self.setMaximumBlockCount(5000)

    @pyqtSlot(str)
    def append_line(self, text: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        color = "#c9d1e3"
        for prefix, c in _COLORS.items():
            if text.strip().startswith(prefix):
                color = c
                break
        safe = (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        html = f'<span style="color:#5b6478;">[{ts}]</span> <span style="color:{color};">{safe}</span>'
        self.appendHtml(html)
        self.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self) -> None:
        self.clear()
