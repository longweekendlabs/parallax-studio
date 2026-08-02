from __future__ import annotations

import math
import threading
from collections import OrderedDict

import cv2
import numpy as np
from PySide6.QtGui import QImage

from app.core.depth import ensure_depth_map
from app.core.layer import Layer

# Preview redraws the same layers dozens of times a second, so the per-frame
# work is kept to arithmetic on pre-allocated buffers. Read-only coordinate
# grids are shared; scratch buffers are thread-local because export renders on
# a worker thread while the preview renders on the GUI thread.
_GRID_LOCK = threading.Lock()
_GRIDS: OrderedDict[tuple[int, int], tuple[np.ndarray, ...]] = OrderedDict()
_RGBA_CACHE: OrderedDict[int, np.ndarray] = OrderedDict()
_SCRATCH = threading.local()
_MAX_CACHED = 4


def _coord_grids(height: int, width: int) -> tuple[np.ndarray, ...]:
    """Cached (xx, yy, xx-cx, yy-cy) float32 grids for an image size."""
    key = (height, width)
    with _GRID_LOCK:
        grids = _GRIDS.get(key)
        if grids is None:
            yy, xx = np.indices((height, width), dtype=np.float32)
            grids = (xx, yy, xx - width / 2.0, yy - height / 2.0)
            _GRIDS[key] = grids
            while len(_GRIDS) > _MAX_CACHED:
                _GRIDS.popitem(last=False)
        else:
            _GRIDS.move_to_end(key)
    return grids


def _scratch(height: int, width: int) -> tuple[np.ndarray, ...]:
    """Thread-local map_x / map_y / influence / tmp buffers for an image size."""
    key = (height, width)
    store = getattr(_SCRATCH, "buffers", None)
    if store is None:
        store = _SCRATCH.buffers = {}
    bufs = store.get(key)
    if bufs is None:
        shape = (height, width)
        bufs = tuple(np.empty(shape, dtype=np.float32) for _ in range(5))
        store.clear()  # only ever one active size per thread in practice
        store[key] = bufs
    return bufs


def qimage_to_rgba(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width = rgba.width()
    height = rgba.height()
    ptr = rgba.bits()
    arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
    return arr.copy()


def cached_rgba(image: QImage) -> np.ndarray:
    """qimage_to_rgba memoised on QImage.cacheKey(); the result is read-only.

    Layer pixels do not change during playback, so converting them on every
    frame is pure overhead.
    """
    key = image.cacheKey()
    with _GRID_LOCK:
        arr = _RGBA_CACHE.get(key)
        if arr is not None:
            _RGBA_CACHE.move_to_end(key)
            return arr
    arr = qimage_to_rgba(image)
    arr.flags.writeable = False
    with _GRID_LOCK:
        _RGBA_CACHE[key] = arr
        while len(_RGBA_CACHE) > _MAX_CACHED:
            _RGBA_CACHE.popitem(last=False)
    return arr


def rgba_to_qimage(array: np.ndarray) -> QImage:
    # cv2.remap on a uint8 source already returns uint8 in range, so the clip
    # and cast that used to run here were a full-resolution no-op per frame.
    if array.dtype != np.uint8:
        array = np.clip(array, 0, 255).astype(np.uint8)
    array = np.ascontiguousarray(array)
    height, width, _ = array.shape
    image = QImage(array.data, width, height, width * 4, QImage.Format.Format_RGBA8888)
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
        # Eased, not a raw triangle wave. The triangle ran at constant speed and
        # reversed instantly at both ends: measured at a 33px-per-frame velocity
        # snap against 6.8 for the seamless path, which is the jolt that made
        # Bounce look broken. Smoothstep brings the speed to zero at each
        # turnaround while still moving faster through the middle than a sine,
        # so it keeps the snappier feel the name implies.
        ramp = 1.0 - abs(2.0 * phase - 1.0)
        eased = ramp * ramp * (3.0 - 2.0 * ramp)
        travel = eased * 2.0 - 1.0
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
    source = cached_rgba(layer.image)
    height, width = source.shape[:2]
    depth = ensure_depth_map(layer)
    if depth.shape != (height, width):
        depth = cv2.resize(depth, (width, height), interpolation=cv2.INTER_LINEAR)
    if depth.dtype != np.float32:
        depth = depth.astype(np.float32)

    focus = max(0.0, min(1.0, depth_focus))
    xx, yy, xx_c, yy_c = _coord_grids(height, width)
    map_x, map_y, influence, tmp, tmp2 = _scratch(height, width)

    # influence = (depth - focus) * 2
    np.subtract(depth, focus, out=influence)
    np.multiply(influence, 2.0, out=influence)

    # Same arithmetic and same operand order as the original expression
    # `coord - d * influence - (coord - centre) * (zoom * influence)`, but
    # written in place so a preview frame allocates nothing at full resolution.
    if zoom:
        np.multiply(influence, zoom, out=tmp)      # zoom_strength
        np.multiply(xx_c, tmp, out=map_x)
        np.multiply(influence, dx, out=tmp2)
        np.subtract(xx, tmp2, out=tmp2)
        np.subtract(tmp2, map_x, out=map_x)

        np.multiply(yy_c, tmp, out=map_y)
        np.multiply(influence, dy, out=tmp2)
        np.subtract(yy, tmp2, out=tmp2)
        np.subtract(tmp2, map_y, out=map_y)
    else:
        np.multiply(influence, dx, out=tmp)
        np.subtract(xx, tmp, out=map_x)
        np.multiply(influence, dy, out=tmp)
        np.subtract(yy, tmp, out=map_y)

    displaced = cv2.remap(
        source,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rgba_to_qimage(displaced)
