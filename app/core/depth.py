from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.core.layer import Layer

MAX_UNDO = 20


def ensure_depth_map(layer: Layer) -> np.ndarray:
    if layer.depth_map is None:
        layer.depth_map = np.full((layer.image.height(), layer.image.width()), 0.5, dtype=np.float32)
    return layer.depth_map


def push_depth_undo(layer: Layer) -> None:
    depth = ensure_depth_map(layer)
    layer.depth_undo_stack.append(depth.copy())
    if len(layer.depth_undo_stack) > MAX_UNDO:
        layer.depth_undo_stack.pop(0)
    layer.depth_redo_stack.clear()


def undo_depth(layer: Layer) -> bool:
    if not layer.depth_undo_stack:
        return False
    current = ensure_depth_map(layer)
    layer.depth_redo_stack.append(current.copy())
    layer.depth_map = layer.depth_undo_stack.pop()
    return True


def redo_depth(layer: Layer) -> bool:
    if not layer.depth_redo_stack:
        return False
    current = ensure_depth_map(layer)
    layer.depth_undo_stack.append(current.copy())
    layer.depth_map = layer.depth_redo_stack.pop()
    return True


def clear_depth(layer: Layer) -> None:
    push_depth_undo(layer)
    layer.depth_map = np.full((layer.image.height(), layer.image.width()), 0.5, dtype=np.float32)


def invert_depth(layer: Layer) -> None:
    push_depth_undo(layer)
    layer.depth_map = 1.0 - ensure_depth_map(layer)


def blur_depth(layer: Layer, radius: int = 5) -> None:
    push_depth_undo(layer)
    kernel = max(3, radius | 1)
    layer.depth_map = cv2.GaussianBlur(ensure_depth_map(layer), (kernel, kernel), 0)


def auto_depth(layer: Layer) -> None:
    """Create a lightweight starter depth map from image luminance and center bias."""
    image = layer.image.convertToFormat(QImage.Format.Format_RGBA8888)
    height, width = image.height(), image.width()
    rgba = np.frombuffer(image.bits(), dtype=np.uint8).reshape((height, width, 4)).copy()
    rgb = rgba[:, :, :3].astype(np.float32) / 255.0
    alpha = rgba[:, :, 3].astype(np.float32) / 255.0

    luminance = rgb[:, :, 0] * 0.2126 + rgb[:, :, 1] * 0.7152 + rgb[:, :, 2] * 0.0722
    luminance = cv2.GaussianBlur(luminance, (0, 0), sigmaX=max(2.0, min(width, height) / 180.0))

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cx = (width - 1) / 2.0
    cy = (height - 1) / 2.0
    rx = max(1.0, width * 0.55)
    ry = max(1.0, height * 0.55)
    center_bias = 1.0 - np.clip(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2, 0.0, 1.0)

    edges = cv2.Laplacian(luminance, cv2.CV_32F)
    edges = cv2.GaussianBlur(np.abs(edges), (0, 0), sigmaX=2.0)
    edge_max = float(edges.max())
    if edge_max > 0:
        edges /= edge_max

    depth = 0.5 + (luminance - 0.5) * 0.22 + (center_bias - 0.5) * 0.20 + edges * 0.06
    depth = depth * alpha + 0.5 * (1.0 - alpha)
    depth = cv2.GaussianBlur(depth, (0, 0), sigmaX=max(1.5, min(width, height) / 220.0))

    push_depth_undo(layer)
    layer.depth_map = np.clip(depth, 0.0, 1.0).astype(np.float32)


def paint_depth(
    layer: Layer,
    x: int,
    y: int,
    size: int,
    value: float,
    hardness: float,
    opacity: float,
) -> None:
    depth = ensure_depth_map(layer)
    radius = max(1, int(size / 2))
    x0 = max(0, x - radius)
    y0 = max(0, y - radius)
    x1 = min(depth.shape[1], x + radius + 1)
    y1 = min(depth.shape[0], y + radius + 1)
    if x0 >= x1 or y0 >= y1:
        return

    hardness = float(np.clip(hardness, 0.0, 1.0))
    opacity = float(np.clip(opacity, 0.0, 1.0))
    yy, xx = np.ogrid[y0:y1, x0:x1]
    dist = np.sqrt((xx - x) ** 2 + (yy - y) ** 2).astype(np.float32)

    hard_radius = float(radius * min(hardness, 0.99))
    soft_width = max(1.0, float(radius - hard_radius))
    # Hard zone: full opacity; soft zone: linear falloff to 0 (matches Depthy gradient model)
    soft_alpha = np.clip(1.0 - (dist - hard_radius) / soft_width, 0.0, 1.0)
    alpha = (np.where(dist <= hard_radius, 1.0, soft_alpha) * opacity).astype(np.float32)

    # Blend directly toward target value — never pull toward 0.5
    region = depth[y0:y1, x0:x1]
    region[:] = region * (1.0 - alpha) + value * alpha
    np.clip(depth, 0.0, 1.0, out=depth)


def depth_to_qimage(depth: np.ndarray | None) -> QImage | None:
    if depth is None:
        return None
    clipped = np.clip(depth, 0.0, 1.0)
    height, width = clipped.shape

    # Show the depth field itself, the way Depthy does: it renders the depth map
    # as a near-opaque greyscale sprite (previewSprite.alpha = depthPreview,
    # which it sets to 0.75-1.0). Tinting by distance from neutral - what this
    # used to do - collapses the falloff, so a soft edge and a hard edge look
    # identical and each stroke just overrides the last. Painting brightness
    # directly makes hardness, strength and overlap readable as shading.
    grey = (clipped * 255.0).astype(np.uint8)
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = grey
    rgba[:, :, 1] = grey
    rgba[:, :, 2] = grey
    rgba[:, :, 3] = 185
    image = QImage(rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888)
    return image.copy()
