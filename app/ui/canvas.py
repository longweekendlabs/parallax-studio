from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt, QRect, QRectF
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QLinearGradient, QRadialGradient,
    QFont, QPainterPath,
)

from app.ui.theme import (
    C_CANVAS_SURROUND, C_CHECKER_DARK, C_CHECKER_LIGHT,
    C_ACCENT, C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
    C_RAISED_PANEL, C_BORDER,
)

CHECKER_SIZE = 12


class StatusPill(QWidget):
    def __init__(self, text: str, accent: bool = False, parent=None):
        super().__init__(parent)
        self._text = text
        self._accent = accent
        self._font = QFont("JetBrains Mono, SF Mono, Menlo, monospace")
        self._font.setPointSize(10)
        self.setFont(self._font)
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(text) + 20
        self.setFixedSize(w, 22)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        bg = QColor(C_ACCENT + "28") if self._accent else QColor("#0B1014CC")
        border = QColor(C_ACCENT + "88") if self._accent else QColor("#24313C")
        text_color = QColor(C_ACCENT) if self._accent else QColor(C_TEXT_SECONDARY)

        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 11, 11)

        p.setPen(text_color)
        p.setFont(self._font)
        p.drawText(self.rect(), Qt.AlignCenter, self._text)


class PreviewStage(QWidget):
    """The actual preview canvas with checkerboard, frame, and pills."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Floating pills — laid out manually in resizeEvent
        self._pills = []
        pill_data = [
            ("Paint Overlay  ON", True),
            ("Selected: Character", False),
            ("Zoom  78%", False),
        ]
        for text, accent in pill_data:
            pill = StatusPill(text, accent, self)
            self._pills.append(pill)

        self._empty = True

    def _frame_rect(self) -> QRect:
        """The inner preview frame rect (16:9-ish, centered)."""
        margin = 32
        available = self.rect().adjusted(margin, margin, -margin, -margin)
        target_ratio = 16 / 9
        w = available.width()
        h = int(w / target_ratio)
        if h > available.height():
            h = available.height()
            w = int(h * target_ratio)
        x = available.x() + (available.width() - w) // 2
        y = available.y() + (available.height() - h) // 2
        return QRect(x, y, w, h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        fr = self._frame_rect()
        # place pills bottom-left of frame
        x = fr.left() + 8
        y = fr.bottom() - 28
        for pill in self._pills:
            pill.move(x, y)
            x += pill.width() + 6

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        # dark stage background
        p.fillRect(self.rect(), QColor(C_CANVAS_SURROUND))

        fr = self._frame_rect()

        # clip path for rounded frame
        path = QPainterPath()
        path.addRoundedRect(QRectF(fr), 6, 6)

        # checkerboard inside frame
        p.save()
        p.setClipPath(path)
        dark = QColor(C_CHECKER_DARK)
        light = QColor(C_CHECKER_LIGHT)
        cs = CHECKER_SIZE
        for row in range(fr.height() // cs + 1):
            for col in range(fr.width() // cs + 1):
                color = light if (row + col) % 2 == 0 else dark
                p.fillRect(fr.x() + col * cs, fr.y() + row * cs, cs, cs, color)

        if self._empty:
            self._draw_empty_state(p, fr)

        p.restore()

        # frame border with soft glow
        p.setPen(QPen(QColor(C_ACCENT + "44"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(fr), 6, 6)

        # inner shadow (top edge)
        from PySide6.QtCore import QPointF
        grad2 = QLinearGradient(
            QPointF(fr.x(), fr.y()),
            QPointF(fr.x(), fr.y() + 16),
        )
        grad2.setColorAt(0, QColor("#00000060"))
        grad2.setColorAt(1, QColor("#00000000"))
        p.save()
        p.setClipPath(path)
        p.fillRect(fr, grad2)
        p.restore()

    def _draw_empty_state(self, p: QPainter, fr: QRect):
        cx = fr.center().x()
        cy = fr.center().y()

        # dashed drop zone
        pen = QPen(QColor(C_ACCENT + "44"), 1, Qt.DashLine)
        pen.setDashPattern([6, 4])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        inner = fr.adjusted(30, 30, -30, -30)
        p.drawRoundedRect(QRectF(inner), 8, 8)

        # main text
        font = QFont("Inter, SF Pro Display, system-ui")
        font.setPointSize(18)
        font.setWeight(QFont.Weight.Light)
        p.setFont(font)
        p.setPen(QColor(C_TEXT_SECONDARY))
        p.drawText(QRect(fr.x(), cy - 48, fr.width(), 32), Qt.AlignHCenter, "Drop PNG layers here")

        # divider
        p.setPen(QPen(QColor(C_ACCENT + "55"), 1))
        mid_y = cy - 8
        p.drawLine(cx - 24, mid_y, cx - 8, mid_y)
        font2 = QFont("Inter, SF Pro Text, system-ui")
        font2.setPointSize(10)
        p.setFont(font2)
        p.setPen(QColor(C_TEXT_MUTED))
        p.drawText(QRect(cx - 6, mid_y - 8, 20, 16), Qt.AlignCenter, "or")
        p.setPen(QPen(QColor(C_ACCENT + "55"), 1))
        p.drawLine(cx + 8, mid_y, cx + 24, mid_y)

        # secondary text
        font3 = QFont("Inter, SF Pro Text, system-ui")
        font3.setPointSize(13)
        p.setFont(font3)
        p.setPen(QColor(C_ACCENT + "AA"))
        p.drawText(QRect(fr.x(), cy + 4, fr.width(), 28), Qt.AlignHCenter, "Add your first layer")

        # tip
        font4 = QFont("Inter, SF Pro Text, system-ui")
        font4.setPointSize(10)
        p.setFont(font4)
        p.setPen(QColor(C_TEXT_MUTED))
        p.drawText(
            QRect(fr.x(), cy + 44, fr.width(), 20),
            Qt.AlignHCenter,
            "Tip: background → character → foreground works best",
        )


class CanvasPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {C_CANVAS_SURROUND};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._stage = PreviewStage()
        layout.addWidget(self._stage)
