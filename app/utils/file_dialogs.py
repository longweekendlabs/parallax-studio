from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QWidget


IMAGE_PATTERNS = ["*.png", "*.jpg", "*.jpeg", "*.webp"]
PROJECT_PATTERNS = ["*.parlx"]
ALL_OPEN_PATTERNS = PROJECT_PATTERNS + IMAGE_PATTERNS


@contextmanager
def _plain_qt_dialogs():
    app = QApplication.instance()
    if app is None:
        yield
        return
    old_stylesheet = app.styleSheet()
    try:
        app.setStyleSheet("")
        yield
    finally:
        app.setStyleSheet(old_stylesheet)


def _start_path(start: str | Path, save_name: str = "") -> str:
    path = Path(start or Path.home()).expanduser()
    if save_name:
        if path.is_dir():
            return str(path / save_name)
        return str(path)
    if path.is_file():
        return str(path.parent)
    return str(path)


def _desktop_commands() -> list[str]:
    desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    session = os.environ.get("DESKTOP_SESSION", "").lower()
    if "kde" in desktop or "plasma" in desktop or "kde" in session or "plasma" in session:
        return ["kdialog", "zenity"]
    return ["zenity", "kdialog"]


def _run_dialog(args: list[str]) -> list[str] | None:
    started = time.monotonic()
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return None
    if result.returncode == 0:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]

    # If the desktop helper exits immediately, treat it as unavailable and let
    # the next helper or Qt's native dialog handle the request. If it stayed up
    # long enough for user interaction, this was most likely a normal cancel.
    if time.monotonic() - started < 0.75:
        return None
    else:
        return []


def _kdialog_open(title: str, start: str, patterns: list[str], multiple: bool) -> list[str] | None:
    exe = shutil.which("kdialog")
    if not exe:
        return None
    args = [exe, "--title", title]
    if multiple:
        args += ["--multiple", "--separate-output"]
    args += ["--getopenfilename", _start_path(start), " ".join(patterns)]
    return _run_dialog(args)


def _kdialog_save(title: str, start: str, patterns: list[str]) -> str | None:
    exe = shutil.which("kdialog")
    if not exe:
        return None
    args = [exe, "--title", title, "--getsavefilename", _start_path(start), " ".join(patterns)]
    paths = _run_dialog(args)
    return paths[0] if paths else ""


def _zenity_open(title: str, start: str, patterns: list[str], multiple: bool) -> list[str] | None:
    exe = shutil.which("zenity")
    if not exe:
        return None
    args = [
        exe,
        "--file-selection",
        f"--title={title}",
        f"--filename={_start_path(start)}/",
        f"--file-filter=Supported files | {' '.join(patterns)}",
    ]
    if multiple:
        args += ["--multiple", "--separator=\n"]
    return _run_dialog(args)


def _zenity_save(title: str, start: str, patterns: list[str]) -> str | None:
    exe = shutil.which("zenity")
    if not exe:
        return None
    args = [
        exe,
        "--file-selection",
        "--save",
        f"--title={title}",
        f"--filename={_start_path(start)}",
        f"--file-filter=Supported files | {' '.join(patterns)}",
    ]
    paths = _run_dialog(args)
    return paths[0] if paths else ""


def _try_desktop_open(title: str, start: str, patterns: list[str], multiple: bool) -> list[str] | None:
    if sys.platform != "linux":
        return None
    for command in _desktop_commands():
        if command == "kdialog":
            paths = _kdialog_open(title, start, patterns, multiple)
        else:
            paths = _zenity_open(title, start, patterns, multiple)
        if paths is not None:
            return paths
    return None


def _try_desktop_save(title: str, start: str, patterns: list[str]) -> str | None:
    if sys.platform != "linux":
        return None
    for command in _desktop_commands():
        if command == "kdialog":
            path = _kdialog_save(title, start, patterns)
        else:
            path = _zenity_save(title, start, patterns)
        if path is not None:
            return path
    return None


def open_project_or_image(parent: QWidget, title: str, start: str) -> str:
    paths = _try_desktop_open(title, start, ALL_OPEN_PATTERNS, multiple=False)
    if paths is not None:
        return paths[0] if paths else ""
    with _plain_qt_dialogs():
        path, _ = QFileDialog.getOpenFileName(
            parent,
            title,
            start,
            "All Supported (*.parlx *.png *.jpg *.jpeg *.webp);;Parallax Project (*.parlx);;Images (*.png *.jpg *.jpeg *.webp)",
        )
    return path


def open_images(parent: QWidget, title: str, start: str) -> list[str]:
    paths = _try_desktop_open(title, start, IMAGE_PATTERNS, multiple=True)
    if paths is not None:
        return paths
    with _plain_qt_dialogs():
        files, _ = QFileDialog.getOpenFileNames(parent, title, start, "Images (*.png *.jpg *.jpeg *.webp)")
    return files


def save_project(parent: QWidget, title: str, start: str) -> str:
    path = _try_desktop_save(title, start, PROJECT_PATTERNS)
    if path is not None:
        return path
    with _plain_qt_dialogs():
        path, _ = QFileDialog.getSaveFileName(parent, title, start, "Parallax Studio Projects (*.parlx)")
    return path


def save_export(parent: QWidget, title: str, start: str, extension: str) -> str:
    patterns = [f"*{extension}"]
    label = "MP4 Video" if extension == ".mp4" else "GIF Animation"
    path = _try_desktop_save(title, start, patterns)
    if path is not None:
        return path
    with _plain_qt_dialogs():
        path, _ = QFileDialog.getSaveFileName(parent, title, start, f"{label} (*{extension})")
    return path
