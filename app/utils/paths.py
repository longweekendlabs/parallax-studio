from pathlib import Path
import os
import sys

APP_NAME = "Parallax Studio"
APP_DIR_NAME = "parallax-studio"


def app_support_dir() -> Path:
    """Return the platform app data directory for Parallax Studio."""
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        return Path(base) / APP_NAME if base else Path.home() / "AppData" / "Roaming" / APP_NAME

    base = os.environ.get("XDG_DATA_HOME")
    return Path(base) / APP_DIR_NAME if base else Path.home() / ".local" / "share" / APP_DIR_NAME


def app_config_dir() -> Path:
    """Return the platform config directory for Parallax Studio."""
    if sys.platform == "darwin":
        return app_support_dir()
    if sys.platform == "win32":
        return app_support_dir()

    base = os.environ.get("XDG_CONFIG_HOME")
    return Path(base) / APP_DIR_NAME if base else Path.home() / ".config" / APP_DIR_NAME


def settings_path() -> Path:
    return app_config_dir() / "settings.json"


def models_dir() -> Path:
    return app_support_dir() / "models"


def ensure_app_dirs() -> bool:
    try:
        app_config_dir().mkdir(parents=True, exist_ok=True)
        app_support_dir().mkdir(parents=True, exist_ok=True)
        models_dir().mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True
