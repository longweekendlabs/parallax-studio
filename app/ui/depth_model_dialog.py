from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

import numpy as np
from PySide6.QtGui import QImage

from app.core import depth_model
from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_PANEL_BG,
    C_TEXT_MAIN,
    C_TEXT_SECONDARY,
    C_WINDOW_BG,
)


class _Worker(QObject):
    """Downloads the model if needed, then runs depth estimation."""

    progress = Signal(int, int, str)   # current, total, label
    finished = Signal(object)          # np.ndarray depth map
    error = Signal(str)

    def __init__(self, image: QImage, model_id: str, relief: bool = False,
                 relief_strength: float | None = None):
        super().__init__()
        self._image = image
        self._model_id = model_id
        self._relief = relief
        self._relief_strength = relief_strength
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def _fetch(self, model) -> bool:
        """Download one model, reporting progress. False if cancelled."""
        if depth_model.has_file(model):
            return True

        def on_progress(done: int, total: int):
            self.progress.emit(
                done, total,
                f"Downloading {model.label}  {done // 1048576} / {max(1, total // 1048576)} MB",
            )

        self.progress.emit(0, 1, f"Connecting to download {model.label}...")
        depth_model.ensure_file(
            model, progress_cb=on_progress, cancelled_cb=lambda: self._cancelled
        )
        return not self._cancelled

    @Slot()
    def run(self):
        try:
            if not self._fetch(depth_model.get_model(self._model_id)):
                return
            if self._relief:
                # Body relief needs the person and pose models on top of the
                # depth model; each is fetched once and kept.
                from app.core import body_model

                for extra in body_model.BODY_MODELS:
                    if not self._fetch(extra):
                        return

            if self._cancelled:
                return

            # Indeterminate: inference is a single opaque call.
            self.progress.emit(
                0, 0,
                "Finding the body and its parts..." if self._relief
                else "Analysing image depth...",
            )
            depth = depth_model.estimate_depth(
                self._image, self._model_id, relief=self._relief,
                relief_strength=self._relief_strength,
            )
            if self._cancelled:
                return
            self.finished.emit(depth)
        except InterruptedError:
            return
        except Exception as exc:
            self.error.emit(str(exc))


class DepthModelDialog(QDialog):
    """Progress window for the one-time model download plus depth estimation."""

    def __init__(self, image: QImage, model_id: str, parent=None, relief: bool = False,
                 relief_strength: float | None = None):
        super().__init__(parent)
        self.depth_map: np.ndarray | None = None
        self._model_id = model_id
        self._relief = relief
        self._relief_strength = relief_strength
        self._thread: QThread | None = None
        self._worker: _Worker | None = None

        model = depth_model.get_model(model_id)
        already = depth_model.is_downloaded(model_id)
        if relief:
            from app.core import body_model

            already = already and body_model.models_ready()
        title = "Body Relief" if relief else "Auto Depth"
        self.setWindowTitle(title if already else "Download Depth Model")
        self.setModal(True)
        self.setFixedWidth(430)
        self.setStyleSheet(
            f"""
            QDialog {{ background: {C_WINDOW_BG}; color: {C_TEXT_MAIN}; }}
            QLabel {{ background: transparent; }}
            QPushButton {{
                background: {C_PANEL_BG}; border: 1px solid {C_BORDER};
                border-radius: 6px; color: {C_TEXT_MAIN}; padding: 6px 16px;
            }}
            QPushButton:hover {{ border-color: {C_ACCENT}; color: {C_ACCENT}; }}
            QProgressBar {{
                background: #0D141B; border: 1px solid {C_BORDER};
                border-radius: 6px; height: 18px; text-align: center;
                color: {C_TEXT_SECONDARY}; font-size: 11px;
            }}
            QProgressBar::chunk {{ background: {C_ACCENT}; border-radius: 5px; }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(12)

        # Heading names the operation once the models are on disk. Showing the
        # model and its size every run made a routine 2-second progress window
        # look like it was downloading 50 MB again on every click.
        heading = QLabel(title if already else model.label)
        heading.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 14px; font-weight: 700;")
        layout.addWidget(heading)

        if not already:
            blurb = QLabel(
                f"This is a one-time download of about {model.approx_bytes // 1048576} MB. "
                "It is kept on this machine and reused every time after."
            )
            blurb.setWordWrap(True)
            blurb.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
            layout.addWidget(blurb)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        layout.addWidget(self.bar)

        self.status = QLabel("Starting...")
        self.status.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        row.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._on_cancel)
        row.addWidget(self.cancel_button)
        layout.addLayout(row)

    def start(self):
        self._worker = _Worker(
            self._image_ref, self._model_id, self._relief, self._relief_strength
        )
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    # image is stored separately so start() can be called after construction
    def set_image(self, image: QImage):
        self._image_ref = image

    @Slot(int, int, str)
    def _on_progress(self, current: int, total: int, label: str):
        if total <= 0:
            self.bar.setRange(0, 0)  # busy indicator
        else:
            self.bar.setRange(0, 100)
            self.bar.setValue(int(current * 100 / max(1, total)))
        self.status.setText(label)

    @Slot(object)
    def _on_finished(self, depth):
        self.depth_map = depth
        self._stop_thread()
        self.accept()

    @Slot(str)
    def _on_error(self, message: str):
        self._stop_thread()
        self.status.setText(message)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.cancel_button.setText("Close")

    def _on_cancel(self):
        if self._worker:
            self._worker.cancel()
        self._stop_thread()
        self.reject()

    def _stop_thread(self):
        if self._thread:
            self._thread.quit()
            self._thread.wait(4000)
            self._thread = None
            self._worker = None

    def closeEvent(self, event):
        self._on_cancel()
        super().closeEvent(event)
