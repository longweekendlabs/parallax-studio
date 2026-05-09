import math
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QVBoxLayout, QWidget

from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_CANVAS_SURROUND,
    C_CHECKER_DARK,
    C_CHECKER_LIGHT,
)

CHECKER = 16


def _tool_button_style(active: bool = False) -> str:
    if active:
        return """
            QPushButton {
                background: rgba(61, 217, 201, 0.13);
                border: 1px solid rgba(61, 217, 201, 0.95);
                border-radius: 7px;
                color: #3DD9C9;
                font-size: 12px;
                font-weight: 600;
                padding: 0 12px;
            }
            QPushButton:hover {
                background: rgba(61, 217, 201, 0.18);
            }
        """
    return """
        QPushButton {
            background: #0D141B;
            border: 1px solid #2D3A45;
            border-radius: 7px;
            color: #D7E6F0;
            font-size: 12px;
            padding: 0 12px;
        }
        QPushButton:hover {
            border-color: #3DD9C9;
            color: #FFFFFF;
        }
    """


class CanvasToolbar(QWidget):
    overlayToggled = Signal(bool)
    fitWidthRequested = Signal()
    fitWindowRequested = Signal()
    zoomPercentChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setStyleSheet("background: #090F13; border-bottom: 1px solid #24303A;")
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 14, 0)
        row.setSpacing(8)

        title = QLabel("Preview")
        title.setStyleSheet("background: transparent; color: #D9E5EE; font-size: 13px; font-weight: 600;")
        row.addWidget(title)

        self.overlay_button = QPushButton("Paint Overlay")
        self.overlay_button.setCheckable(True)
        self.overlay_button.setChecked(True)
        self.overlay_button.setFixedHeight(30)
        self.overlay_button.setCursor(Qt.PointingHandCursor)
        self.overlay_button.setStyleSheet(_tool_button_style(True))
        self.overlay_button.toggled.connect(self._sync_overlay_style)
        self.overlay_button.toggled.connect(self.overlayToggled.emit)
        row.addWidget(self.overlay_button)

        self.fit_width_button = QPushButton("Fit Width")
        self.fit_width_button.setFixedHeight(30)
        self.fit_width_button.setCursor(Qt.PointingHandCursor)
        self.fit_width_button.setStyleSheet(_tool_button_style(False))
        self.fit_width_button.clicked.connect(self.fitWidthRequested.emit)
        row.addWidget(self.fit_width_button)

        self.fit_window_button = QPushButton("Fit Window")
        self.fit_window_button.setFixedHeight(30)
        self.fit_window_button.setCursor(Qt.PointingHandCursor)
        self.fit_window_button.setStyleSheet(_tool_button_style(False))
        self.fit_window_button.clicked.connect(self.fitWindowRequested.emit)
        row.addWidget(self.fit_window_button)

        row.addSpacing(10)
        zoom_label = QLabel("Zoom")
        zoom_label.setStyleSheet("background: transparent; color: #8A97A3; font-size: 12px;")
        row.addWidget(zoom_label)

        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(25, 250)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(190)
        self.zoom_slider.setFixedHeight(18)
        self.zoom_slider.valueChanged.connect(self._sync_zoom_value)
        self.zoom_slider.valueChanged.connect(self.zoomPercentChanged.emit)
        row.addWidget(self.zoom_slider)

        self.zoom_value = QLabel("100%")
        self.zoom_value.setFixedWidth(52)
        self.zoom_value.setAlignment(Qt.AlignCenter)
        self.zoom_value.setStyleSheet(
            """
            QLabel {
                background: #0D141B;
                border: 1px solid #2D3A45;
                border-radius: 7px;
                color: #D7E6F0;
                font-family: 'JetBrains Mono', 'SF Mono', monospace;
                font-size: 12px;
            }
            """
        )
        row.addWidget(self.zoom_value)
        row.addStretch(1)

    def _sync_overlay_style(self, checked: bool):
        self.overlay_button.setText("Paint Overlay  On" if checked else "Paint Overlay  Off")
        self.overlay_button.setStyleSheet(_tool_button_style(checked))
        self.overlay_button.update()

    def _sync_zoom_value(self, percent: int):
        self.zoom_value.setText(f"{percent}%")

    def set_zoom_percent(self, percent: int):
        self.zoom_slider.blockSignals(True)
        self.zoom_slider.setValue(percent)
        self.zoom_slider.blockSignals(False)
        self.zoom_value.setText(f"{percent}%")

    def set_overlay_enabled(self, enabled: bool):
        self.overlay_button.blockSignals(True)
        self.overlay_button.setChecked(enabled)
        self.overlay_button.blockSignals(False)
        self._sync_overlay_style(enabled)


