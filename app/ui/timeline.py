from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QSlider, QSizePolicy
from PySide6.QtCore import Qt, QRectF, QPointF, QRect
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QFont, QPainterPath, QPolygonF,
)
from app.ui.theme import (
    C_PANEL_BG, C_RAISED_PANEL, C_ACCENT, C_BORDER, C_BORDER_SOFT,
    C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED, C_CANVAS_SURROUND,
)


class PlayButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(C_ACCENT)))
        tri = QPolygonF([QPointF(8, 6), QPointF(8, 22), QPointF(22, 14)])
        p.drawPolygon(tri)


class PauseButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(C_TEXT_SECONDARY)))
        p.drawRect(QRectF(7, 6, 5, 16))
        p.drawRect(QRectF(16, 6, 5, 16))


class FilmStrip(QWidget):
    """Timeline bar with time markers, frame thumbnails, and a scrub head."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pos = 0.33  # playhead 0–1
        self._duration = 4.0
        self._frame_colors = [
            "#3A1A1A", "#4A2020", "#3A1820", "#2A1830",
            "#3A1A18", "#4A2818", "#3A2018", "#2A1A18",
        ]

    def mousePressEvent(self, event):
        self._pos = max(0.0, min(1.0, event.position().x() / self.width()))
        self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._pos = max(0.0, min(1.0, event.position().x() / self.width()))
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        # background
        p.fillRect(self.rect(), QColor(C_CANVAS_SURROUND))

        # time markers row (top ~16px)
        marker_h = 16
        p.setPen(QPen(QColor(C_TEXT_MUTED), 1))
        f = QFont()
        f.setFamily("JetBrains Mono, SF Mono, monospace")
        f.setPointSize(8)
        p.setFont(f)
        for i in range(5):   # 0s, 1s, 2s, 3s, 4s
            x = int(i / 4 * (w - 1))
            p.drawLine(x, 0, x, 6)
            p.drawText(QRect(x - 10, 6, 24, 10), Qt.AlignHCenter, f"{i}s")

        # filmstrip area
        strip_y = marker_h
        strip_h = h - marker_h
        frame_w = max(1, w // len(self._frame_colors))

        for i, col in enumerate(self._frame_colors):
            fx = i * frame_w
            fw = frame_w if i < len(self._frame_colors) - 1 else w - fx

            # frame gradient
            grad = QLinearGradient(QPointF(fx, strip_y), QPointF(fx, strip_y + strip_h))
            grad.setColorAt(0, QColor(col).lighter(130))
            grad.setColorAt(1, QColor(col))
            p.fillRect(QRect(fx, strip_y, fw, strip_h), grad)

            # frame border
            p.setPen(QPen(QColor(C_BORDER_SOFT), 1))
            p.drawLine(fx, strip_y, fx, strip_y + strip_h)

        # progress fill overlay
        filled_w = int(self._pos * w)
        p.setBrush(QBrush(QColor(C_ACCENT + "30")))
        p.setPen(Qt.NoPen)
        p.drawRect(QRect(0, strip_y, filled_w, strip_h))

        # playhead
        px = int(self._pos * w)
        p.setPen(QPen(QColor(C_ACCENT), 2))
        p.drawLine(px, 0, px, h)

        # playhead diamond
        p.setBrush(QBrush(QColor(C_ACCENT)))
        p.setPen(Qt.NoPen)
        diamond = QPolygonF([
            QPointF(px, strip_y + 8),
            QPointF(px - 5, strip_y),
            QPointF(px + 5, strip_y),
        ])
        p.drawPolygon(diamond)


class ToggleSwitch(QWidget):
    def __init__(self, on: bool = True, parent=None):
        super().__init__(parent)
        self._on = on
        self.setFixedSize(38, 20)
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
        p.drawRoundedRect(QRectF(0, 2, 38, 16), 8, 8)
        knob_x = 20.0 if self._on else 2.0
        p.setBrush(QBrush(QColor("#FFFFFF")))
        p.drawEllipse(QRectF(knob_x, 0, 20, 20))


class TimelineStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet(
            f"background: {C_PANEL_BG}; border-top: 1px solid {C_BORDER_SOFT};"
        )
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # top controls row
        top = QWidget()
        top.setFixedHeight(38)
        top.setStyleSheet(f"background: {C_PANEL_BG};")
        top_row = QHBoxLayout(top)
        top_row.setContentsMargins(12, 0, 12, 0)
        top_row.setSpacing(8)

        top_row.addWidget(PlayButton())
        top_row.addWidget(PauseButton())

        time_lbl = QLabel("1.32s / 4.0s")
        time_lbl.setStyleSheet(
            f"color: {C_ACCENT}; font-family: 'JetBrains Mono', 'SF Mono', monospace; font-size: 12px;"
        )
        top_row.addWidget(time_lbl)

        top_row.addStretch()

        speed_lbl = QLabel("Speed")
        speed_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        top_row.addWidget(speed_lbl)

        speed_slider = QSlider(Qt.Horizontal)
        speed_slider.setRange(0, 100)
        speed_slider.setValue(50)
        speed_slider.setFixedWidth(80)
        top_row.addWidget(speed_slider)

        speed_val = QLabel("1.00x")
        speed_val.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-family: 'JetBrains Mono', 'SF Mono', monospace; font-size: 11px;"
        )
        top_row.addWidget(speed_val)

        top_row.addSpacing(16)

        for label, is_on in [("Bounce", False), ("Seamless", True)]:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
            top_row.addWidget(lbl)
            top_row.addWidget(ToggleSwitch(is_on))
            top_row.addSpacing(4)

        outer.addWidget(top)

        # filmstrip row
        film = FilmStrip()
        outer.addWidget(film, stretch=1)
