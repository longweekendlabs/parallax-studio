from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy, QHBoxLayout
from PySide6.QtCore import Qt, QRect, QRectF, QPointF, QSize
from PySide6.QtGui import (
    QPainter, QColor, QBrush, QPen, QLinearGradient,
    QFont, QPainterPath,
)
from app.ui.theme import (
    C_CANVAS_SURROUND, C_CHECKER_DARK, C_CHECKER_LIGHT,
    C_ACCENT, C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED,
    C_RAISED_PANEL, C_PANEL_BG, C_BORDER,
)

CHECKER = 14


class StatusPill(QWidget):
    def __init__(self, text: str, accent: bool = False, parent=None):
        super().__init__(parent)
        self._text = text
        self._accent = accent
        f = QFont()
        f.setFamily("JetBrains Mono, SF Mono, Menlo, monospace")
        f.setPointSize(10)
        self.setFont(f)
        fm = self.fontMetrics()
        self.setFixedSize(fm.horizontalAdvance(text) + 22, 24)
        self.setAttribute(Qt.WA_TranslucentBackground)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor(C_ACCENT + "28") if self._accent else QColor("#0C1318DD")
        border = QColor(C_ACCENT + "99") if self._accent else QColor("#2A3A46")
        fg = QColor(C_ACCENT) if self._accent else QColor(C_TEXT_SECONDARY)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 12, 12)
        p.setPen(fg)
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self._text)


class PreviewStage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        pill_data = [
            ("✏  Paint Overlay  ON", True),
            ("◎  Selected: Character", False),
            ("⊕  Zoom  78%", False),
        ]
        self._pills = []
        for text, accent in pill_data:
            pill = StatusPill(text, accent, self)
            self._pills.append(pill)

    def _frame_rect(self) -> QRect:
        m = 24
        avail = self.rect().adjusted(m, 44, -m, -m)  # top margin for pills
        ratio = 16 / 9
        w = avail.width()
        h = int(w / ratio)
        if h > avail.height():
            h = avail.height()
            w = int(h * ratio)
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        return QRect(x, y, w, h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # pills float top-left of frame
        fr = self._frame_rect()
        x = fr.left() + 10
        y = fr.top() - 32
        for pill in self._pills:
            pill.move(x, y)
            x += pill.width() + 8

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C_CANVAS_SURROUND))

        fr = self._frame_rect()

        path = QPainterPath()
        path.addRoundedRect(QRectF(fr), 6, 6)

        p.save()
        p.setClipPath(path)

        # checkerboard
        dark = QColor(C_CHECKER_DARK)
        light = QColor(C_CHECKER_LIGHT)
        for row in range(fr.height() // CHECKER + 2):
            for col in range(fr.width() // CHECKER + 2):
                c = light if (row + col) % 2 == 0 else dark
                p.fillRect(fr.x() + col * CHECKER, fr.y() + row * CHECKER, CHECKER, CHECKER, c)

        # placeholder scene gradient (simulating layered artwork)
        scene_grad = QLinearGradient(QPointF(fr.x(), fr.y()), QPointF(fr.x(), fr.bottom()))
        scene_grad.setColorAt(0.0, QColor("#1A0A08"))
        scene_grad.setColorAt(0.3, QColor("#3A1A1A"))
        scene_grad.setColorAt(0.6, QColor("#6A3020"))
        scene_grad.setColorAt(1.0, QColor("#1A1020"))
        p.setOpacity(0.85)
        p.fillRect(fr, scene_grad)

        # sky glow
        sky = QLinearGradient(QPointF(fr.x(), fr.y()), QPointF(fr.x(), fr.y() + fr.height() * 0.5))
        sky.setColorAt(0.0, QColor("#C06030AA"))
        sky.setColorAt(1.0, QColor("#00000000"))
        p.fillRect(fr, sky)
        p.setOpacity(1.0)

        p.restore()

        # frame border
        p.setPen(QPen(QColor(C_ACCENT + "33"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(fr).adjusted(0.5, 0.5, -0.5, -0.5), 6, 6)

        # inner top shadow
        p.save()
        p.setClipPath(path)
        shadow = QLinearGradient(QPointF(fr.x(), fr.y()), QPointF(fr.x(), fr.y() + 30))
        shadow.setColorAt(0, QColor("#00000055"))
        shadow.setColorAt(1, QColor("#00000000"))
        p.fillRect(fr, shadow)
        p.restore()

        # empty state text
        self._draw_empty_state(p, fr)

    def _draw_empty_state(self, p: QPainter, fr: QRect):
        cx = fr.center().x()
        cy = fr.center().y()

        # dashed border
        pen = QPen(QColor(C_ACCENT + "35"), 1, Qt.DashLine)
        pen.setDashPattern([6, 5])
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(fr.adjusted(28, 28, -28, -28)), 8, 8)

        f1 = QFont("Inter, SF Pro Display, system-ui")
        f1.setPointSize(17)
        f1.setWeight(QFont.Weight.Light)
        p.setFont(f1)
        p.setPen(QColor(C_TEXT_SECONDARY))
        p.drawText(QRect(fr.x(), cy - 44, fr.width(), 30), Qt.AlignHCenter, "Drop PNG layers here")

        p.setPen(QColor(C_TEXT_MUTED))
        f2 = QFont("Inter, SF Pro Text, system-ui")
        f2.setPointSize(10)
        p.setFont(f2)
        p.drawText(QRect(cx - 10, cy - 6, 20, 14), Qt.AlignHCenter, "or")

        f3 = QFont("Inter, SF Pro Text, system-ui")
        f3.setPointSize(13)
        p.setFont(f3)
        p.setPen(QColor(C_ACCENT + "BB"))
        p.drawText(QRect(fr.x(), cy + 10, fr.width(), 26), Qt.AlignHCenter, "Add your first layer")

        f4 = QFont("Inter, SF Pro Text, system-ui")
        f4.setPointSize(10)
        p.setFont(f4)
        p.setPen(QColor(C_TEXT_MUTED))
        p.drawText(
            QRect(fr.x(), cy + 50, fr.width(), 18),
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
        layout.addWidget(PreviewStage())
