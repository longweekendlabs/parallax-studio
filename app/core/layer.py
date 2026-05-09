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
    depth_undo_stack: list[np.ndarray] = field(default_factory=list)
    depth_redo_stack: list[np.ndarray] = field(default_factory=list)

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
