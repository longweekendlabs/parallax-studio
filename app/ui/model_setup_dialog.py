"""First-run prompt for the models the depth buttons need.

The catalogue itself lives on a Settings page, because which models are
installed is a setting. This window exists only for the one case where a
window of its own is right: the app has just started, something it needs is
missing, and downloading it is the entire reason the window is open.
"""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.model_panel import ModelPanel, essential_missing, missing_models  # noqa: F401
from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_BORDER_SOFT,
    C_PANEL_BG,
    C_TEXT_MAIN,
    C_TEXT_SECONDARY,
    C_WINDOW_BG,
)


class ModelSetupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set up models")
        self.setModal(True)
        self.setFixedSize(600, 520)
        self.setStyleSheet(
            f"""
            QDialog {{ background: {C_WINDOW_BG}; color: {C_TEXT_MAIN}; }}
            QLabel {{ background: transparent; }}
            QPushButton#footerBtn {{
                background: {C_PANEL_BG}; border: 1px solid {C_BORDER};
                border-radius: 6px; color: {C_TEXT_MAIN}; padding: 6px 18px; font-size: 12.5px;
            }}
            QPushButton#footerBtn:hover {{ border-color: {C_ACCENT}; color: {C_ACCENT}; }}
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QWidget()
        head.setStyleSheet("background: transparent;")
        head_lay = QVBoxLayout(head)
        head_lay.setContentsMargins(24, 20, 24, 8)
        head_lay.setSpacing(6)
        title = QLabel("Offline models")
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 600; color: {C_TEXT_MAIN}; background: transparent;"
        )
        head_lay.addWidget(title)
        blurb = QLabel(
            "Auto Depth, Body Relief and the figure motions run entirely on this machine. Each model "
            "is downloaded once from its original publisher and then used offline. "
            "Nothing is sent anywhere."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet(
            f"font-size: 11.5px; color: {C_TEXT_SECONDARY}; background: transparent;"
        )
        head_lay.addWidget(blurb)
        outer.addWidget(head)

        body = QWidget()
        body.setStyleSheet("background: transparent;")
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(24, 0, 24, 12)
        self.panel = ModelPanel()
        body_lay.addWidget(self.panel)
        outer.addWidget(body, 1)

        bar = QWidget()
        bar.setStyleSheet(
            f"background: {C_WINDOW_BG}; border-top: 1px solid {C_BORDER_SOFT};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(22, 12, 22, 14)
        row.addStretch()
        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("footerBtn")
        self.close_button.clicked.connect(self._on_close)
        row.addWidget(self.close_button)
        outer.addWidget(bar)

    def _on_close(self):
        if self.panel.is_busy():
            self.panel.cancel()
            return
        self.accept()

    def closeEvent(self, event):
        self.panel.cancel()
        super().closeEvent(event)
