from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.ui.theme import C_ACCENT, C_BORDER, C_PANEL_BG, C_TEXT_MAIN, C_TEXT_SECONDARY, C_WINDOW_BG


SHORTCUT_GROUPS = [
    (
        "Project",
        [
            ("New project", "Ctrl+N"),
            ("Open project or image", "Ctrl+O"),
            ("Save", "Ctrl+S"),
            ("Save as", "Ctrl+Shift+S"),
            ("Add image layer", "Shift+O"),
            ("Export", "Ctrl+E"),
        ],
    ),
    (
        "Editing",
        [
            ("Undo", "Ctrl+Z"),
            ("Redo", "Ctrl+Y / Ctrl+Shift+Z"),
            ("Quick help", "F1"),
            ("Keyboard shortcuts", "Ctrl+/"),
        ],
    ),
]


class ShortcutsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setFixedWidth(600)
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
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(14)

        title = QLabel("Keyboard Shortcuts")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title)

        subtitle = QLabel("Quick actions available while editing.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        subtitle.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(subtitle)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {C_BORDER};")
        layout.addWidget(line)

        groups = QGridLayout()
        groups.setContentsMargins(0, 0, 0, 0)
        groups.setHorizontalSpacing(28)
        groups.setVerticalSpacing(16)
        for index, (group_name, rows) in enumerate(SHORTCUT_GROUPS):
            groups.addWidget(self._group_widget(group_name, rows), 0, index)
        layout.addLayout(groups)

        close = QPushButton("Close")
        close.setFixedWidth(104)
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        row.addStretch()
        layout.addLayout(row)

    def _group_widget(self, group_name: str, rows: list[tuple[str, str]]) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        group_label = QLabel(group_name.upper())
        group_label.setStyleSheet(f"color: {C_ACCENT}; font-size: 11px; font-weight: 700;")
        layout.addWidget(group_label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)
        for row, (action, keys) in enumerate(rows):
            action_label = QLabel(action)
            action_label.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 12px;")
            key_label = QLabel(keys)
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight)
            key_label.setStyleSheet(f"color: {C_ACCENT}; font-family: monospace; font-weight: 700;")
            grid.addWidget(action_label, row, 0)
            grid.addWidget(key_label, row, 1)
        grid.setColumnStretch(0, 1)
        layout.addLayout(grid)
        layout.addStretch()
        return panel
