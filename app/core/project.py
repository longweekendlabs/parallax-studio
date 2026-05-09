import base64
import json
import zlib
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from app.core.layer import Layer, load_layer
from app.ui.controls import MotionSettings


class ProjectSerializer:
    @staticmethod
    def serialize(
        layers: list[Layer],
        motion_settings: MotionSettings,
        selected_layer_id: str | None,
    ) -> str:
        data = {
            "version": "1.0",
            "selected_layer_id": selected_layer_id,
            "motion_settings": {
                "motion_scale_x": motion_settings.motion_scale_x,
                "motion_scale_y": motion_settings.motion_scale_y,
                "zoom_strength": motion_settings.zoom_strength,
                "loop_type": motion_settings.loop_type,
                "movement_strength": motion_settings.movement_strength,
                "focus_depth": motion_settings.focus_depth,
                "layer_intensity": motion_settings.layer_intensity,
                "global_intensity": motion_settings.global_intensity,
                "duration": motion_settings.duration,
                "preview_fps": motion_settings.preview_fps,
            },
            "layers": [],
        }

        for layer in layers:
            layer_data = {
                "id": layer.id,
                "name": layer.name,
                "source_path": str(layer.source_path),
                "visible": layer.visible,
                "locked": layer.locked,
                "opacity": layer.opacity,
                "intensity": layer.intensity,
                "motion_scale_x": layer.motion_scale_x,
                "motion_scale_y": layer.motion_scale_y,
                "zoom_strength": layer.zoom_strength,
                "movement_strength": layer.movement_strength,
                "focus_depth": layer.focus_depth,
                "global_intensity": layer.global_intensity,
                "duration": layer.duration,
                "loop_type": layer.loop_type,
                "x_offset": layer.x_offset,
                "y_offset": layer.y_offset,
                "scale": layer.scale,
            }

            if layer.depth_map is not None:
                # Compress depth map (float32 -> bytes -> zlib -> base64)
                depth_bytes = layer.depth_map.astype(np.float32).tobytes()
                compressed = zlib.compress(depth_bytes)
                layer_data["depth_map"] = base64.b64encode(compressed).decode("ascii")
                layer_data["depth_width"] = layer.depth_map.shape[1]
                layer_data["depth_height"] = layer.depth_map.shape[0]

            data["layers"].append(layer_data)

        return json.dumps(data, indent=2)

    @staticmethod
    def deserialize(json_str: str) -> tuple[list[Layer], MotionSettings, str | None]:
        data = json.loads(json_str)
        ms_data = data.get("motion_settings", {})

        motion_settings = MotionSettings(
            motion_scale_x=ms_data.get("motion_scale_x", 1.0),
            motion_scale_y=ms_data.get("motion_scale_y", 1.0),
            zoom_strength=ms_data.get("zoom_strength", 0.35),
            loop_type=ms_data.get("loop_type", "Seamless Loop"),
            movement_strength=ms_data.get("movement_strength", 1.0),
            focus_depth=ms_data.get("focus_depth", 0.5),
            layer_intensity=ms_data.get("layer_intensity", 0.65),
            global_intensity=ms_data.get("global_intensity", 0.75),
            duration=ms_data.get("duration", 4.0),
            preview_fps=ms_data.get("preview_fps", 24),
        )

        layers = []
        for l_data in data.get("layers", []):
            source_path = Path(l_data["source_path"])
            try:
                layer = load_layer(source_path)
            except Exception:
                # Handle missing or unreadable file gracefully
                placeholder = QImage(256, 256, QImage.Format.Format_ARGB32_Premultiplied)
                placeholder.fill(Qt.GlobalColor.darkGray)
                layer = Layer(
                    source_path=source_path,
                    image=placeholder,
                    name=l_data.get("name", source_path.stem) + " (Missing)",
                )

            layer.id = l_data["id"]
            layer.name = l_data["name"]
            layer.visible = l_data.get("visible", True)
            layer.locked = l_data.get("locked", False)
            layer.opacity = l_data.get("opacity", 1.0)
            layer.intensity = l_data.get("intensity", 1.0)
            layer.motion_scale_x = l_data.get("motion_scale_x", 1.0)
            layer.motion_scale_y = l_data.get("motion_scale_y", 1.0)
            layer.zoom_strength = l_data.get("zoom_strength", 0.35)
            layer.movement_strength = l_data.get("movement_strength", 1.0)
            layer.focus_depth = l_data.get("focus_depth", 0.5)
            layer.global_intensity = l_data.get("global_intensity", 0.75)
            layer.duration = l_data.get("duration", 4.0)
            layer.loop_type = l_data.get("loop_type", "Seamless Loop")
            layer.x_offset = l_data.get("x_offset", 0)
            layer.y_offset = l_data.get("y_offset", 0)
            layer.scale = l_data.get("scale", 1.0)

            if "depth_map" in l_data and "depth_width" in l_data and "depth_height" in l_data:
                try:
                    depth_bytes = zlib.decompress(base64.b64decode(l_data["depth_map"]))
                    depth_map = np.frombuffer(depth_bytes, dtype=np.float32)
                    h, w = l_data["depth_height"], l_data["depth_width"]
                    layer.depth_map = depth_map.reshape((h, w)).copy()
                except Exception:
                    layer.depth_map = None

            layers.append(layer)

        return layers, motion_settings, data.get("selected_layer_id")