_HANDLE = 7.0   # corner handle half-size in screen px
_BORDER = 12.0  # drag-border thickness in screen px


class PreviewStage(QWidget):
    depthPaintRequested = Signal(int, int, bool)
    layerMoveRequested = Signal(int, int)
    layerResizeRequested = Signal(float)  # absolute new scale value
    layerTransformStarted = Signal()
    layerTransformFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.composite_image: QImage | None = None
        self.depth_overlay: QImage | None = None
        self.selected_layer_name: str = ""
        self.zoom_percent = 100
        self.zoom_mode = "fit_window"
        self.paint_overlay_enabled = True
        # selection bounds set by main_window: (x, y, w, h) in composite pixels
        self.selected_bounds: tuple[int, int, int, int] | None = None
        self._selected_layer_locked: bool = False
        self._current_layer_scale: float = 1.0
        self._brush_size: int = 28
        self._brush_opacity: float = 0.75
        self._hover_pos: QPointF | None = None
        # drag state: 'paint' | 'move' | 'resize' | None
        self._drag_intent: str | None = None
        self._paint_active = False
        self._drag_origin: QPointF | None = None
        self._drag_emitted_x: int = 0
        self._drag_emitted_y: int = 0
        self._resize_center: QPointF = QPointF()
        self._resize_initial_dist: float = 1.0
        self._resize_initial_scale: float = 1.0
        self.setMinimumSize(620, 520)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_composite(self, image: QImage | None, selected_layer_name: str = ""):
        self.composite_image = image
        self.selected_layer_name = selected_layer_name
        self.update()

    def set_depth_overlay(self, image: QImage | None):
        self.depth_overlay = image
        self.update()

    def set_zoom_percent(self, percent: int):
        self.zoom_percent = max(25, min(250, int(percent)))
        self.update()

    def set_zoom_mode(self, mode: str):
        self.zoom_mode = mode
        self.update()

    def set_paint_overlay_enabled(self, enabled: bool):
        self.paint_overlay_enabled = enabled
        self.update()

    def set_selected_layer_bounds(
        self,
        bounds: tuple[int, int, int, int] | None,
        layer_scale: float = 1.0,
        locked: bool = False,
    ):
        self.selected_bounds = bounds
        self._current_layer_scale = layer_scale
        self._selected_layer_locked = locked
        self.update()

    def set_brush_preview(self, size: int, opacity: float):
        self._brush_size = max(1, int(size))
        self._brush_opacity = max(0.0, min(1.0, float(opacity)))
        self.update()

    # ── geometry helpers ──────────────────────────────────────────────────

    def _composite_to_screen(self, cx: float, cy: float) -> QPointF:
        target = self._composite_target_rect()
        if target is None or self.composite_image is None:
            return QPointF(0.0, 0.0)
        cw = max(1, self.composite_image.width())
        ch = max(1, self.composite_image.height())
        return QPointF(
            target.x() + cx / cw * target.width(),
            target.y() + cy / ch * target.height(),
        )

    def _selection_screen_rect(self) -> QRectF | None:
        if self.selected_bounds is None or self.composite_image is None:
            return None
        x, y, w, h = self.selected_bounds
        tl = self._composite_to_screen(x, y)
        br = self._composite_to_screen(x + w, y + h)
        if br.x() <= tl.x() + 2 or br.y() <= tl.y() + 2:
            return None
        return QRectF(tl, br)

    def _corner_rects(self) -> list[QRectF]:
        r = self._selection_screen_rect()
        if r is None:
            return []
        h = _HANDLE
        return [QRectF(c.x() - h, c.y() - h, h * 2, h * 2)
                for c in [r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight()]]

    def _hit_corner(self, pos: QPointF) -> int:
        if self._selected_layer_locked:
            return -1
        for i, rect in enumerate(self._corner_rects()):
            if rect.adjusted(-4, -4, 4, 4).contains(pos):
                return i
        return -1

    def _hit_border(self, pos: QPointF) -> bool:
        if self._selected_layer_locked:
            return False
        r = self._selection_screen_rect()
        if r is None:
            return False
        outer = r.adjusted(-_BORDER, -_BORDER, _BORDER, _BORDER)
        inner = r.adjusted(_BORDER, _BORDER, -_BORDER, -_BORDER)
        return outer.contains(pos) and not inner.contains(pos)

    def _update_hover_cursor(self, pos: QPointF):
        self._hover_pos = pos
        if self._selected_layer_locked and self._event_to_composite_xy(pos) is not None and self.selected_bounds is not None:
            self.setCursor(Qt.CursorShape.BlankCursor)
        elif self._hit_corner(pos) >= 0:
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self._hit_border(pos):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        elif self._event_to_composite_xy(pos) is not None and self.selected_bounds is not None:
            self.setCursor(Qt.CursorShape.BlankCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()

    def _display_scale(self) -> float:
        if self.composite_image is None or self.composite_image.isNull():
            return 1.0
        art = self._art_rect()
        iw, ih = self.composite_image.width(), self.composite_image.height()
        if iw <= 0 or ih <= 0:
            return 1.0
        zoom = max(0.25, self.zoom_percent / 100.0)
        if self.zoom_mode == "fit_width":
            return (art.width() / iw) * zoom
        return min(art.width() / iw, art.height() / ih) * zoom

    def _outer_rect(self) -> QRect:
        return self.rect().adjusted(0, 0, 0, 0)

    def _stage_rect(self) -> QRect:
        outer = self._outer_rect().adjusted(10, 18, -10, -18)
        return outer

    def _art_rect(self) -> QRect:
        return self._stage_rect().adjusted(8, 8, -8, -8)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(C_CANVAS_SURROUND))

        stage = self._stage_rect()
        p.setBrush(QColor("#0A0F13"))
        p.setPen(QPen(QColor(C_BORDER), 1))
        p.drawRoundedRect(QRectF(stage), 8, 8)

        inner = stage.adjusted(7, 7, -7, -7)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(inner), 6, 6)
        art = self._art_rect()
        if self.composite_image is None:
            p.save()
            p.setClipPath(clip)
            self._paint_checker(p, inner)
            p.restore()
            self._paint_art(p, art)
        else:
            p.save()
            p.setClipPath(clip)
            p.fillRect(inner, QColor("#05080B"))
            p.restore()
            self._paint_composite(p, art)

        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(C_BORDER), 1.2))
        p.drawRoundedRect(QRectF(stage).adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)

        if self.composite_image is not None and self.selected_bounds is not None:
            self._paint_selection_overlay(p)
        self._paint_brush_cursor(p)

    def _paint_selection_overlay(self, p: QPainter):
        if self._selected_layer_locked:
            return
        r = self._selection_screen_rect()
        if r is None:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        # Bounding box: dashed cyan
        pen = QPen(QColor(C_ACCENT), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([6.0, 3.0])
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(r)
        # Corner handles: filled dark squares with cyan border
        p.setPen(QPen(QColor(C_ACCENT), 1.5))
        p.setBrush(QColor("#0B1014"))
        for handle in self._corner_rects():
            p.drawRect(handle)
        p.restore()

    def _paint_brush_cursor(self, p: QPainter):
        if (
            self._hover_pos is None
            or self._drag_intent in {"move", "resize"}
            or self.selected_bounds is None
            or self._event_to_composite_xy(self._hover_pos) is None
        ):
            return
        radius = max(4.0, (self._brush_size * self._current_layer_scale * self._display_scale()) / 2.0)
        radius = min(radius, 180.0)
        alpha = int(90 + self._brush_opacity * 135)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setBrush(QColor(255, 255, 255, int(18 + self._brush_opacity * 28)))
        p.setPen(QPen(QColor(255, 255, 255, alpha), 1.5))
        p.drawEllipse(self._hover_pos, radius, radius)
        p.setPen(QPen(QColor(0, 0, 0, 160), 1.0))
        p.drawEllipse(self._hover_pos, radius + 1.5, radius + 1.5)
        p.setPen(QPen(QColor(255, 255, 255, alpha), 1.0))
        p.drawLine(QPointF(self._hover_pos.x() - 4, self._hover_pos.y()), QPointF(self._hover_pos.x() + 4, self._hover_pos.y()))
        p.drawLine(QPointF(self._hover_pos.x(), self._hover_pos.y() - 4), QPointF(self._hover_pos.x(), self._hover_pos.y() + 4))
        p.restore()

    def _paint_composite(self, p: QPainter, r: QRect):
        if self.composite_image is None or self.composite_image.isNull():
            return

        target = self._composite_target_rect()
        if target is None:
            return

        p.save()
        art_path = QPainterPath()
        art_path.addRoundedRect(QRectF(r), 6, 6)
        p.setClipPath(art_path)
        path = QPainterPath()
        path.addRoundedRect(QRectF(target), 2, 2)
        p.setClipPath(path, Qt.ClipOperation.IntersectClip)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(target, self.composite_image)
        if self.paint_overlay_enabled and self.depth_overlay is not None and not self.depth_overlay.isNull():
            p.setOpacity(0.62)
            p.drawImage(target, self.depth_overlay)
            p.setOpacity(1.0)
        p.restore()

        p.setPen(QPen(QColor(255, 255, 255, 35), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(target).adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)

    def _composite_target_rect(self) -> QRect | None:
        if self.composite_image is None or self.composite_image.isNull():
            return None
        art = self._art_rect()
        base = art.adjusted(0, 0, 0, 0)
        if base.width() <= 0 or base.height() <= 0:
            return None
        image_w = self.composite_image.width()
        image_h = self.composite_image.height()
        if image_w <= 0 or image_h <= 0:
            return None
        zoom = max(0.25, self.zoom_percent / 100.0)
        if self.zoom_mode == "fit_width":
            scale = (base.width() / image_w) * zoom
        else:
            scale = min(base.width() / image_w, base.height() / image_h) * zoom
        image_size_w = max(1, int(image_w * scale))
        image_size_h = max(1, int(image_h * scale))
        return QRect(
            art.x() + (art.width() - image_size_w) // 2,
            art.y() + (art.height() - image_size_h) // 2,
            image_size_w,
            image_size_h,
        )

    def _event_to_composite_xy(self, position) -> tuple[int, int] | None:
        target = self._composite_target_rect()
        if target is None or not target.contains(position.toPoint()):
            return None
        if self.composite_image is None:
            return None
        x = int((position.x() - target.x()) / target.width() * self.composite_image.width())
        y = int((position.y() - target.y()) / target.height() * self.composite_image.height())
        return (
            max(0, min(self.composite_image.width() - 1, x)),
            max(0, min(self.composite_image.height() - 1, y)),
        )

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pos = event.position()
        if not self._selected_layer_locked:
            # Corner handle → resize
            corner = self._hit_corner(pos)
            if corner >= 0:
                r = self._selection_screen_rect()
                if r is not None:
                    self._drag_intent = 'resize'
                    self.layerTransformStarted.emit()
                    self._resize_center = r.center()
                    dist = math.sqrt((pos.x() - r.center().x()) ** 2 + (pos.y() - r.center().y()) ** 2)
                    self._resize_initial_dist = max(1.0, dist)
                    self._resize_initial_scale = self._current_layer_scale
                    return
            # Bounding-box border → move
            if self._hit_border(pos):
                self._drag_intent = 'move'
                self.layerTransformStarted.emit()
                self._drag_origin = pos
                self._drag_emitted_x = 0
                self._drag_emitted_y = 0
                return
        # Otherwise → paint depth
        self._drag_intent = 'paint'
        xy = self._event_to_composite_xy(pos)
        if xy is None:
            self._drag_intent = None
            return
        self._paint_active = True
        self.depthPaintRequested.emit(xy[0], xy[1], True)

    def mouseMoveEvent(self, event):
        pos = event.position()
        self._hover_pos = pos
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            # Hover — update cursor
            self._update_hover_cursor(pos)
            return
        if self._drag_intent == 'move' and self._drag_origin is not None:
            ds = self._display_scale()
            if ds > 0:
                total_dx = int((pos.x() - self._drag_origin.x()) / ds)
                total_dy = int((pos.y() - self._drag_origin.y()) / ds)
                dx = total_dx - self._drag_emitted_x
                dy = total_dy - self._drag_emitted_y
                if dx != 0 or dy != 0:
                    self._drag_emitted_x = total_dx
                    self._drag_emitted_y = total_dy
                    self.layerMoveRequested.emit(dx, dy)
        elif self._drag_intent == 'resize':
            new_dist = math.sqrt((pos.x() - self._resize_center.x()) ** 2 +
                                 (pos.y() - self._resize_center.y()) ** 2)
            if self._resize_initial_dist > 1.0:
                new_scale = self._resize_initial_scale * new_dist / self._resize_initial_dist
                self.layerResizeRequested.emit(new_scale)
        elif self._drag_intent == 'paint' and self._paint_active:
            xy = self._event_to_composite_xy(pos)
            if xy is not None:
                self.depthPaintRequested.emit(xy[0], xy[1], False)

    def mouseReleaseEvent(self, event):
        if self._drag_intent in {"move", "resize"}:
            self.layerTransformFinished.emit()
        self._drag_intent = None
        self._paint_active = False
        self._drag_origin = None
        self.update()

    def leaveEvent(self, event):
        self._hover_pos = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.update()
        super().leaveEvent(event)

    def _paint_checker(self, p: QPainter, rect: QRect):
        for row in range(rect.height() // CHECKER + 2):
            for col in range(rect.width() // CHECKER + 2):
                color = C_CHECKER_LIGHT if (row + col) % 2 == 0 else C_CHECKER_DARK
                p.fillRect(rect.x() + col * CHECKER, rect.y() + row * CHECKER, CHECKER, CHECKER, QColor(color))

    def _paint_art(self, p: QPainter, r: QRect):
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), 2, 2)
        p.save()
        p.setClipPath(path)

        sky = QLinearGradient(QPointF(r.x(), r.y()), QPointF(r.x(), r.bottom()))
        sky.setColorAt(0, QColor("#263957"))
        sky.setColorAt(0.2, QColor("#E38B6C"))
        sky.setColorAt(0.42, QColor("#666889"))
        sky.setColorAt(0.72, QColor("#283852"))
        sky.setColorAt(1, QColor("#0F1927"))
        p.fillRect(r, sky)

        sun = QRadialGradient(QPointF(r.center().x(), r.y() + r.height() * 0.38), r.width() * 0.34)
        sun.setColorAt(0, QColor("#FFC27A99"))
        sun.setColorAt(0.48, QColor("#E86C5B33"))
        sun.setColorAt(1, QColor("#00000000"))
        p.fillRect(r, sun)

        self._paint_mountain(p, r, 0.56, "#D7E0EA", "#40506C")
        self._paint_mountain(p, r, 0.66, "#31405A", "#172235", offset=-90)
        self._paint_mountain(p, r, 0.78, "#213047", "#111B2A", offset=80)
        self._paint_city(p, r)
        self._paint_character(p, r)
        self._paint_branches(p, r)
        self._paint_petals(p, r)

        vignette = QRadialGradient(QPointF(r.center()), r.width() * 0.72)
        vignette.setColorAt(0, QColor("#00000000"))
        vignette.setColorAt(0.72, QColor("#00000011"))
        vignette.setColorAt(1, QColor("#00000088"))
        p.fillRect(r, vignette)

        p.restore()
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(r).adjusted(0.5, 0.5, -0.5, -0.5), 2, 2)

    def _paint_mountain(self, p, r, base_y, snow, shade, offset=0):
        x0 = r.x() + offset
        peak_x = r.x() + r.width() * 0.62 + offset * 0.2
        peak_y = r.y() + r.height() * 0.12
        base = r.y() + r.height() * base_y
        path = QPainterPath()
        path.moveTo(x0, base)
        path.lineTo(peak_x, peak_y)
        path.lineTo(r.right() + 120, base + r.height() * 0.12)
        path.lineTo(r.right() + 120, r.bottom())
        path.lineTo(x0, r.bottom())
        path.closeSubpath()
        grad = QLinearGradient(QPointF(peak_x, peak_y), QPointF(peak_x, r.bottom()))
        grad.setColorAt(0, QColor(snow))
        grad.setColorAt(0.28, QColor(shade))
        grad.setColorAt(1, QColor("#0C1119"))
        p.setBrush(grad)
        p.setPen(Qt.NoPen)
        p.drawPath(path)

    def _paint_city(self, p, r):
        p.setPen(Qt.NoPen)
        for i, frac in enumerate([0.1, 0.16, 0.23, 0.69, 0.76, 0.84, 0.91]):
            x = r.x() + r.width() * frac
            y = r.y() + r.height() * (0.62 + (i % 3) * 0.04)
            w = r.width() * 0.09
            h = r.height() * 0.2
            p.setBrush(QColor("#121923CC"))
            p.drawRect(QRectF(x, y, w, h))
            p.drawRect(QRectF(x - w * 0.08, y + h * 0.18, w * 1.16, h * 0.12))
            p.drawRect(QRectF(x + w * 0.42, y - h * 0.26, w * 0.16, h * 0.26))
            p.drawRect(QRectF(x + w * 0.22, y + h * 0.34, w * 0.56, h * 0.08))
            p.setBrush(QColor("#F8A85D99"))
            for n in range(3):
                p.drawEllipse(QRectF(x + w * (0.22 + n * 0.22), y + h * 0.55, 3, 3))

    def _paint_character(self, p, r):
        scale = min(r.width(), r.height())
        cx = r.x() + r.width() * 0.38
        ground = r.y() + r.height() * 0.92

        cliff = QPainterPath()
        cliff.moveTo(r.x() + r.width() * 0.26, ground)
        cliff.lineTo(r.x() + r.width() * 0.46, ground - scale * 0.02)
        cliff.lineTo(r.x() + r.width() * 0.52, r.bottom())
        cliff.lineTo(r.x() + r.width() * 0.18, r.bottom())
        cliff.closeSubpath()
        p.setBrush(QColor("#11131A"))
        p.setPen(Qt.NoPen)
        p.drawPath(cliff)

        head = QRectF(cx - scale * 0.025, ground - scale * 0.53, scale * 0.05, scale * 0.06)
        p.setBrush(QColor("#0B0B10"))
        p.drawEllipse(head)

        body = QPainterPath()
        body.moveTo(cx, ground - scale * 0.47)
        body.cubicTo(cx - scale * 0.07, ground - scale * 0.35, cx - scale * 0.08, ground - scale * 0.18, cx - scale * 0.04, ground - scale * 0.08)
        body.lineTo(cx + scale * 0.085, ground - scale * 0.08)
        body.cubicTo(cx + scale * 0.04, ground - scale * 0.25, cx + scale * 0.05, ground - scale * 0.36, cx, ground - scale * 0.47)
        body.closeSubpath()
        p.setBrush(QColor("#101018"))
        p.drawPath(body)

        p.setPen(QPen(QColor("#0B0B10"), scale * 0.012))
        for dx, dy in [(-0.17, -0.4), (-0.13, -0.3), (0.08, -0.36), (0.16, -0.28), (-0.22, -0.22)]:
            p.drawLine(QPointF(cx, ground - scale * 0.49), QPointF(cx + scale * dx, ground + scale * dy))

        p.setPen(QPen(QColor("#9D1827"), scale * 0.012))
        p.drawLine(QPointF(cx - scale * 0.05, ground - scale * 0.28), QPointF(cx + scale * 0.19, ground - scale * 0.16))
        p.drawLine(QPointF(cx + scale * 0.04, ground - scale * 0.29), QPointF(cx - scale * 0.18, ground - scale * 0.1))

        p.setPen(QPen(QColor("#C3C8CD"), scale * 0.006))
        p.drawLine(QPointF(cx + scale * 0.08, ground - scale * 0.32), QPointF(cx + scale * 0.14, ground - scale * 0.06))

    def _paint_branches(self, p, r):
        p.setPen(QPen(QColor("#130B0D"), max(4, r.width() * 0.006)))
        p.drawLine(QPointF(r.x(), r.y() + r.height() * 0.1), QPointF(r.x() + r.width() * 0.25, r.y() + r.height() * 0.03))
        p.drawLine(QPointF(r.x() + r.width() * 0.06, r.y()), QPointF(r.x() + r.width() * 0.2, r.y() + r.height() * 0.24))

    def _paint_petals(self, p, r):
        p.setPen(Qt.NoPen)
        colors = ["#F59AAF", "#D85F78", "#FFB0BE"]
        for i in range(120):
            x = r.x() + (i * 97 % r.width())
            y = r.y() + (i * 53 % r.height())
            size = 3 + (i % 5)
            p.setBrush(QColor(colors[i % len(colors)] + "AA"))
            p.drawEllipse(QRectF(x, y, size, size * 0.7))


class CanvasPanel(QWidget):
    imageFilesDropped = Signal(list)
    unsupportedFilesDropped = Signal(list)
    depthPaintRequested = Signal(int, int, bool)
    layerMoveRequested = Signal(int, int)
    layerResizeRequested = Signal(float)
    layerTransformStarted = Signal()
    layerTransformFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {C_CANVAS_SURROUND};")
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.toolbar = CanvasToolbar(self)
        self.stage = PreviewStage(self)
        layout.addWidget(self.toolbar)
        layout.addWidget(self.stage, 1)
        self.stage.depthPaintRequested.connect(self.depthPaintRequested.emit)
        self.stage.layerMoveRequested.connect(self.layerMoveRequested.emit)
        self.stage.layerResizeRequested.connect(self.layerResizeRequested.emit)
        self.stage.layerTransformStarted.connect(self.layerTransformStarted.emit)
        self.stage.layerTransformFinished.connect(self.layerTransformFinished.emit)
        self.toolbar.overlayToggled.connect(self.stage.set_paint_overlay_enabled)
        self.toolbar.fitWidthRequested.connect(lambda: self._set_fit_mode("fit_width"))
        self.toolbar.fitWindowRequested.connect(lambda: self._set_fit_mode("fit_window"))
        self.toolbar.zoomPercentChanged.connect(self.stage.set_zoom_percent)
        self.set_zoom_percent(self.toolbar.zoom_slider.value())
        self.set_zoom_mode("fit_window")
        self.set_paint_overlay_enabled(True)

    def set_composite(self, image: QImage | None, selected_layer_name: str = ""):
        self.stage.set_composite(image, selected_layer_name)

    def set_depth_overlay(self, image: QImage | None):
        self.stage.set_depth_overlay(image)

    def set_zoom_percent(self, percent: int):
        self.toolbar.set_zoom_percent(percent)
        self.stage.set_zoom_percent(percent)

    def set_selected_layer_bounds(
        self,
        bounds: tuple[int, int, int, int] | None,
        layer_scale: float = 1.0,
        locked: bool = False,
    ):
        self.stage.set_selected_layer_bounds(bounds, layer_scale, locked)

    def set_brush_preview(self, size: int, opacity: float):
        self.stage.set_brush_preview(size, opacity)

    def set_zoom_mode(self, mode: str):
        self.stage.set_zoom_mode(mode)
        self.toolbar.fit_width_button.setStyleSheet(_tool_button_style(mode == "fit_width"))
        self.toolbar.fit_window_button.setStyleSheet(_tool_button_style(mode == "fit_window"))

    def set_paint_overlay_enabled(self, enabled: bool):
        self.toolbar.set_overlay_enabled(enabled)
        self.stage.set_paint_overlay_enabled(enabled)

    def _set_fit_mode(self, mode: str):
        self.set_zoom_mode(mode)
        self.set_zoom_percent(100)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        files = [
            Path(url.toLocalFile())
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        image_files = [
            str(path)
            for path in files
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ]
        unsupported = [str(path) for path in files if str(path) not in image_files]

        if image_files:
            self.imageFilesDropped.emit(image_files)
        if unsupported:
            self.unsupportedFilesDropped.emit(unsupported)

        event.acceptProposedAction()
