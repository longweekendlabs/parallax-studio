from __future__ import annotations

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.core.layer import Layer

MAX_UNDO = 20

# How many feather passes relax_paint_folds may spend making a stroke safe to
# displace. Each pass costs about 180ms at 12MP, and only the most extreme
# slider settings ever need more than one.
MAX_FOLD_PASSES = 4

# The fraction of the base amplitude a stroke has to survive. depth_model uses
# 0.4875 for model output, but the motion controls emit global intensity 1.0 and
# a layer intensity of 1.0 by default, so a painted edge that only clears 0.4875
# still folds at the settings the app ships with, measured at a jacobian of
# -0.19 where anything below zero is the grid running backwards. Painted depth
# is checked against the full 1.0.
PAINT_FOLD_INTENSITY = 1.0


def touch_depth(layer: Layer) -> None:
    """Mark the layer's depth map as changed.

    Every function that writes depth must call this. The preview keeps a
    downscaled proxy of each layer and used to decide whether to rebuild it by
    comparing array identity, which a brush stroke never changes because it
    writes into the array in place. The result was that painting had no effect
    on the preview at all until some other edit happened to rebind the array.
    """
    layer.depth_revision += 1


def ensure_depth_map(layer: Layer) -> np.ndarray:
    if layer.depth_map is None:
        layer.depth_map = np.full((layer.image.height(), layer.image.width()), 0.5, dtype=np.float32)
        touch_depth(layer)
    return layer.depth_map


def push_depth_undo(layer: Layer) -> None:
    depth = ensure_depth_map(layer)
    layer.depth_undo_stack.append((depth.copy(), layer.depth_inverted))
    if len(layer.depth_undo_stack) > MAX_UNDO:
        layer.depth_undo_stack.pop(0)
    layer.depth_redo_stack.clear()


def undo_depth(layer: Layer) -> bool:
    if not layer.depth_undo_stack:
        return False
    current = ensure_depth_map(layer)
    layer.depth_redo_stack.append((current.copy(), layer.depth_inverted))
    layer.depth_map, layer.depth_inverted = layer.depth_undo_stack.pop()
    touch_depth(layer)
    return True


def redo_depth(layer: Layer) -> bool:
    if not layer.depth_redo_stack:
        return False
    current = ensure_depth_map(layer)
    layer.depth_undo_stack.append((current.copy(), layer.depth_inverted))
    layer.depth_map, layer.depth_inverted = layer.depth_redo_stack.pop()
    touch_depth(layer)
    return True


def clear_depth(layer: Layer) -> None:
    push_depth_undo(layer)
    layer.depth_map = np.full((layer.image.height(), layer.image.width()), 0.5, dtype=np.float32)
    layer.depth_inverted = False
    touch_depth(layer)


def invert_depth(layer: Layer) -> None:
    push_depth_undo(layer)
    layer.depth_map = 1.0 - ensure_depth_map(layer)
    layer.depth_inverted = not layer.depth_inverted
    touch_depth(layer)


def blur_depth(layer: Layer, radius: int = 5) -> None:
    push_depth_undo(layer)
    kernel = max(3, radius | 1)
    layer.depth_map = cv2.GaussianBlur(ensure_depth_map(layer), (kernel, kernel), 0)
    touch_depth(layer)


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
    layer.depth_inverted = False
    touch_depth(layer)


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
    touch_depth(layer)


