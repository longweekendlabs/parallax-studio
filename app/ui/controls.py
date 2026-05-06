from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QSizePolicy, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QBrush, QPen, QFont

from app.ui.theme import (
    C_PANEL_BG, C_RAISED_PANEL, C_ACCENT, C_BORDER, C_BORDER_SOFT,
    C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
)


class ToggleSwitch(QWidget):
    """iOS-style toggle switch."""
    def __init__(self, on: bool = True, parent=None):
        super().__init__(parent)
        self._on = on
        self.setFixedSize(40, 22)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self._on = not self._on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QColor(C_ACCENT) if self._on else QColor(C_BORDER)
        p.setBrush(QBrush(track))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 3, 40, 16), 8, 8)
        knob_x = 22.0 if self._on else 2.0
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawEllipse(QRectF(knob_x, 1, 18, 18))


def _slider_row(label: str, value: int = 50, display: str = "") -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    col = QVBoxLayout(w)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(4)

    row = QHBoxLayout()
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
    val = QLabel(display or str(value))
    val.setStyleSheet(
        f"color: {C_TEXT_MAIN}; font-size: 11px; "
        f"font-family: 'JetBrains Mono', 'SF Mono', monospace;"
    )
    row.addWidget(lbl)
    row.addStretch()
    row.addWidget(val)
    col.addLayout(row)

    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(value)
    slider.setFixedHeight(18)
    col.addWidget(slider)
    return w


def _section_sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"background: {C_BORDER_SOFT}; max-height: 1px; border: none;")
    return f


def _section_header(icon: str, title: str) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)

    ico = QLabel(icon)
    ico.setStyleSheet(f"color: {C_ACCENT}; font-size: 13px;")
    lbl = QLabel(title)
    lbl.setStyleSheet(
        f"color: {C_TEXT_MAIN}; font-size: 11px; font-weight: 600; letter-spacing: 0.8px;"
    )
    arrow = QLabel("∧")
    arrow.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 10px;")

    row.addWidget(ico)
    row.addWidget(lbl)
    row.addStretch()
    row.addWidget(arrow)
    return w


class ControlsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {C_PANEL_BG};")
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        col = QVBoxLayout(content)
        col.setContentsMargins(12, 12, 12, 12)
        col.setSpacing(14)

        # ── DEPTH BRUSH ──
        col.addWidget(_section_header("≋", "DEPTH BRUSH"))
        col.addWidget(_section_sep())
        col.addWidget(_slider_row("Brush Size", 85, "128"))
        col.addWidget(_slider_row("Depth Value", 45, "0.45"))
        col.addWidget(_slider_row("Hardness", 65, "65%"))
        col.addWidget(_slider_row("Opacity", 100, "100%"))

        col.addSpacing(4)

        # ── MOTION ──
        col.addWidget(_section_header("≈", "MOTION"))
        col.addWidget(_section_sep())

        style_lbl = QLabel("Motion Style")
        style_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        col.addWidget(style_lbl)

        style_box = QComboBox()
        style_box.addItems([
            "Parallax Orbit",
            "Gentle Float",
            "Horizontal Drift",
            "Vertical Drift",
            "Zoom Breathe",
        ])
        col.addWidget(style_box)

        loop_lbl = QLabel("Loop Type")
        loop_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        col.addWidget(loop_lbl)

        loop_box = QComboBox()
        loop_box.addItems(["Seamless Loop", "Bounce"])
        col.addWidget(loop_box)

        col.addWidget(_slider_row("Layer Intensity", 65, "0.65"))
        col.addWidget(_slider_row("Speed", 60, "1.00x"))

        col.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll)
