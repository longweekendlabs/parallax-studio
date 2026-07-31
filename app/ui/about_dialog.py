from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from app.version import __app_name__, __copyright__, __org_name__, __version__
from app.ui.theme import C_ACCENT, C_BORDER, C_PANEL_BG, C_TEXT_MAIN, C_TEXT_SECONDARY, C_WINDOW_BG
from app.utils.resources import resource_path


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"About {__app_name__}")
        self.setFixedWidth(430)
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
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)

        logo_path = resource_path("assets", "icons", "long-weekend-labs-logo.png")
        if logo_path.exists():
            logo = QLabel()
            logo.setPixmap(
                QPixmap(str(logo_path)).scaled(
                    112,
                    112,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
            logo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            layout.addWidget(logo)

        name = QLabel(__app_name__)
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        name.setFont(font)
        name.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(name)

        version = QLabel(f"Version {__version__}")
        version.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        version.setStyleSheet(f"color: {C_ACCENT}; font-size: 12px;")
        layout.addWidget(version)

        org = QLabel(f"{__org_name__}\n{__copyright__}")
        org.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        org.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(org)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"background: {C_BORDER};")
        layout.addWidget(line)

        body = QLabel(
            "Parallax Studio turns static artwork layers into short looping "
            "2.5D motion previews and exports."
        )
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(body)

        links = QLabel(
            '<a href="https://longweekendlabs.github.io/parallax-studio/">'
            'longweekendlabs.github.io/parallax-studio</a><br>'
            '<a href="https://github.com/longweekendlabs/parallax-studio">'
            'github.com/longweekendlabs/parallax-studio</a>'
        )
        links.setOpenExternalLinks(True)
        links.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        links.setStyleSheet(f"color: {C_ACCENT}; font-size: 11px;")
        layout.addWidget(links)

        stack = QLabel("Built with Python, PySide6, NumPy, OpenCV, imageio, and Pillow.")
        stack.setWordWrap(True)
        stack.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        stack.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 11px;")
        layout.addWidget(stack)

        close = QPushButton("Close")
        close.setFixedWidth(100)
        close.clicked.connect(self.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close)
        row.addStretch()
        layout.addLayout(row)
