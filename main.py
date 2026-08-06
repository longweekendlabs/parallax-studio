import logging
import os
import platform
import sys

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from app.version import __app_name__, __org_name__, __version__
from app.ui.main_window import MainWindow
from app.ui.theme import QSS
from app.utils.resources import resource_path


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
    # Apple Silicon guard is only relevant on macOS source runs. Linux and
    # Windows builds are supported on their native architectures.
    if sys.platform == "darwin" and platform.machine() not in ("arm64", ""):
        _warn(
            "Unsupported Architecture",
            "Parallax Studio macOS release builds target Apple Silicon (M1 / M2 / M3 / M4).",
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
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(__org_name__)
    app.setDesktopFileName("com.longweekendlabs.parallaxstudio")
    app.setWindowIcon(QIcon(str(resource_path("assets", "icons", "parallax-studio.png"))))
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)

    _check_environment()

    window = MainWindow()
    window.show()

    # Say up front what is missing, rather than ambushing the user with a
    # download the first time they press a button. Only the models the two
    # depth buttons actually need count here: the optional full-precision and
    # Base checkpoints are alternatives, and nagging about them every launch
    # would train the dialog to be dismissed unread.
    QTimer.singleShot(0, lambda: _offer_model_setup(window))

    sys.exit(app.exec())


def _offer_model_setup(window) -> None:
    try:
        from app.ui.model_panel import essential_missing
        from app.ui.model_setup_dialog import ModelSetupDialog

        if not essential_missing(window.settings):
            return
        ModelSetupDialog(window).exec()
    except Exception:
        logging.getLogger(__name__).exception("Model setup check failed")


if __name__ == "__main__":
    main()
