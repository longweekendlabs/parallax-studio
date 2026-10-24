from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QImageReader, QPixmap


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class Layer:
    source_path: Path
    image: QImage
    name: str
    id: str = field(default_factory=lambda: uuid4().hex)
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    intensity: float = 1.0
    motion_scale_x: float = 1.0
    motion_scale_y: float = 1.0
    zoom_strength: float = 0.35
    movement_strength: float = 1.0
    focus_depth: float = 0.5
    global_intensity: float = 0.75
    duration: float = 4.0
    loop_type: str = "Seamless Loop"
    x_offset: int = 0
    y_offset: int = 0
    scale: float = 1.0
    depth_map: np.ndarray | None = None
    # Bumped by every depth edit, including brush strokes, which write into the
    # existing array. Caches downstream cannot detect those by identity, so
    # without this counter a painted stroke never reaches the preview.
    depth_revision: int = 0
    # Whether the depth map is currently flipped. Invert is a state the user has
    # to be able to read off the button, not a one-shot action that leaves no
    # trace, so the flag rides along with the map through undo and redo.
    depth_inverted: bool = False
    # (depth, inverted, portrait_hold) per step; the hold is None outside the
    # figure motions.
    depth_undo_stack: list[tuple] = field(default_factory=list)
    depth_redo_stack: list[tuple] = field(default_factory=list)
    # Set by Portrait: head, neck pivot, chest and eye distance in source
    # pixels (app/core/portrait.py). While set, the layer plays the portrait
    # motion instead of the depth-plane motion.
    portrait_rig: dict | None = None
    # Where the figure is, 0..1, so the portrait motion leaves a background still.
    portrait_mask: np.ndarray | None = None
    # 0..1 painted by Erase while a figure motion is on: 1 holds that area
    # still. The depth brush has nothing to say about these motions, which
    # take their movement from the figure, not from depth.
    portrait_hold: np.ndarray | None = None

    @property
    def file_type(self) -> str:
        return self.source_path.suffix.removeprefix(".").upper() or "IMAGE"

    @property
    def file_size_label(self) -> str:
        try:
            size = self.source_path.stat().st_size
        except OSError:
            return "missing"
        if size >= 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} MB"
        if size >= 1024:
            return f"{size / 1024:.0f} KB"
        return f"{size} B"

    @property
    def info_label(self) -> str:
        return f"{self.file_size_label}  •  {self.file_type}"

    def thumbnail(self, width: int = 120, height: int = 172) -> QPixmap:
        pixmap = QPixmap.fromImage(self.image)
        return pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    def duplicate(self) -> "Layer":
        return Layer(
            source_path=self.source_path,
            image=self.image.copy(),
            name=f"{self.name} copy",
            visible=self.visible,
            locked=self.locked,
            opacity=self.opacity,
            intensity=self.intensity,
            motion_scale_x=self.motion_scale_x,
            motion_scale_y=self.motion_scale_y,
            zoom_strength=self.zoom_strength,
            movement_strength=self.movement_strength,
            focus_depth=self.focus_depth,
            global_intensity=self.global_intensity,
            duration=self.duration,
            loop_type=self.loop_type,
            x_offset=self.x_offset,
            y_offset=self.y_offset,
            scale=self.scale,
            depth_map=None if self.depth_map is None else self.depth_map.copy(),
            depth_revision=self.depth_revision,
            depth_inverted=self.depth_inverted,
            portrait_rig=None if self.portrait_rig is None else dict(self.portrait_rig),
            portrait_mask=None if self.portrait_mask is None else self.portrait_mask.copy(),
            portrait_hold=None if self.portrait_hold is None else self.portrait_hold.copy(),
        )


def is_supported_image(path: str | Path) -> bool:
    return Path(path).suffix.lower() in IMAGE_EXTENSIONS


def load_layer(path: str | Path) -> Layer:
    source_path = Path(path)
    reader = QImageReader(str(source_path))
    reader.setAutoTransform(True)
    image = reader.read()
    if image.isNull():
        error = reader.errorString() or "Unsupported or unreadable image"
        raise ValueError(f"{source_path.name}: {error}")

    return Layer(
        source_path=source_path,
        image=image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied),
        name=source_path.stem,
    )
