from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Callable

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from app.core.compositor import composite_animated_layers
from app.core.layer import Layer


def _qimage_to_rgb(image: QImage) -> np.ndarray:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    h, w = rgba.height(), rgba.width()
    arr = np.frombuffer(rgba.bits(), dtype=np.uint8).reshape((h, w, 4)).copy()
    return arr[:, :, :3]


def _even_dims(arr: np.ndarray) -> np.ndarray:
    """Crop to even dimensions required by H.264."""
    h, w = arr.shape[:2]
    return arr[: h & ~1, : w & ~1]


def render_frames(
    layers: Sequence[Layer],
    duration: float,
    fps: int,
    scale: float = 1.0,
    loop_type: str = "Seamless Loop",
    global_intensity: float = 0.75,
    focus_depth: float = 0.5,
    progress_cb: Callable[[int, int], None] | None = None,
    cancelled_cb: Callable[[], bool] | None = None,
) -> list[np.ndarray]:
    """Render animation frames as a list of RGB uint8 numpy arrays."""
    total = max(1, int(round(duration * fps)))
    frames: list[np.ndarray] = []
    amplitude = 20.0

    for i in range(total):
        if cancelled_cb and cancelled_cb():
            return []

        phase = i / total
        frame = composite_animated_layers(
            layers,
            phase,
            amplitude,
            global_intensity=global_intensity,
            depth_focus=focus_depth,
            loop_type=loop_type,
        )
        if frame is None:
            continue

        if scale != 1.0:
            new_w = max(1, int(frame.width() * scale))
            new_h = max(1, int(frame.height() * scale))
            frame = frame.scaled(
                new_w,
                new_h,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        frames.append(_qimage_to_rgb(frame))
        if progress_cb:
            progress_cb(i + 1, total)

    return frames


def export_mp4(
    frames: list[np.ndarray],
    output_path: Path,
    fps: int,
    progress_cb: Callable[[int, int], None] | None = None,
) -> None:
    import imageio  # deferred — not needed on module load

    total = len(frames)
    writer = imageio.get_writer(str(output_path), fps=fps, quality=8)
    try:
        for i, frame in enumerate(frames):
            writer.append_data(_even_dims(frame))
            if progress_cb:
                progress_cb(i + 1, total)
    finally:
        writer.close()


def export_gif(
    frames: list[np.ndarray],
    output_path: Path,
    fps: int,
    progress_cb: Callable[[int, int], None] | None = None,
) -> None:
    from PIL import Image  # deferred

    if not frames:
        raise ValueError("No frames to export")

    duration_ms = max(1, int(round(1000 / fps)))
    total = len(frames)
    pil_frames = []
    for i, frame in enumerate(frames):
        pil_frames.append(Image.fromarray(frame))
        if progress_cb:
            progress_cb(i + 1, total)

    pil_frames[0].save(
        str(output_path),
        save_all=True,
        append_images=pil_frames[1:],
        loop=0,
        duration=duration_ms,
        optimize=True,
    )
