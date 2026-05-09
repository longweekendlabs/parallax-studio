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
