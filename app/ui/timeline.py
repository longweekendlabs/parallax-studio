from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_BORDER_SOFT,
    C_CANVAS_SURROUND,
    C_EXPORT,
    C_PANEL_BG,
    C_RAISED_PANEL,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
    C_WINDOW_BG,
)


class TransportButton(QWidget):
    clicked = Signal()

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.active = False
        self.setFixedSize(56, 56)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("Play preview loop" if mode == "play" else "Pause preview loop")

    def set_active(self, active: bool):
        self.active = active
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor("#102027" if self.active else "#0D141B"))
        p.setPen(QPen(QColor(C_ACCENT if self.active else C_BORDER), 1))
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
        self.pos = 0.0
        self.ready = False

    def set_pos(self, pos: float):
        self.pos = max(0.0, min(1.0, pos))
        self.update()

    def set_ready(self, ready: bool):
        self.ready = ready
        self.update()

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
        p.fillRect(strip, QColor("#0A0F13"))
        if self.ready:
            progress = QRectF(strip.x(), strip.y(), strip.width() * self.pos, strip.height())
            grad = QLinearGradient(QPointF(progress.x(), progress.y()), QPointF(progress.right(), progress.y()))
            grad.setColorAt(0, QColor("#1B716D"))
            grad.setColorAt(1, QColor(C_ACCENT))
            p.fillRect(progress, grad)
        else:
            font = QFont("Inter")
            font.setPointSize(11)
            p.setFont(font)
            p.setPen(QColor(C_TEXT_MUTED))
            p.drawText(QRectF(strip), Qt.AlignmentFlag.AlignCenter, "Paint depth to enable preview loop")
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


