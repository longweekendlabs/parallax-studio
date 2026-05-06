from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPixmap

from app.ui.theme import (
    C_PANEL_BG, C_RAISED_PANEL, C_ACCENT, C_BORDER,
    C_BORDER_SOFT, C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
    C_DANGER,
)

# Dummy layer data for Phase 0
DUMMY_LAYERS = [
    {"name": "Foreground",  "type": "PNG", "visible": True,  "color": "#2A3A2A"},
    {"name": "Character",   "type": "PNG", "visible": True,  "color": "#2A2A3A"},
    {"name": "Background",  "type": "JPG", "visible": True,  "color": "#3A2A2A"},
]


class LayerThumbnail(QWidget):
    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self._color = QColor(color)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QBrush(self._color))
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawRoundedRect(0, 0, 35, 35, 4, 4)
        # checkerboard hint in corner
        p.setBrush(QBrush(QColor("#FFFFFF18")))
        p.setPen(Qt.NoPen)
        for row in range(3):
            for col in range(3):
                if (row + col) % 2 == 0:
                    p.drawRect(col * 12, row * 12, 12, 12)


class EyeButton(QWidget):
    """Visibility toggle drawn as a simple eye icon."""
    def __init__(self, visible: bool = True, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self._visible = visible
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(C_ACCENT) if self._visible else QColor(C_TEXT_MUTED)
        p.setPen(QPen(color, 1.5))
        p.setBrush(Qt.NoBrush)
        # eye outline
        from PySide6.QtCore import QRectF
        p.drawEllipse(QRectF(2, 6, 16, 8))
        # pupil
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(7, 8, 6, 6))
        if not self._visible:
            p.setPen(QPen(color, 1.5))
            p.drawLine(2, 4, 18, 16)

    def mousePressEvent(self, event):
        self._visible = not self._visible
        self.update()


class DragHandle(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 20)
        self.setCursor(Qt.SizeVerCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(QColor(C_TEXT_MUTED), 1))
        for y in (6, 10, 14):
            p.drawLine(2, y, 12, y)


class LayerCard(QWidget):
    def __init__(self, data: dict, selected: bool = False, parent=None):
        super().__init__(parent)
        self._selected = selected
        self._data = data
        self.setFixedHeight(58)
        self.setCursor(Qt.PointingHandCursor)
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(0)

        # left cyan accent bar (selected indicator)
        self._accent_bar = QFrame()
        self._accent_bar.setFixedWidth(3)
        self._accent_bar.setStyleSheet(
            f"background: {C_ACCENT}; border-radius: 2px;" if self._selected
            else "background: transparent;"
        )
        layout.addWidget(self._accent_bar)

        layout.addSpacing(8)

        drag = DragHandle()
        layout.addWidget(drag)

        layout.addSpacing(8)

        thumb = LayerThumbnail(self._data["color"])
        layout.addWidget(thumb)

        layout.addSpacing(10)

        info = QVBoxLayout()
        info.setSpacing(2)
        name_label = QLabel(self._data["name"])
        name_label.setStyleSheet(
            f"color: {C_ACCENT}; font-weight: 600; font-size: 13px;"
            if self._selected
            else f"color: {C_TEXT_MAIN}; font-size: 13px;"
        )
        type_label = QLabel(self._data["type"])
        type_label.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 10px; "
            f"font-family: 'JetBrains Mono', 'SF Mono', monospace;"
        )
        info.addWidget(name_label)
        info.addWidget(type_label)
        layout.addLayout(info)

        layout.addStretch()

        eye = EyeButton(self._data["visible"])
        layout.addWidget(eye)

        layout.addSpacing(4)

        more = QLabel("···")
        more.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 16px;")
        more.setCursor(Qt.PointingHandCursor)
        layout.addWidget(more)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._selected:
            p.setBrush(QBrush(QColor(C_ACCENT + "18")))
            p.setPen(QPen(QColor(C_ACCENT + "55"), 1))
        else:
            p.setBrush(QBrush(QColor(C_RAISED_PANEL)))
            p.setPen(QPen(QColor(C_BORDER_SOFT), 1))

        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)

        if self._selected:
            # soft glow effect
            glow = QPen(QColor(C_ACCENT + "33"), 3)
            p.setPen(glow)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(self.rect().adjusted(0, 0, 0, 0), 6, 6)


class LayerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(240)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {C_PANEL_BG};")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: {C_PANEL_BG}; border-bottom: 1px solid {C_BORDER_SOFT};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 8, 0)

        title = QLabel("LAYERS")
        title.setObjectName("sectionHeader")

        add_btn = QPushButton("+ Add")
        add_btn.setFixedHeight(24)
        add_btn.setFixedWidth(52)
        add_btn.setStyleSheet(
            f"background: {C_ACCENT}22; border: 1px solid {C_ACCENT}66; "
            f"color: {C_ACCENT}; border-radius: 4px; font-size: 11px; padding: 0 6px;"
        )

        h_layout.addWidget(title)
        h_layout.addStretch()
        h_layout.addWidget(add_btn)
        layout.addWidget(header)

        # scroll area for cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        cards_widget = QWidget()
        cards_widget.setStyleSheet("background: transparent;")
        cards_layout = QVBoxLayout(cards_widget)
        cards_layout.setContentsMargins(8, 8, 8, 8)
        cards_layout.setSpacing(6)

        for i, layer in enumerate(DUMMY_LAYERS):
            card = LayerCard(layer, selected=(i == 1))  # "Character" selected
            cards_layout.addWidget(card)

        cards_layout.addStretch()
        scroll.setWidget(cards_widget)
        layout.addWidget(scroll)

        # footer
        footer = QWidget()
        footer.setFixedHeight(36)
        footer.setStyleSheet(f"background: {C_PANEL_BG}; border-top: 1px solid {C_BORDER_SOFT};")
        f_layout = QHBoxLayout(footer)
        f_layout.setContentsMargins(10, 0, 10, 0)
        f_layout.setSpacing(6)

        for label, tip in [("⊕", "Add layer"), ("⊖", "Remove layer"), ("❐", "Duplicate")]:
            btn = QPushButton(label)
            btn.setFixedSize(26, 26)
            btn.setToolTip(tip)
            btn.setStyleSheet(
                f"background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER}; "
                f"color: {C_TEXT_SECONDARY}; border-radius: 4px; font-size: 14px;"
            )
            f_layout.addWidget(btn)

        f_layout.addStretch()
        layout.addWidget(footer)
