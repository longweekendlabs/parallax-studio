import os
import platform
import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from app.ui.main_window import MainWindow
from app.ui.theme import QSS


def _warn(title: str, body: str, detail: str = "") -> None:
    msg = QMessageBox()
    msg.setWindowTitle(title)
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setText(body)
    if detail:
        msg.setInformativeText(detail)
    msg.exec()


def _check_environment() -> bool:
    """
    Runs before the main window is created.
    Returns False only if the problem is fatal and the app cannot start.
    """
    # Apple Silicon guard — only relevant when running from source on an Intel Mac.
    # The bundled .app is arm64-only so macOS enforces this automatically there.
    if platform.machine() not in ("arm64", ""):
        _warn(
            "Unsupported Architecture",
            "Parallax Studio is built for Apple Silicon (M1 / M2 / M3 / M4).",
            f"This machine reports: {platform.machine()}\n\n"
            "The app may not work correctly.",
        )
        # Non-fatal: allow launch anyway in case of unusual Rosetta setup

    # ffmpeg check — warns if the bundled encoder is missing or not executable.
    # Export will fail without it, but painting / preview / save still work.
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        if not os.path.isfile(ffmpeg_exe):
            raise FileNotFoundError(ffmpeg_exe)
        if not os.access(ffmpeg_exe, os.X_OK):
            os.chmod(ffmpeg_exe, 0o755)
    except Exception as exc:
        _warn(
            "Export Encoder Unavailable",
            "The bundled ffmpeg encoder could not be found.",
            "MP4 and GIF export will not work in this session.\n"
            "All other features (import, paint, preview, save) are unaffected.\n\n"
            f"Detail: {exc}",
        )
        # Non-fatal

    return True


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Parallax Studio")
    app.setOrganizationName("Long Weekend Labs")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    _check_environment()

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