def relax_paint_folds(layer: Layer) -> bool:
    """Feather any brushed edge steep enough to tear when the depth map moves.

    Displacement is ``influence * amplitude``, so the sampling grid stops being
    monotonic and the picture folds back over itself wherever the depth gradient
    passes ``1 / (2 * amplitude * intensity)``. The brush reaches that easily:
    measured across the slider range on a 4000px photo, only the softest and
    widest strokes stayed under the limit, and every other combination tore.
    Hardness at 100% tore by two orders of magnitude.

    This is the same gradient-weighted feather ``soften_for_parallax`` applies
    to model output, at the same limit, so painting on top of a generated map
    leaves it alone rather than blurring it a second time. It runs once when a
    stroke ends, not per stamp, and it does nothing where the map is already
    smooth enough, which makes repeating it harmless.

    Returns True if the map was changed.
    """
    from app.core.depth_model import (
        DESIGN_AMPLITUDE,
        FOLD_MARGIN,
        PARALLAX_FEATHER,
    )

    depth = ensure_depth_map(layer)
    height, width = depth.shape[:2]
    long_edge = max(width, height)
    amplitude = max(60.0, long_edge * DESIGN_AMPLITUDE)
    safe_grad = FOLD_MARGIN / (2.0 * amplitude * PAINT_FOLD_INTENSITY)
    sigma = max(1.0, long_edge * PARALLAX_FEATHER)

    # Everything is measured and blurred on a proxy and upsampled: at 12MP a
    # full-resolution blur this wide costs seconds, and both the feather and its
    # weight map are smooth by construction.
    scale = min(1.0, 512.0 / long_edge)
    small_sigma = max(0.6, sigma * scale)
    changed = False

    # One feather of this width clears everything the sliders can produce except
    # a full-height step painted with a hard brush, where it takes the fold from
    # about 80 pixels of backwards grid down to a fraction of one. Repeating
    # closes that last case; each pass costs nothing once the map is safe,
    # because the gradient check below exits first.
    for _ in range(MAX_FOLD_PASSES):
        small = (
            cv2.resize(depth, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            if scale < 1.0
            else depth
        )
        grad = cv2.magnitude(
            cv2.Sobel(small, cv2.CV_32F, 1, 0, ksize=3),
            cv2.Sobel(small, cv2.CV_32F, 0, 1, ksize=3),
        ) * (scale / 8.0)
        if float(grad.max()) <= safe_grad:
            break

        small_blur = cv2.GaussianBlur(small, (0, 0), sigmaX=small_sigma)

        weight = np.clip(grad / safe_grad, 0.0, 1.0)
        # The band over the limit is only a few pixels wide, so smoothing it
        # directly would flatten its own peak and leave most of the step
        # unfeathered. Grow it to cover the feather first, then soften its edges.
        radius = max(1, int(round(small_sigma * 2.0)))
        weight = cv2.dilate(weight, np.ones((radius * 2 + 1,) * 2, np.uint8))
        weight = cv2.GaussianBlur(weight, (0, 0), sigmaX=max(0.6, small_sigma * 0.5))

        if scale < 1.0:
            small_blur = cv2.resize(small_blur, (width, height), interpolation=cv2.INTER_LINEAR)
            weight = cv2.resize(weight, (width, height), interpolation=cv2.INTER_LINEAR)

        depth = np.clip(depth * (1.0 - weight) + small_blur * weight, 0.0, 1.0).astype(np.float32)
        changed = True

    if changed:
        layer.depth_map = depth
        touch_depth(layer)
    return changed


def depth_to_qimage(depth: np.ndarray | None) -> QImage | None:
    if depth is None:
        return None
    clipped = np.clip(depth, 0.0, 1.0)
    height, width = clipped.shape

    # Depth as colour, not brightness. Greyscale is what Depthy uses, but its
    # overlay only ever has to show hand-painted strokes, which are drawn with
    # deliberate contrast. A generated depth map puts a whole figure inside a
    # fraction of the range -- measured, an entire body spanning 85 of 255 grey
    # levels once the alpha blend is applied -- and that reads as one flat wash
    # with no parts visible in it. The eye resolves far more steps in hue than
    # in lightness, so the same data becomes legible as a ramp.
    #
    # Blue is far, cyan/green is the neutral plane, red is near, which matches
    # the direction the motion controls talk about.
    grey = (clipped * 255.0).astype(np.uint8)
    coloured = cv2.applyColorMap(grey, cv2.COLORMAP_TURBO)  # BGR
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = coloured[:, :, 2]
    rgba[:, :, 1] = coloured[:, :, 1]
    rgba[:, :, 2] = coloured[:, :, 0]
    rgba[:, :, 3] = 150
    image = QImage(rgba.data, width, height, width * 4, QImage.Format.Format_RGBA8888)
    return image.copy()
