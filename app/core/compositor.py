from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter

from app.core.animator import motion_offset
from app.core.animator import displace_layer
from app.core.layer import Layer


def composite_layers(layers: Sequence[Layer]) -> QImage | None:
    visible_layers = [layer for layer in layers if layer.visible and not layer.image.isNull()]
    if not visible_layers:
        return None

    width = max(layer.image.width() for layer in visible_layers)
    height = max(layer.image.height() for layer in visible_layers)
    if width <= 0 or height <= 0:
        return None

    composite = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    composite.fill(QColor(0, 0, 0, 0))

    painter = QPainter(composite)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    for layer in visible_layers:
        img = layer.image
        if layer.scale != 1.0:
            sw = max(1, int(img.width() * layer.scale))
            sh = max(1, int(img.height() * layer.scale))
            img = img.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.setOpacity(max(0.0, min(1.0, layer.opacity)))
        x = (width - img.width()) // 2 + layer.x_offset
        y = (height - img.height()) // 2 + layer.y_offset
        painter.drawImage(QRect(x, y, img.width(), img.height()), img)

    painter.end()
    return composite


def composite_animated_layers(
    layers: Sequence[Layer],
    phase: float,
    amplitude: float,
    global_intensity: float = 1.0,
    depth_focus: float = 0.5,
    loop_type: str = "Seamless Loop",
) -> QImage | None:
    visible_layers = [layer for layer in layers if layer.visible and not layer.image.isNull()]
    if not visible_layers:
        return None

    width = max(layer.image.width() for layer in visible_layers)
    height = max(layer.image.height() for layer in visible_layers)
    if width <= 0 or height <= 0:
        return None

    composite = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
    composite.fill(QColor(0, 0, 0, 0))

    painter = QPainter(composite)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

    for layer in visible_layers:
        intensity = max(0.0, layer.intensity * global_intensity)
        dx, dy, zoom = motion_offset(
            layer.motion_scale_x,
            layer.motion_scale_y,
            phase,
            amplitude=amplitude * max(0.0, layer.movement_strength),
            zoom_strength=layer.zoom_strength,
            loop_type=loop_type,
        )
        frame = displace_layer(layer, dx * intensity, dy * intensity, zoom * intensity, layer.focus_depth if layer.focus_depth is not None else depth_focus)
        if layer.scale != 1.0:
            sw = max(1, int(frame.width() * layer.scale))
            sh = max(1, int(frame.height() * layer.scale))
            frame = frame.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        painter.setOpacity(max(0.0, min(1.0, layer.opacity)))
        x = (width - frame.width()) // 2 + layer.x_offset
        y = (height - frame.height()) // 2 + layer.y_offset
        painter.drawImage(QRect(x, y, frame.width(), frame.height()), frame)

    painter.end()
    return composite
