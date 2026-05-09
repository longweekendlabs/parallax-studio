from __future__ import annotations

import math

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.core.depth import ensure_depth_map
from app.core.layer import Layer


def qimage_to_rgba(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = rgba.width()
    height = rgba.height()
    ptr = rgba.bits()
    arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
    return arr.copy()


def rgba_to_qimage(array: np.ndarray) -> QImage:
    clipped = np.clip(array, 0, 255).astype(np.uint8)
    height, width, _ = clipped.shape
    image = QImage(clipped.data, width, height, width * 4, QImage.Format.Format_RGBA8888)
    return image.copy().convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def motion_offset(
    scale_x: float,
    scale_y: float,
    phase: float,
    amplitude: float,
    zoom_strength: float = 0.0,
    loop_type: str = "Seamless Loop",
) -> tuple[float, float, float]:
    scale_x = max(0.0, min(1.0, scale_x))
    scale_y = max(0.0, min(1.0, scale_y))
    zoom_strength = max(0.0, min(1.0, zoom_strength))
    angle = phase * math.tau
    if loop_type == "Bounce":
        travel = (1.0 - abs(2.0 * phase - 1.0)) * 2.0 - 1.0
        cross = math.sin(angle) * 0.35
        zoom = travel * 0.06 * zoom_strength
        return travel * amplitude * scale_x, cross * amplitude * scale_y, zoom

    return (
        math.sin(angle) * amplitude * scale_x,
        math.cos(angle) * amplitude * scale_y,
        math.sin(angle) * 0.06 * zoom_strength,
    )


def loop_phase(elapsed_seconds: float, duration: float, speed: float, loop_type: str) -> float:
    duration = max(0.25, duration)
    speed = max(0.05, speed)
    raw = (elapsed_seconds * speed / duration) % 1.0
    return raw


def displace_layer(layer: Layer, dx: float, dy: float, zoom: float = 0.0, depth_focus: float = 0.5) -> QImage:
    source = qimage_to_rgba(layer.image)
    height, width = source.shape[:2]
    depth = ensure_depth_map(layer)
    if depth.shape != (height, width):
        depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_LINEAR)

    focus = max(0.0, min(1.0, depth_focus))
    influence = (depth.astype(np.float32) - focus) * 2.0
    yy, xx = np.indices((height, width), dtype=np.float32)

    center_x = width / 2.0
    center_y = height / 2.0
    zoom_strength = zoom * influence
    map_x = xx - dx * influence - (xx - center_x) * zoom_strength
    map_y = yy - dy * influence - (yy - center_y) * zoom_strength

    displaced = cv2.remap(
        source,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rgba_to_qimage(displaced)
