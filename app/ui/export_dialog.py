from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.core.exporter import export_gif, export_mp4, is_cuda_available, is_nvenc_available, render_frames
from app.core.layer import Layer
from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_BORDER_SOFT,
    C_EXPORT,
    C_PANEL_BG,
    C_RAISED_PANEL,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
    C_WINDOW_BG,
)
from app.utils.file_dialogs import save_export


class _ExportWorker(QObject):
    progress = Signal(int, int, str)   # current, total, label
    finished = Signal(str)             # output_path
    error = Signal(str)

    def __init__(
        self,
        layers: list[Layer],
        duration: float,
        fps: int,
        scale: float,
        loop_type: str,
        global_intensity: float,
        focus_depth: float,
        fmt: str,
        output_path: Path,
        use_gpu: bool = False,
        use_nvenc: bool = True,
    ):
        super().__init__()
        self._layers = layers
        self._duration = duration
        self._fps = fps
        self._scale = scale
        self._loop_type = loop_type
        self._global_intensity = global_intensity
        self._focus_depth = focus_depth
        self._fmt = fmt
        self._output_path = output_path
        self._use_gpu = use_gpu
        self._use_nvenc = use_nvenc
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @Slot()
    def run(self) -> None:
        try:
            total_frames = max(1, int(round(self._duration * self._fps)))
            # Set by render_frames once it knows which backend it actually used,
            # so the label never claims GPU while the CPU path is running.
            render_label = "Rendering"

            def backend_cb(backend: str) -> None:
                nonlocal render_label
                render_label = "Rendering (GPU)" if backend == "cuda" else "Rendering (CPU)"

            def render_cb(i: int, _t: int) -> None:
                self.progress.emit(i, total_frames * 2, f"{render_label}  {i} / {total_frames}")

            frames = render_frames(
                self._layers,
                self._duration,
                self._fps,
                self._scale,
                self._loop_type,
                self._global_intensity,
                self._focus_depth,
                progress_cb=render_cb,
                cancelled_cb=lambda: self._cancelled,
                backend_cb=backend_cb,
                use_gpu=self._use_gpu,
            )

            if self._cancelled:
                return

            if not frames:
                self.error.emit("No visible layers to render.")
                return

            if self._fmt == "MP4":
                nvenc = self._use_nvenc and is_nvenc_available()
                enc_label = "Encoding MP4 (GPU)" if nvenc else "Encoding MP4…"
                self.progress.emit(total_frames, total_frames * 2, enc_label)

                def encode_cb(i: int, t: int) -> None:
                    self.progress.emit(total_frames + i, total_frames * 2, f"Encoding  {i} / {t}")

                export_mp4(
                    frames,
                    self._output_path,
                    self._fps,
                    progress_cb=encode_cb,
                    use_nvenc=self._use_nvenc,
                )
            else:
                self.progress.emit(total_frames, total_frames * 2, "Building GIF…")
                export_gif(frames, self._output_path, self._fps)

            if not self._cancelled:
                self.finished.emit(str(self._output_path))

        except Exception as exc:
            self.error.emit(str(exc))


def _section_header(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 10px; font-weight: 700; "
        f"letter-spacing: 1.5px; background: transparent;"
    )
    return lbl


def _row_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 14px; background: transparent;")
    return lbl


def _value_box(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedSize(58, 28)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"""
        QLabel {{
            background: #0D141B;
            border: 1px solid {C_BORDER};
            border-radius: 6px;
            color: {C_TEXT_MAIN};
            font-family: 'JetBrains Mono', 'SF Mono', monospace;
            font-size: 12px;
        }}
        """
    )
    return lbl