class FpsSelector(QWidget):
    """Preview playback rate.

    The choices mirror the export frame rates so the preview can be set to the
    rate the file will be rendered at before committing to a render. Note this
    only affects smoothness: loop speed comes from duration, in both paths.
    """

    changed = Signal(int)

    RATES = (24, 30, 60)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 24
        self._buttons: dict[int, QPushButton] = {}
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        for rate in self.RATES:
            btn = QPushButton(str(rate))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedSize(30, 26)
            btn.setToolTip(f"Play the preview at {rate} fps, matching a {rate} fps export")
            btn.clicked.connect(lambda _=False, r=rate: self.set_value(r))
            self._buttons[rate] = btn
            row.addWidget(btn)

        # Three bare numbers in a toolbar say nothing about what they do. The
        # unit is what makes them read as a frame rate rather than, say, a
        # zoom or a brush size.
        unit = QLabel("fps")
        unit.setStyleSheet(
            f"color: {C_TEXT_MUTED}; font-size: 11px; background: transparent;"
        )
        row.addSpacing(2)
        row.addWidget(unit)
        row.addStretch()
        self._sync()

    def value(self) -> int:
        return self._value

    def set_value(self, rate: int, emit: bool = True):
        if rate not in self._buttons:
            return
        changed = rate != self._value
        self._value = rate
        self._sync()
        if changed and emit:
            self.changed.emit(rate)

    def _sync(self):
        for rate, btn in self._buttons.items():
            active = rate == self._value
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background: {C_ACCENT if active else "transparent"};
                    border: 1px solid {C_ACCENT if active else C_BORDER};
                    border-radius: 5px;
                    color: {"#08131A" if active else C_TEXT_SECONDARY};
                    font-size: 12px;
                    font-weight: {700 if active else 500};
                    /* The application sheet gives every QPushButton 14px of
                       side padding. These are 30px wide and fixed, so that
                       padding claimed 28 of the 30 and left two pixels for the
                       number, which Qt then elided away to nothing. The buttons
                       rendered as three blank boxes. */
                    padding: 0px;
                    text-align: center;
                }}
                QPushButton:hover {{
                    border-color: {C_ACCENT};
                }}
                QPushButton:disabled {{
                    color: {C_TEXT_MUTED};
                    border-color: {C_BORDER_SOFT};
                    background: transparent;
                }}
                """
            )

    def setEnabled(self, enabled: bool):  # noqa: N802 - Qt naming
        super().setEnabled(enabled)
        for btn in self._buttons.values():
            btn.setEnabled(enabled)


class TimelineStrip(QWidget):
    playRequested = Signal()
    pauseRequested = Signal()
    fpsChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(178)
        self.setStyleSheet(f"background: {C_WINDOW_BG};")
        self.play_button: TransportButton | None = None
        self.pause_button: TransportButton | None = None
        self.time_label: QLabel | None = None
        self.total_label: QLabel | None = None
        self.film: FilmStrip | None = None
        self._ready = False
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

        self.play_button = TransportButton("play")
        self.pause_button = TransportButton("pause")
        self.play_button.clicked.connect(self.playRequested.emit)
        self.pause_button.clicked.connect(self.pauseRequested.emit)
        row.addWidget(self.play_button)
        row.addWidget(self.pause_button)

        self.time_label = QLabel("0.00s")
        self.time_label.setStyleSheet(f"background: transparent; color: {C_ACCENT}; font-family: 'JetBrains Mono'; font-size: 18px;")
        row.addWidget(self.time_label)
        self.total_label = QLabel("/ 0.00s")
        self.total_label.setStyleSheet(f"background: transparent; color: {C_TEXT_SECONDARY}; font-family: 'JetBrains Mono'; font-size: 14px;")
        row.addWidget(self.total_label)

        self.film = FilmStrip()
        row.addWidget(self.film, stretch=1)

        sep = QFrame()
        sep.setFixedWidth(1)
        sep.setStyleSheet(f"background: {C_BORDER};")
        row.addWidget(sep)

        meta_col = QVBoxLayout()
        meta_col.setSpacing(6)

        fps_lbl = QLabel("Preview fps")
        fps_lbl.setStyleSheet(f"background: transparent; color: {C_TEXT_SECONDARY}; font-size: 13px;")
        meta_col.addWidget(fps_lbl)
        self.fps_selector = FpsSelector()
        self.fps_selector.changed.connect(self.fpsChanged.emit)
        meta_col.addWidget(self.fps_selector)

        # Only speaks up when the preview cannot keep up with the selected rate,
        # which is the case where the preview stops predicting the export.
        self.fps_actual_label = QLabel("")
        self.fps_actual_label.setStyleSheet(
            f"background: transparent; color: {C_EXPORT}; font-size: 11px;"
        )
        meta_col.addWidget(self.fps_actual_label)

        loop_lbl = QLabel("Loop")
        loop_lbl.setStyleSheet(f"background: transparent; color: {C_TEXT_SECONDARY}; font-size: 13px;")
        loop_val = QLabel("Motion panel")
        loop_val.setStyleSheet(f"background: transparent; color: {C_TEXT_MAIN}; font-size: 15px; font-weight: 600;")
        meta_col.addWidget(loop_lbl)
        meta_col.addWidget(loop_val)
        row.addLayout(meta_col)
        self.set_preview_ready(False)
        self.set_playing(False)

    def set_playing(self, playing: bool):
        if self.play_button is not None:
            self.play_button.set_active(self._ready and playing)
            self.play_button.setEnabled(self._ready)
        if self.pause_button is not None:
            self.pause_button.set_active(self._ready and not playing)
            self.pause_button.setEnabled(self._ready)

    def set_preview_fps(self, fps: int):
        self.fps_selector.set_value(fps, emit=False)

    def set_measured_fps(self, measured: float | None):
        """Report the rate the preview is actually achieving.

        Stays blank while the preview keeps up. When it cannot, the preview is
        no longer a fair prediction of the exported file, and the user needs to
        know that before judging the motion by it.
        """
        target = self.fps_selector.value()
        if measured is None or measured >= target * 0.85:
            self.fps_actual_label.setText("")
            self.fps_actual_label.setToolTip("")
            return
        self.fps_actual_label.setText(f"actual {measured:.0f} fps")
        self.fps_actual_label.setToolTip(
            f"This image is too large to preview at {target} fps. The export still "
            f"renders every frame, so the file will be smoother than this preview."
        )

    def set_preview_ready(self, ready: bool):
        self._ready = ready
        self.fps_selector.setEnabled(ready)
        if not ready:
            self.set_measured_fps(None)
        self.setToolTip(
            "Preview loop follows the generated parallax motion"
            if ready
            else "Paint depth variation before using the preview loop"
        )
        if self.film is not None:
            self.film.set_ready(ready)
        if not ready:
            self.set_time(0.0, 0.0)
            self.set_playing(False)

    def set_time(self, elapsed: float, duration: float):
        duration = max(0.0, float(duration))
        elapsed = max(0.0, min(float(elapsed), duration)) if duration else 0.0
        if self.time_label is not None:
            self.time_label.setText(f"{elapsed:.2f}s")
        if self.total_label is not None:
            self.total_label.setText(f"/ {duration:.2f}s")
        if self.film is not None:
            self.film.set_pos(elapsed / duration if duration else 0.0)
