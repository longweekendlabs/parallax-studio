import os
import sys
from pathlib import Path

# PyInstaller points these at the bundle so the frozen app finds its own
# libraries. Anything we spawn inherits them and then tries to load our Qt/GTK
# build instead of the system one, which makes helpers like kdialog abort with
# missing-symbol errors. Restore the originals before launching system tools.
_BUNDLE_ENV_VARS = (
    "LD_LIBRARY_PATH",
    "DYLD_LIBRARY_PATH",
    "DYLD_FRAMEWORK_PATH",
    "QT_PLUGIN_PATH",
    "QML2_IMPORT_PATH",
    "GTK_PATH",
    "GI_TYPELIB_PATH",
    "GDK_PIXBUF_MODULE_FILE",
    "GSETTINGS_SCHEMA_DIR",
    "FONTCONFIG_FILE",
    "FONTCONFIG_PATH",
)


def resource_path(*parts: str) -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).joinpath(*parts)
    return Path(__file__).resolve().parents[2].joinpath(*parts)


def system_env() -> dict[str, str]:
    """Environment for spawning *system* executables from inside the app.

    Outside a bundle this is just the current environment.
    """
    env = dict(os.environ)
    if not getattr(sys, "frozen", False):
        return env

    meipass = getattr(sys, "_MEIPASS", None)
    for var in _BUNDLE_ENV_VARS:
        original = env.pop(f"{var}_ORIG", None)
        if original is not None:
            # PyInstaller saved what was there before it took over.
            if original:
                env[var] = original
            else:
                env.pop(var, None)
        elif meipass and var in env:
            # No saved original means the variable did not exist before the
            # bundle set it; drop the bundle's own paths from it.
            kept = [
                part
                for part in env[var].split(os.pathsep)
                if part and not part.startswith(meipass)
            ]
            if kept:
                env[var] = os.pathsep.join(kept)
            else:
                env.pop(var, None)
    return env