class ExportDialog(QDialog):
    exportCompleted = Signal(str)

    def __init__(
        self,
        layers: list[Layer],
        motion_settings,
        last_export_dir: str = "",
        parent=None,
        use_gpu: bool = False,
        use_nvenc: bool = True,
    ):
        super().__init__(parent)
        self._layers = layers
        self._motion = motion_settings
        self._use_gpu = use_gpu
        self._use_nvenc = use_nvenc
        self._last_export_dir = last_export_dir or str(Path.home() / "Movies")
        self._fmt = "MP4"
        self._thread: QThread | None = None
        self._worker: _ExportWorker | None = None
        self.last_used_dir: str = ""
        self._user_selected_path: bool = False

        self.setWindowTitle("Export Animation")
        self.setModal(True)
        self.setMinimumWidth(484)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.MinimumExpanding)

        self._build()
        self._update_output_path()

    # ── build ──────────────────────────────────────────────────────────────

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        # Header Row with Title & CUDA Badge
        header_row = QHBoxLayout()
        title = QLabel("Export Animation")
        title.setStyleSheet(
            f"font-size: 17px; font-weight: 700; color: {C_TEXT_MAIN}; background: transparent;"
        )
        header_row.addWidget(title)

        # Report only what this export will really use, not what the machine
        # could theoretically do. Enabling GPU work lives in Settings.
        gpu_render = self._use_gpu and is_cuda_available()
        gpu_encode = self._use_nvenc and is_nvenc_available()
        if gpu_render or gpu_encode:
            parts = []
            if gpu_render:
                parts.append("render")
            if gpu_encode:
                parts.append("encode")
            badge = QLabel(f"GPU: {' + '.join(parts)}")
            badge.setStyleSheet(
                f"background: #102A1E; color: #4ADE80; border: 1px solid #166534; "
                f"border-radius: 10px; padding: 3px 8px; font-size: 11px; font-weight: 600;"
            )
            badge.setToolTip("Hardware acceleration enabled for this export (see Settings).")
        else:
            badge = QLabel("CPU")
            badge.setStyleSheet(
                f"background: #1A222B; color: {C_TEXT_SECONDARY}; border: 1px solid {C_BORDER}; "
                f"border-radius: 10px; padding: 3px 8px; font-size: 11px; font-weight: 600;"
            )
            badge.setToolTip("Rendering and encoding on the CPU. Enable GPU acceleration in Settings.")
        header_row.addStretch()
        header_row.addWidget(badge)

        layout.addLayout(header_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(sep)

        # FORMAT card
        layout.addWidget(self._build_format_card())

        # SETTINGS card
        layout.addWidget(self._build_settings_card())

        # OUTPUT card
        layout.addWidget(self._build_output_card())

        # Progress (hidden until export starts)
        self._progress_widget = self._build_progress_widget()
        self._progress_widget.hide()
        layout.addWidget(self._progress_widget)

        # Button row
        layout.addLayout(self._build_buttons())

    def _make_card(self, object_name: str) -> QFrame:
        card = QFrame()
        card.setObjectName(object_name)
        card.setStyleSheet(
            f"""
            QFrame#{object_name} {{
                background: {C_RAISED_PANEL};
                border: 1px solid {C_BORDER_SOFT};
                border-radius: 10px;
            }}
            """
        )
        return card

    def _build_format_card(self) -> QFrame:
        card = self._make_card("fmtCard")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 13, 16, 13)
        col.setSpacing(10)
        col.addWidget(_section_header("FORMAT"))

        row = QHBoxLayout()
        row.setSpacing(8)

        self._mp4_btn = QPushButton("MP4")
        self._gif_btn = QPushButton("GIF")
        self._mp4_btn.setToolTip("Best for sharing, editing, and high-quality playback. Uses H.264 video encoding.")
        self._gif_btn.setToolTip("Best for quick looping previews. File size grows quickly, especially at large resolutions.")
        for btn in (self._mp4_btn, self._gif_btn):
            btn.setFixedSize(88, 32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

        self._mp4_btn.clicked.connect(lambda: self._set_format("MP4"))
        self._gif_btn.clicked.connect(lambda: self._set_format("GIF"))
        self._refresh_format_buttons()

        row.addWidget(self._mp4_btn)
        row.addWidget(self._gif_btn)
        row.addStretch()
        col.addLayout(row)
        return card

    def _build_settings_card(self) -> QFrame:
        card = self._make_card("settingsCard")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 13, 16, 13)
        col.setSpacing(12)
        col.addWidget(_section_header("SETTINGS"))

        # Duration
        dur_row = QHBoxLayout()
        dur_row.setSpacing(10)
        dur_row.addWidget(_row_label("Duration"))
        self._duration_slider = QSlider(Qt.Orientation.Horizontal)
        self._duration_slider.setRange(2, 30)
        self._duration_slider.setValue(max(2, min(30, int(self._motion.duration))))
        self._duration_slider.setFixedHeight(18)
        self._duration_slider.setToolTip("Length of the rendered loop. Longer exports move more slowly and create more frames.")
        self._duration_val = _value_box(f"{self._duration_slider.value()} s")
        self._duration_slider.valueChanged.connect(
            lambda v: self._duration_val.setText(f"{v} s")
        )
        dur_row.addWidget(self._duration_slider, stretch=1)
        dur_row.addWidget(self._duration_val)
        col.addLayout(dur_row)

        # FPS
        fps_row = QHBoxLayout()
        fps_row.addWidget(_row_label("Frame Rate"))
        fps_row.addStretch()
        self._fps_combo = QComboBox()
        self._fps_combo.addItems(["24 fps", "30 fps", "60 fps"])
        self._fps_combo.setToolTip(
            "Frames per second for the exported file. 60 fps produces smooth motion playback."
        )
        self._fps_combo.setCurrentText("60 fps")
        self._fps_combo.setFixedWidth(110)
        fps_row.addWidget(self._fps_combo)
        col.addLayout(fps_row)

        # Resolution
        res_row = QHBoxLayout()
        res_row.addWidget(_row_label("Resolution"))
        res_row.addStretch()
        self._res_combo = QComboBox()
        self._res_combo.addItems(["100%", "75%", "50%", "25%"])
        self._res_combo.setToolTip("Output size relative to the current canvas. Lower values render faster and create smaller files.")
        self._res_combo.setCurrentIndex(0)
        self._res_combo.setFixedWidth(110)
        res_row.addWidget(self._res_combo)
        col.addLayout(res_row)

        return card

    def _build_output_card(self) -> QFrame:
        card = self._make_card("outputCard")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 13, 16, 13)
        col.setSpacing(10)
        col.addWidget(_section_header("OUTPUT FILE"))

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._path_edit = QLineEdit()
        self._path_edit.setToolTip("Destination file for the rendered animation.")
        self._path_edit.setStyleSheet(
            f"""
            QLineEdit {{
                background: #0D141B;
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                color: {C_TEXT_SECONDARY};
                font-family: 'JetBrains Mono', 'SF Mono', monospace;
                font-size: 12px;
                padding: 6px 10px;
            }}
            QLineEdit:focus {{ border-color: {C_ACCENT}; color: {C_TEXT_MAIN}; }}
            """
        )
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(84)
        browse_btn.setToolTip("Pick the folder and filename for the export.")
        browse_btn.clicked.connect(self._browse_output)
        path_row.addWidget(self._path_edit, stretch=1)
        path_row.addWidget(browse_btn)
        col.addLayout(path_row)
        return card

    def _build_progress_widget(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(7)
        self._progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #0A1117;
                border: 1px solid {C_BORDER};
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {C_ACCENT};
                border-radius: 3px;
            }}
            """
        )

        self._progress_label = QLabel("Preparing…")
        self._progress_label.setStyleSheet(
            f"color: {C_TEXT_SECONDARY}; font-size: 12px; background: transparent;"
        )

        col.addWidget(self._progress_bar)
        col.addWidget(self._progress_label)
        return w

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setFixedSize(96, 36)
        self._cancel_btn.setToolTip("Stop the current render, or close this dialog before rendering starts.")
        self._cancel_btn.clicked.connect(self._on_cancel)

        self._export_btn = QPushButton("⇧  Export")
        self._export_btn.setObjectName("exportBtn")
        self._export_btn.setFixedSize(124, 36)
        self._export_btn.setToolTip("Render the current parallax motion and encode it with the selected format settings.")
        self._export_btn.clicked.connect(self._start_export)

        row.addWidget(self._cancel_btn)
        row.addWidget(self._export_btn)
        return row

    # ── format toggle ───────────────────────────────────────────────────────

    def _seg_style(self, active: bool) -> str:
        if active:
            return f"""
                QPushButton {{
                    background: {C_ACCENT}22;
                    border: 1px solid {C_ACCENT};
                    border-radius: 7px;
                    color: {C_ACCENT};
                    font-size: 13px;
                    font-weight: 600;
                }}
            """
        return f"""
            QPushButton {{
                background: #0D141B;
                border: 1px solid {C_BORDER};
                border-radius: 7px;
                color: {C_TEXT_SECONDARY};
                font-size: 13px;
            }}
            QPushButton:hover {{
                border-color: {C_ACCENT}66;
                color: {C_TEXT_MAIN};
            }}
        """

    def _refresh_format_buttons(self) -> None:
        self._mp4_btn.setStyleSheet(self._seg_style(self._fmt == "MP4"))
        self._gif_btn.setStyleSheet(self._seg_style(self._fmt == "GIF"))

    def _set_format(self, fmt: str) -> None:
        self._fmt = fmt
        self._refresh_format_buttons()
        self._update_output_extension()

    # ── path helpers ────────────────────────────────────────────────────────

    def _derive_default_path(self) -> Path:
        from datetime import datetime
        dt = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = ".mp4" if self._fmt == "MP4" else ".gif"

        if self._layers:
            src = self._layers[0].source_path
            base_dir = src.parent if src.parent.exists() else Path(self._last_export_dir)
            stem = src.stem
        else:
            base_dir = Path(self._last_export_dir)
            stem = "parallax_export"

        return base_dir / f"{stem}_{dt}{ext}"

    def _update_output_path(self) -> None:
        self._path_edit.setText(str(self._derive_default_path()))

    def _update_output_extension(self) -> None:
        current = self._path_edit.text().strip()
        if current:
            ext = ".mp4" if self._fmt == "MP4" else ".gif"
            self._path_edit.setText(str(Path(current).with_suffix(ext)))

    def _browse_output(self) -> None:
        start = self._path_edit.text().strip() or self._last_export_dir
        ext = ".mp4" if self._fmt == "MP4" else ".gif"
        path = save_export(self, "Save Export As", start, ext)
        if path:
            p = Path(path)
            if p.suffix.lower() != ext:
                p = p.with_suffix(ext)
            self._path_edit.setText(str(p))
            self.last_used_dir = str(p.parent)
            self._user_selected_path = True

    # ── export orchestration ────────────────────────────────────────────────

    def _fps_value(self) -> int:
        return int(self._fps_combo.currentText().split()[0])

    def _scale_value(self) -> float:
        return int(self._res_combo.currentText().rstrip("%")) / 100.0

    def _set_controls_enabled(self, enabled: bool) -> None:
        for w in (
            self._mp4_btn,
            self._gif_btn,
            self._duration_slider,
            self._fps_combo,
            self._res_combo,
            self._path_edit,
            self._export_btn,
        ):
            w.setEnabled(enabled)

    def _start_export(self) -> None:
        if not self._user_selected_path:
            self._browse_output()
            if not self._user_selected_path:
                return  # User cancelled save file selection dialog

        raw = self._path_edit.text().strip()
        if not raw:
            self._show_error("Please choose an output file path.")
            return

        output_path = Path(raw)
        if not output_path.parent.exists():
            self._show_error(f"Output directory does not exist:\n{output_path.parent}")
            return

        self.last_used_dir = str(output_path.parent)

        self._set_controls_enabled(False)
        self._progress_bar.setValue(0)
        self._progress_label.setText("Preparing…")
        self._progress_widget.show()
        self.adjustSize()

        self._worker = _ExportWorker(
            layers=self._layers,
            duration=float(self._duration_slider.value()),
            fps=self._fps_value(),
            scale=self._scale_value(),
            loop_type=self._motion.loop_type,
            global_intensity=self._motion.global_intensity,
            focus_depth=self._motion.focus_depth,
            fmt=self._fmt,
            output_path=output_path,
            use_gpu=self._use_gpu,
            use_nvenc=self._use_nvenc,
        )
        self._thread = QThread(self)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    @Slot(int, int, str)
    def _on_progress(self, current: int, total: int, label: str) -> None:
        pct = int(current * 100 / max(1, total))
        self._progress_bar.setValue(pct)
        self._progress_label.setText(label)

    @Slot(str)
    def _on_finished(self, output_path: str) -> None:
        self._cleanup_thread()
        self.exportCompleted.emit(output_path)
        self.accept()

    @Slot(str)
    def _on_error(self, message: str) -> None:
        self._cleanup_thread()
        self._set_controls_enabled(True)
        self._progress_widget.hide()
        self.adjustSize()
        self._show_error(f"Export failed:\n{message}")

    def _on_cancel(self) -> None:
        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(3000)
        self._cleanup_thread()
        self.reject()

    def _cleanup_thread(self) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(1000)
            self._thread = None
            self._worker = None

    def _show_error(self, message: str) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Export Error")
        msg.setText(message)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.exec()

    def closeEvent(self, event) -> None:
        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(3000)
        super().closeEvent(event)
