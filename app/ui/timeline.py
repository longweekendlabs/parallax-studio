from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QSlider, QSizePolicy,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient, QFont,
)

from app.ui.theme import (
    C_PANEL_BG, C_RAISED_PANEL, C_ACCENT, C_BORDER, C_BORDER_SOFT,
    C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
)


class PlayPauseButton(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._playing = False
        self.setFixedSize(32, 32)
        self.setCursor(Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self._playing = not self._playing
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # circle background
        p.setBrush(QBrush(QColor(C_ACCENT + "22")))
        p.setPen(QPen(QColor(C_ACCENT + "88"), 1))
        p.drawEllipse(QRectF(1, 1, 30, 30))

        p.setBrush(QBrush(QColor(C_ACCENT)))
        p.setPen(Qt.NoPen)

        cx, cy = 16, 16
        if self._playing:
            # pause bars
            p.drawRect(int(cx - 6), int(cy - 5), 4, 10)
            p.drawRect(int(cx + 2), int(cy - 5), 4, 10)
        else:
            # play triangle
            from PySide6.QtGui import QPolygonF
            tri = QPolygonF([
                QPointF(cx - 4, cy - 6),
                QPointF(cx - 4, cy + 6),
                QPointF(cx + 7, cy),
            ])
            p.drawPolygon(tri)


class ScrubBar(QWidget):
    """Simple custom scrub bar with marker."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(20)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._pos = 0.45  # 0.0 – 1.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        track_y = h // 2

        # track
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor(C_RAISED_PANEL)))
        p.drawRoundedRect(QRectF(0, track_y - 2, w, 4), 2, 2)

        # filled portion
        filled_w = self._pos * w
        grad = QLinearGradient(QPointF(0, 0), QPointF(filled_w, 0))
        grad.setColorAt(0, QColor(C_ACCENT + "88"))
        grad.setColorAt(1, QColor(C_ACCENT))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(QRectF(0, track_y - 2, filled_w, 4), 2, 2)

        # scrub head
        marker_x = self._pos * w
        p.setBrush(QBrush(QColor(C_ACCENT)))
        p.setPen(QPen(QColor(C_PANEL_BG), 2))
        p.drawEllipse(QPointF(marker_x, track_y), 5, 5)

    def mousePressEvent(self, event):
        self._pos = max(0.0, min(1.0, event.position().x() / self.width()))
        self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self._pos = max(0.0, min(1.0, event.position().x() / self.width()))
            self.update()


class TimelineStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(48)
        self.setStyleSheet(
            f"background: {C_PANEL_BG}; border-top: 1px solid {C_BORDER_SOFT};"
        )
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        play_btn = PlayPauseButton()
        layout.addWidget(play_btn)

        time_lbl = QLabel("00:00")
        time_lbl.setStyleSheet(
            f"color: {C_ACCENT}; font-family: 'JetBrains Mono', 'SF Mono', monospace; font-size: 12px;"
        )
        layout.addWidget(time_lbl)

        scrub = ScrubBar()
        layout.addWidget(scrub)

        duration_lbl = QLabel("04.0s")
        duration_lbl.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-family: 'JetBrains Mono', 'SF Mono', monospace; font-size: 11px;"
        )
        layout.addWidget(duration_lbl)

        sep = QLabel("|")
        sep.setStyleSheet(f"color: {C_BORDER};")
        layout.addWidget(sep)

        speed_lbl = QLabel("Speed")
        speed_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(speed_lbl)

        speed_slider = QSlider(Qt.Horizontal)
        speed_slider.setRange(0, 100)
        speed_slider.setValue(35)
        speed_slider.setFixedWidth(80)
        layout.addWidget(speed_slider)

        sep2 = QLabel("|")
        sep2.setStyleSheet(f"color: {C_BORDER};")
        layout.addWidget(sep2)

        # Bounce / Seamless toggle
        for i, opt in enumerate(["Seamless", "Bounce"]):
            btn = QPushButton(opt)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setFixedHeight(24)
            btn.setFixedWidth(72)
            radius = (
                "border-top-left-radius: 4px; border-bottom-left-radius: 4px; border-radius: 0;"
                if i == 0
                else "border-top-right-radius: 4px; border-bottom-right-radius: 4px; border-radius: 0;"
            )
            btn.setStyleSheet(
                f"QPushButton {{ background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER}; "
                f"color: {C_TEXT_SECONDARY}; font-size: 11px; {radius} }}"
                f"QPushButton:checked {{ background: {C_ACCENT}22; border-color: {C_ACCENT}; color: {C_ACCENT}; }}"
            )
            layout.addWidget(btn)
