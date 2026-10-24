import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.utils.paths import ensure_app_dirs, settings_path


@dataclass
class AppSettings:
    recent_projects: list[str] = field(default_factory=list)
    last_open_dir: str = ""
    last_export_dir: str = ""
    window_width: int = 1448
    window_height: int = 1086
    # Off by default: GPU export needs an optional PyTorch install that is not
    # bundled, and the CPU renderer produces the same frames either way.
    gpu_export: bool = False
    gpu_encode: bool = True
    # Depth model used by Auto Depth, Body Relief, Portrait, Flaunt and Bounce; see app/core/depth_model.py
    depth_model: str = "dav2-small-fp16"
    # How far apart Body Relief pushes the parts of a figure. Must match
    # body_model.BODY_SPREAD, which is the same number for callers that do not
    # go through settings. Adjustable in the Settings dialog.
    body_relief_strength: float = 1.10
    # Pose model behind Body Relief; see app/core/body_model.py POSE_SPECS
    pose_model: str = "movenet-multipose"

    # ── What Body Relief is allowed to move ──────────────────────────────
    # Each region has its own share of the relief, 0 meaning it is left exactly
    # where the depth model put it. These exist because "which parts move" is a
    # taste decision, not something the app should decide silently.
    #
    # Face is off by default and should usually stay off: displacing it pulls
    # the features apart, and it is the first thing anyone looks at.
    relief_face: float = 0.0
    # Hair is the part of a head that has any business bouncing, so it is on.
    relief_hair: float = 0.85
    # The torso and limbs, which is what the button is for.
    relief_body: float = 1.0
    # Never the background. Kept here so the setting is visible and the value
    # is one place rather than scattered, but the UI does not offer to raise it.
    relief_background: float = 0.0


def load_settings(path: Path | None = None) -> AppSettings:
    target = path or settings_path()
    if not target.exists():
        return AppSettings()

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppSettings()

    allowed = AppSettings.__dataclass_fields__.keys()
    clean: dict[str, Any] = {key: data[key] for key in allowed if key in data}
    return AppSettings(**clean)


def save_settings(settings: AppSettings, path: Path | None = None) -> None:
    if not ensure_app_dirs():
        return
    target = path or settings_path()
    try:
        target.write_text(
            json.dumps(asdict(settings), indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        return
