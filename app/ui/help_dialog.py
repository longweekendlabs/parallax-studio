from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.theme import C_ACCENT, C_BORDER, C_PANEL_BG, C_TEXT_MAIN, C_TEXT_SECONDARY, C_WINDOW_BG


HELP_ROWS = [
    (
        "Paint Overlay",
        "Cyan marks depth painted toward the viewer. Violet marks depth painted away. Neutral 0.50 stays transparent.",
        [("Near", "#3DD9C9"), ("Far", "#A68BFF"), ("Neutral", "#25313A")],
    ),
    (
        "Depth Brush",
        "Use Paint to add depth and Erase to brush back toward neutral 0.50. Erase clears faster than the gentle paint default.",
        [("Paint", "#3DD9C9"), ("Erase", "#F2B35E"), ("Soft edge", "#91A1AD")],
    ),
    (
        "Motion Preview",
        "Motion unlocks only after the selected layer has depth variation. Preview FPS is for editing only; export FPS is chosen in Export.",
        [("Flat", "#5F6F7B"), ("Ready", "#3DD9C9")],
    ),
]


class LegendSwatch(QFrame):
    def __init__(self, label: str, color: str, parent=None):
        super().__init__(parent)
        self.setObjectName("legendSwatch")
        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        swatch = QLabel()
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(f"background: {color}; border: 1px solid {C_BORDER}; border-radius: 7px;")
        row.addWidget(swatch)

        text = QLabel(label)
        text.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
        row.addWidget(text)


class HelpRow(QFrame):
    def __init__(self, title: str, body: str, swatches: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        self.setObjectName("helpRow")
        self.setStyleSheet(
            f"""
            QFrame#helpRow {{
                background: {C_PANEL_BG};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
            """
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(16, 14, 16, 14)
        row.setSpacing(18)

        copy = QVBoxLayout()
        copy.setContentsMargins(0, 0, 0, 0)
        copy.setSpacing(6)
        title_label = QLabel(title)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet(f"color: {C_TEXT_MAIN}; background: transparent;")
        copy.addWidget(title_label)

        body_label = QLabel(body)
        body_label.setWordWrap(True)
        body_label.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px; background: transparent;")
        copy.addWidget(body_label)
        row.addLayout(copy, 1)

        legend = QVBoxLayout()
        legend.setContentsMargins(0, 0, 0, 0)
        legend.setSpacing(7)
        for label, color in swatches:
            legend.addWidget(LegendSwatch(label, color))
        legend.addStretch()
        row.addLayout(legend)


class QuickHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick Help")
        self.setFixedWidth(620)
        self.setModal(True)
        self._build()

    def _build(self):
        self.setStyleSheet(
            f"""
            QDialog {{
                background: {C_WINDOW_BG};
                color: {C_TEXT_MAIN};
            }}
            QLabel {{
                background: transparent;
            }}
            QPushButton {{
                background: {C_PANEL_BG};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                color: {C_TEXT_MAIN};
                padding: 6px 16px;
            }}
            QPushButton:hover {{
                border-color: {C_ACCENT};
                color: {C_ACCENT};
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        title = QLabel("Quick Help")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        subtitle = QLabel("Depth painting and preview behavior, without shortcuts mixed in.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(subtitle)

        for title_text, body, swatches in HELP_ROWS:
            layout.addWidget(HelpRow(title_text, body, swatches))

        close = QPushButton("Close")
        close.setFixedWidth(104)
        close.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close)
        close_row.addStretch()
        layout.addLayout(close_row)
