from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QLabel, QSplitter, QStatusBar, QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont

from app.ui.theme import (
    C_WINDOW_BG, C_PANEL_BG, C_RAISED_PANEL, C_ACCENT, C_EXPORT,
    C_BORDER, C_BORDER_SOFT, C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
)
from app.ui.layer_panel import LayerPanel
from app.ui.canvas import CanvasPanel
from app.ui.controls import ControlsPanel
from app.ui.timeline import TimelineStrip


def _vline() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Plain)
    line.setStyleSheet(f"background: {C_BORDER_SOFT}; max-width: 1px; border: none;")
    return line


class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(44)
        self.setStyleSheet(
            f"background: {C_PANEL_BG}; border-bottom: 1px solid {C_BORDER_SOFT};"
        )
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(0)

        # App name — left
        app_name = QLabel("Parallax Studio")
        app_name.setStyleSheet(
            f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 600; letter-spacing: 0.3px;"
        )
        layout.addWidget(app_name)

        layout.addSpacing(24)

        # New / Open / Save — center-left
        for label, tip in [("New", "New project"), ("Open", "Open project"), ("Save", "Save project")]:
            btn = QPushButton(label)
            btn.setToolTip(tip)
            btn.setFixedHeight(28)
            btn.setFixedWidth(52)
            btn.setStyleSheet(
                f"QPushButton {{ background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER}; "
                f"color: {C_TEXT_SECONDARY}; border-radius: 5px; font-size: 12px; }}"
                f"QPushButton:hover {{ border-color: {C_ACCENT}; color: {C_ACCENT}; }}"
            )
            layout.addWidget(btn)
            layout.addSpacing(4)

        layout.addStretch()

        # Preview FPS pill — center-right
        fps_lbl = QLabel("Preview  24 fps")
        fps_lbl.setStyleSheet(
            f"background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER_SOFT}; "
            f"border-radius: 5px; color: {C_ACCENT}; font-size: 11px; "
            f"font-family: 'JetBrains Mono', 'SF Mono', monospace; padding: 3px 10px;"
        )
        layout.addWidget(fps_lbl)

        layout.addSpacing(10)

        # Export button — right, amber
        export_btn = QPushButton("Export MP4")
        export_btn.setObjectName("exportBtn")
        export_btn.setFixedHeight(30)
        export_btn.setFixedWidth(96)
        layout.addWidget(export_btn)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Parallax Studio")
        self.setMinimumSize(1280, 820)
        self.resize(1400, 880)
        self._build()

    def _build(self):
        central = QWidget()
        central.setStyleSheet(f"background: {C_WINDOW_BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top command bar
        top_bar = TopBar()
        root.addWidget(top_bar)

        # Main body: layer panel | canvas | controls
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        layer_panel = LayerPanel()
        body.addWidget(layer_panel)
        body.addWidget(_vline())

        canvas_panel = CanvasPanel()
        body.addWidget(canvas_panel, stretch=1)

        body.addWidget(_vline())
        controls_panel = ControlsPanel()
        body.addWidget(controls_panel)

        root.addLayout(body, stretch=1)

        # Bottom timeline strip
        timeline = TimelineStrip()
        root.addWidget(timeline)

        # Status bar
        status = QStatusBar()
        status.setFixedHeight(22)
        status.showMessage("Ready  ·  No project loaded")
        self.setStatusBar(status)
