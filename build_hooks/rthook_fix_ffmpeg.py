# Runtime hook — runs before any app code inside the bundled .app.
#
# In a PyInstaller macOS .app bundle, data files classified as "binary"
# (executables) land in Contents/Frameworks/, while the importlib.resources
# lookup inside imageio_ffmpeg would look in Contents/Resources/.
#
# We search both locations and explicitly set IMAGEIO_FFMPEG_EXE so that
# imageio_ffmpeg.get_ffmpeg_exe() uses the right path regardless of how
# the package resolves its own resource paths.

import glob
import os
import sys


def _find_bundle_ffmpeg() -> str | None:
    # sys.executable = .../Contents/MacOS/Parallax Studio
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    contents_dir = os.path.dirname(exe_dir)

    candidates = [
        os.path.join(contents_dir, "Frameworks", "imageio_ffmpeg", "binaries"),
        os.path.join(contents_dir, "Resources", "imageio_ffmpeg", "binaries"),
        os.path.join(exe_dir, "imageio_ffmpeg", "binaries"),
    ]
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "imageio_ffmpeg", "binaries"))

    for bin_dir in candidates:
        for f in glob.glob(os.path.join(bin_dir, "ffmpeg*")):
            if not f.endswith(".md") and os.path.isfile(f):
                return f
        # continue to next candidate if nothing found in this one
    return None


if getattr(sys, "frozen", False):
    ffmpeg = _find_bundle_ffmpeg()
    if ffmpeg:
        try:
            os.chmod(ffmpeg, 0o755)
        except OSError:
            pass
        # First item checked by imageio_ffmpeg.get_ffmpeg_exe() — bypasses
        # the importlib.resources lookup that breaks in bundled apps.
        os.environ.setdefault("IMAGEIO_FFMPEG_EXE", ffmpeg)
