from pathlib import Path

APP_NAME = "Parallax Studio"


def app_support_dir() -> Path:
    """Return the macOS Application Support directory for Parallax Studio."""
    return Path.home() / "Library" / "Application Support" / APP_NAME


def settings_path() -> Path:
    return app_support_dir() / "settings.json"


def models_dir() -> Path:
    return app_support_dir() / "models"


def ensure_app_dirs() -> bool:
    try:
        app_support_dir().mkdir(parents=True, exist_ok=True)
        models_dir().mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True
