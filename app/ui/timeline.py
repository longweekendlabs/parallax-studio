from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_BORDER_SOFT,
    C_CANVAS_SURROUND,
    C_PANEL_BG,
    C_RAISED_PANEL,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
    C_WINDOW_BG,
)


class TransportButton(QWidget):
    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setFixedSize(56, 56)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#0D141B"))
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_TEXT_MAIN if self.mode == "pause" else C_TEXT_MAIN))
        if self.mode == "play":
            p.drawPolygon(QPolygonF([QPointF(22, 17), QPointF(22, 39), QPointF(39, 28)]))
        else:
            p.drawRect(QRectF(20, 17, 5, 22))
            p.drawRect(QRectF(31, 17, 5, 22))


class FilmStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.pos = 0.42

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(0, 0, 0, -2)
        p.fillRect(r, QColor(C_CANVAS_SURROUND))

        font = QFont("JetBrains Mono")
        font.setPointSize(10)
        p.setFont(font)
        p.setPen(QColor(C_TEXT_SECONDARY))
        for i in range(5):
            x = r.x() + int(i / 4 * r.width())
            p.drawLine(x, 0, x, 9)
            p.drawText(QRect(x - 16, 10, 32, 18), Qt.AlignCenter, f"{i}s")

        strip = QRect(r.x(), r.y() + 34, r.width(), r.height() - 38)
        path = QPainterPath()
        path.addRoundedRect(QRectF(strip), 4, 4)
        p.save()
        p.setClipPath(path)
        frame_count = 10
        frame_w = strip.width() / frame_count
        colors = ["#223A4D", "#6F4050", "#1E3145", "#273B58", "#7A4636"]
        for i in range(frame_count):
            x = strip.x() + i * frame_w
            grad = QLinearGradient(QPointF(x, strip.y()), QPointF(x, strip.bottom()))
            grad.setColorAt(0, QColor(colors[i % len(colors)]).lighter(150))
            grad.setColorAt(0.5, QColor("#D06B5C"))
            grad.setColorAt(1, QColor(colors[(i + 2) % len(colors)]).darker(140))
            p.fillRect(QRectF(x, strip.y(), frame_w + 1, strip.height()), grad)
            p.setPen(QPen(QColor("#0A0D11AA"), 1))
            p.drawLine(QPointF(x, strip.y()), QPointF(x, strip.bottom()))
        p.restore()

        p.setPen(QPen(QColor(C_BORDER), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(strip).adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)

        x = strip.x() + int(strip.width() * self.pos)
        p.setPen(QPen(QColor(C_ACCENT), 3))
        p.drawLine(x, 10, x, strip.bottom() + 4)
        p.setBrush(QColor(C_ACCENT))
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(x, 30), QPointF(x - 10, 10), QPointF(x + 10, 10)]))


class TimelineStrip(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(178)
        self.setStyleSheet(f"background: {C_WINDOW_BG};")
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 0, 16, 16)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("timelineShell")
        shell.setStyleSheet(
            f"""
            QFrame#timelineShell {{
                background: {C_PANEL_BG};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
            """
        )
        root.addWidget(shell)

        row = QHBoxLayout(shell)
        row.setContentsMargins(22, 20, 22, 20)
        row.setSpacing(20)

        row.addWidget(TransportButton("play"))
        row.addWidget(TransportButton("pause"))

        time = QLabel("1.32s")
        time.setStyleSheet(f"background: transparent; color: {C_ACCENT}; font-family: 'JetBrains Mono'; font-size: 18px;")
        row.addWidget(time)
        total = QLabel("/ 4.00s")
        total.setStyleSheet(f"background: transparent; color: {C_TEXT_SECONDARY}; font-family: 'JetBrains Mono'; font-size: 14px;")
        row.addWidget(total)

        film = FilmStrip()
        row.addWidget(film, stretch=1)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {C_BORDER};")
        row.addWidget(sep)

        meta_col = QVBoxLayout()
        meta_col.setSpacing(8)
        for label, value in [("Preview", "24fps"), ("Loop", "Motion panel")]:
            lbl = QLabel(label)
            lbl.setStyleSheet(f"background: transparent; color: {C_TEXT_SECONDARY}; font-size: 13px;")
            val = QLabel(value)
            val.setStyleSheet(f"background: transparent; color: {C_TEXT_MAIN}; font-size: 15px; font-weight: 600;")
            meta_col.addWidget(lbl)
            meta_col.addWidget(val)
        row.addLayout(meta_col)
