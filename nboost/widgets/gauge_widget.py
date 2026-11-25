"""
Nboost - widgets/gauge_widget.py
Circular neon gauge for CPU / RAM / Disk. Pure QPainter, no image assets.
"""

from __future__ import annotations
from PyQt6.QtCore import Qt, QRectF, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QConicalGradient
from PyQt6.QtWidgets import QWidget


class GaugeWidget(QWidget):
    def __init__(self, title: str, accent: str = "#00f5d4", parent=None):
        super().__init__(parent)
        self._value = 0.0        # 0..100
        self._title = title
        self._subtitle = ""
        self._accent = QColor(accent)
        self.setMinimumSize(140, 140)
        self._anim = QPropertyAnimation(self, b"value")
        self._anim.setDuration(500)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def getValue(self) -> float:
        return self._value

    def setValue(self, v: float) -> None:
        self._value = max(0.0, min(100.0, v))
        self.update()

    value = pyqtProperty(float, fget=getValue, fset=setValue)

    def animate_to(self, target: float, subtitle: str = "") -> None:
        self._subtitle = subtitle
        self._anim.stop()
        self._anim.setStartValue(self._value)
        self._anim.setEndValue(max(0.0, min(100.0, target)))
        self._anim.start()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        side = min(self.width(), self.height())
        rect = QRectF((self.width() - side) / 2 + 10, (self.height() - side) / 2 + 10,
                       side - 20, side - 20)

        # track
        track_pen = QPen(QColor(255, 255, 255, 22))
        track_pen.setWidth(10)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.drawArc(rect, 90 * 16, -360 * 16)

        # glow base (soft wide arc behind the value arc)
        glow = QColor(self._accent)
        glow.setAlpha(60)
        glow_pen = QPen(glow)
        glow_pen.setWidth(18)
        glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(glow_pen)
        span = -int(360 * 16 * (self._value / 100.0))
        p.drawArc(rect, 90 * 16, span)

        # value arc with conical gradient for a neon sweep
        grad = QConicalGradient(rect.center(), 90)
        grad.setColorAt(0.0, self._accent)
        c2 = QColor(self._accent)
        c2.setAlpha(140)
        grad.setColorAt(1.0, c2)
        value_pen = QPen(QColor(self._accent))
        value_pen.setBrush(grad)
        value_pen.setWidth(10)
        value_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(value_pen)
        p.drawArc(rect, 90 * 16, span)

        # center text
        p.setPen(QColor("#f4f6fb"))
        f = QFont("Segoe UI", int(side * 0.16), QFont.Weight.Bold)
        p.setFont(f)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{self._value:.0f}%")

        f2 = QFont("Segoe UI", int(side * 0.075), QFont.Weight.Medium)
        p.setFont(f2)
        p.setPen(QColor(244, 246, 251, 170))
        sub_rect = QRectF(rect.x(), rect.y() + rect.height() * 0.68, rect.width(), rect.height() * 0.2)
        p.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, self._title)

        if self._subtitle:
            f3 = QFont("Segoe UI", int(side * 0.06))
            p.setFont(f3)
            p.setPen(QColor(244, 246, 251, 120))
            sub2 = QRectF(rect.x(), rect.y() + rect.height() * 0.80, rect.width(), rect.height() * 0.16)
            p.drawText(sub2, Qt.AlignmentFlag.AlignCenter, self._subtitle)

        p.end()
