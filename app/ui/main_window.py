from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QStatusBar, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPainter, QBrush, QLinearGradient, QPixmap, QPen

from app.ui.theme import (
    C_WINDOW_BG, C_PANEL_BG, C_RAISED_PANEL, C_ACCENT,
    C_BORDER, C_BORDER_SOFT, C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
)
from app.ui.layer_panel import LayerPanel
from app.ui.canvas import CanvasPanel
from app.ui.controls import ControlsPanel
from app.ui.timeline import TimelineStrip


def _vline() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.VLine)
    f.setStyleSheet(f"background: {C_BORDER_SOFT}; max-width: 1px; border: none;")
    return f


class LogoWidget(QWidget):
    """Small "P" logo mark."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        grad = QLinearGradient(0, 0, 28, 28)
        grad.setColorAt(0, QColor(C_ACCENT))
        grad.setColorAt(1, QColor("#1A8A80"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, 28, 28, 6, 6)
        f = QFont("Inter, SF Pro Display, system-ui")
        f.setPointSize(14)
        f.setWeight(QFont.Weight.Bold)
        p.setFont(f)
        p.setPen(QColor("#0B1014"))
        p.drawText(0, 0, 28, 28, Qt.AlignCenter, "P")


class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"background: {C_PANEL_BG}; border-bottom: 1px solid {C_BORDER_SOFT};"
        )
        self._build()

    def _build(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(0)

        row.addWidget(LogoWidget())
        row.addSpacing(10)

        app_name = QLabel("Parallax Studio")
        app_name.setStyleSheet(
            f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 600;"
        )
        row.addWidget(app_name)

        row.addSpacing(28)

        for icon, label, tip in [
            ("☐", "New",  "New project"),
            ("↗", "Open", "Open project"),
            ("↓", "Save", "Save project"),
        ]:
            btn = QPushButton(f"  {label}")
            btn.setToolTip(tip)
            btn.setFixedHeight(30)
            btn.setFixedWidth(72)
            btn.setStyleSheet(
                f"QPushButton {{ background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER}; "
                f"color: {C_TEXT_SECONDARY}; border-radius: 6px; font-size: 12px; }}"
                f"QPushButton:hover {{ border-color: {C_ACCENT}55; color: {C_TEXT_MAIN}; }}"
            )
            row.addWidget(btn)
            row.addSpacing(6)

        row.addStretch()

        preview_lbl = QLabel("▶  Preview 24fps")
        preview_lbl.setStyleSheet(
            f"color: {C_TEXT_SECONDARY}; font-size: 12px; "
            f"font-family: 'JetBrains Mono', 'SF Mono', monospace;"
        )
        row.addWidget(preview_lbl)

        row.addSpacing(16)

        export_btn = QPushButton("  Export MP4")
        export_btn.setObjectName("exportBtn")
        export_btn.setFixedHeight(32)
        export_btn.setFixedWidth(108)
        row.addWidget(export_btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parallax Studio")
        self.setMinimumSize(1280, 820)
        self.resize(1400, 900)
        self._build()

    def _build(self):
        central = QWidget()
        central.setStyleSheet(f"background: {C_WINDOW_BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(TopBar())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        body.addWidget(LayerPanel())
        body.addWidget(_vline())
        body.addWidget(CanvasPanel(), stretch=1)
        body.addWidget(_vline())
        body.addWidget(ControlsPanel())

        root.addLayout(body, stretch=1)
        root.addWidget(TimelineStrip())

        status = QStatusBar()
        status.setFixedHeight(22)
        status.showMessage("Ready  ·  No project loaded")
        self.setStatusBar(status)
