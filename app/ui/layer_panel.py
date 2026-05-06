from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QFrame,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QRadialGradient,
    QFont,
)
from app.ui.theme import (
    C_PANEL_BG, C_RAISED_PANEL, C_ACCENT, C_BORDER,
    C_BORDER_SOFT, C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
)

DUMMY_LAYERS = [
    {
        "name": "Foreground",
        "info": "3.2 MB · PNG",
        "visible": True,
        "grad": ("#A8C5A0", "#4A7A5A", "#2A3A28"),
    },
    {
        "name": "Character",
        "info": "4.7 MB · PNG",
        "visible": True,
        "selected": True,
        "grad": ("#8B6A8B", "#3A2A5A", "#1A1028"),
    },
    {
        "name": "Background",
        "info": "5.6 MB · JPG",
        "visible": True,
        "grad": ("#C0804A", "#6A3A2A", "#1A0A08"),
    },
]


class LayerThumbnail(QWidget):
    def __init__(self, grad_colors, parent=None):
        super().__init__(parent)
        self.setFixedSize(64, 64)
        self._colors = grad_colors

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(QPointF(0, 0), QPointF(64, 64))
        grad.setColorAt(0.0, QColor(self._colors[0]))
        grad.setColorAt(0.5, QColor(self._colors[1]))
        grad.setColorAt(1.0, QColor(self._colors[2]))

        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, 64, 64), 4, 4)

        # subtle checkerboard hint in corner (transparency indicator)
        cs = 8
        p.setOpacity(0.15)
        p.setBrush(QBrush(QColor("#FFFFFF")))
        for row in range(2):
            for col in range(2):
                if (row + col) % 2 == 0:
                    p.drawRect(col * cs, row * cs, cs, cs)
        p.setOpacity(1.0)


class EyeIcon(QWidget):
    def __init__(self, visible=True, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self._on = visible
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self._on = not self._on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor(C_ACCENT) if self._on else QColor(C_TEXT_MUTED)
        p.setPen(QPen(color, 1.4))
        p.setBrush(Qt.NoBrush)
        # eye arc
        p.drawArc(QRectF(2, 5, 18, 12), 0, 180 * 16)
        p.drawArc(QRectF(2, 5, 18, 12), 180 * 16, 180 * 16)
        # pupil
        p.setBrush(QBrush(color))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QRectF(8, 8, 6, 6))
        if not self._on:
            p.setPen(QPen(color, 1.5))
            p.drawLine(QPointF(3, 4), QPointF(19, 18))


class DragDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 22)
        self.setCursor(Qt.SizeVerCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(C_TEXT_MUTED)))
        for row in range(3):
            for col in range(2):
                p.drawEllipse(col * 5 + 1, row * 6 + 4, 2, 2)


class LayerCard(QWidget):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self._selected = data.get("selected", False)
        self.setFixedHeight(88)
        self.setCursor(Qt.PointingHandCursor)
        self._build(data)

    def _build(self, data):
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 4, 8, 4)
        outer.setSpacing(0)

        # cyan accent bar
        bar = QFrame()
        bar.setFixedWidth(3)
        bar.setStyleSheet(
            f"background: {C_ACCENT}; border-radius: 1px;"
            if self._selected else "background: transparent;"
        )
        outer.addWidget(bar)

        outer.addSpacing(6)

        dots = DragDots()
        outer.addWidget(dots)

        outer.addSpacing(6)

        thumb = LayerThumbnail(data["grad"])
        outer.addWidget(thumb)

        outer.addSpacing(10)

        # name + info
        info_col = QVBoxLayout()
        info_col.setSpacing(3)
        info_col.setAlignment(Qt.AlignVCenter)

        name = QLabel(data["name"])
        name.setStyleSheet(
            f"color: {C_ACCENT}; font-size: 13px; font-weight: 600;"
            if self._selected
            else f"color: {C_TEXT_MAIN}; font-size: 13px; font-weight: 500;"
        )
        info_lbl = QLabel(data["info"])
        info_lbl.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 10px; "
            f"font-family: 'JetBrains Mono', 'SF Mono', monospace;"
        )
        info_col.addStretch()
        info_col.addWidget(name)
        info_col.addWidget(info_lbl)
        info_col.addStretch()
        outer.addLayout(info_col)

        outer.addStretch()

        right_col = QVBoxLayout()
        right_col.setSpacing(4)
        right_col.setAlignment(Qt.AlignVCenter)

        eye = EyeIcon(data["visible"])
        more = QLabel("···")
        more.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 15px; letter-spacing: 1px;")
        more.setCursor(Qt.PointingHandCursor)

        right_col.addStretch()
        right_col.addWidget(eye, alignment=Qt.AlignRight)
        right_col.addWidget(more, alignment=Qt.AlignRight)
        right_col.addStretch()
        outer.addLayout(right_col)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if self._selected:
            p.setBrush(QBrush(QColor(C_ACCENT + "18")))
            p.setPen(QPen(QColor(C_ACCENT + "50"), 1))
        else:
            p.setBrush(QBrush(QColor(C_RAISED_PANEL)))
            p.setPen(QPen(QColor(C_BORDER_SOFT), 1))

        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)


class LayerPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {C_PANEL_BG};")
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # header
        header = QWidget()
        header.setFixedHeight(44)
        header.setStyleSheet(
            f"background: {C_PANEL_BG}; border-bottom: 1px solid {C_BORDER_SOFT};"
        )
        h = QHBoxLayout(header)
        h.setContentsMargins(14, 0, 10, 0)

        title = QLabel("LAYERS")
        title.setObjectName("sectionHeader")

        add_btn = QPushButton("+")
        add_btn.setFixedSize(26, 26)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {C_BORDER}; "
            f"color: {C_TEXT_SECONDARY}; border-radius: 5px; font-size: 16px; font-weight: 300; }}"
            f"QPushButton:hover {{ border-color: {C_ACCENT}; color: {C_ACCENT}; }}"
        )
        h.addWidget(title)
        h.addStretch()
        h.addWidget(add_btn)
        layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(8, 8, 8, 8)
        inner_layout.setSpacing(6)

        for data in DUMMY_LAYERS:
            inner_layout.addWidget(LayerCard(data))

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)
