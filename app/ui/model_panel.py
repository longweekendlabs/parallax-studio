"""The model catalogue, as a widget rather than a window of its own.

Which models are installed is a setting, not an errand, so it lives on a
Settings page beside everything else. The same widget is reused by the
first-run prompt, which is the one case where a separate window is right:
there, downloading is the entire point of the window being open.

Files already fetched by another Long Weekend Labs app are found where they
sit and reported as shared, so the same weights are never downloaded twice.
"""
from __future__ import annotations

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import body_model, depth_model, face_parser
from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_BORDER_SOFT,
    C_PANEL_BG,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
)
from app.utils.paths import models_dir


def catalogue() -> list[tuple[str, tuple]]:
    """Every model the app can use, grouped by what it is for."""
    return [
        ("Depth", tuple(m for m in depth_model.MODELS if m.filename)),
        ("Body Relief", (body_model.SEGMENT_MODEL,) + body_model.POSE_MODELS),
        ("Face and hair", (face_parser.FACE_PARSER,)),
    ]


def all_models() -> list:
    seen, out = set(), []
    for _, group in catalogue():
        for model in group:
            if model.filename and model.filename not in seen:
                seen.add(model.filename)
                out.append(model)
    return out


def missing_models() -> list:
    return [m for m in all_models() if not depth_model.has_file(m)]


def essential_missing(settings) -> list:
    """The models the two depth buttons actually need to work.

    The alternative depth checkpoints are choices, not requirements, so
    nagging about them on every launch would only train the prompt to be
    dismissed unread.
    """
    needed = (
        depth_model.get_model(getattr(settings, "depth_model", "")),
        body_model.SEGMENT_MODEL,
        body_model.pose_spec(getattr(settings, "pose_model", body_model.DEFAULT_POSE)).model,
        face_parser.FACE_PARSER,
    )
    return [m for m in needed if m.filename and not depth_model.has_file(m)]


class _Worker(QThread):
    progress = Signal(str, int, int)
    one_done = Signal(str)
    finished_all = Signal()
    failed = Signal(str)

    def __init__(self, models: list):
        super().__init__()
        self._models = models
        self._stop = False

    def cancel(self):
        self._stop = True

    def run(self):
        try:
            for model in self._models:
                if self._stop:
                    break
                depth_model.ensure_file(
                    model,
                    progress_cb=lambda d, t, m=model: self.progress.emit(m.label, d, t),
                    cancelled_cb=lambda: self._stop,
                )
                self.one_done.emit(model.filename)
            self.finished_all.emit()
        except InterruptedError:
            self.finished_all.emit()
        except Exception as exc:  # network, disk, permissions
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ModelPanel(QWidget):
    """List of every model with its state, plus a download control."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: dict[str, QLabel] = {}
        self._worker: _Worker | None = None
        self._build()
        self.refresh()

    def _build(self):
        self.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        where = QLabel(f"Downloads go to  {models_dir()}")
        where.setWordWrap(True)
        where.setStyleSheet(
            f"font-size: 10.5px; color: {C_TEXT_MUTED}; background: transparent;"
        )
        lay.addWidget(where)
        lay.addSpacing(2)

        for heading, group in catalogue():
            caption = QLabel(heading.upper())
            caption.setStyleSheet(
                f"font-size: 9px; font-weight: 700; color: {C_TEXT_MUTED};"
                f" letter-spacing: 1.4px; background: transparent;"
            )
            lay.addWidget(caption)
            for model in group:
                if not model.filename:
                    continue
                row = QLabel()
                row.setWordWrap(True)
                row.setStyleSheet("font-size: 11.5px; background: transparent;")
                self._rows[model.filename] = row
                lay.addWidget(row)
            lay.addSpacing(6)

        lay.addStretch()

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(16)
        self.progress.setVisible(False)
        self.progress.setStyleSheet(
            f"""
            QProgressBar {{
                background: {C_PANEL_BG}; border: 1px solid {C_BORDER};
                border-radius: 5px; text-align: center;
                color: {C_TEXT_SECONDARY}; font-size: 10px;
            }}
            QProgressBar::chunk {{ background: {C_ACCENT}; border-radius: 4px; }}
            """
        )
        lay.addWidget(self.progress)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            f"font-size: 11px; color: {C_TEXT_SECONDARY}; background: transparent;"
        )
        row.addWidget(self.status, 1)
        self.download_button = QPushButton("Download missing")
        self.download_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.download_button.setStyleSheet(
            f"""
            QPushButton {{
                background: {C_PANEL_BG}; border: 1px solid {C_BORDER};
                border-radius: 6px; color: {C_TEXT_MAIN}; padding: 6px 14px; font-size: 12px;
            }}
            QPushButton:hover {{ border-color: {C_ACCENT}; color: {C_ACCENT}; }}
            QPushButton:disabled {{ color: {C_TEXT_MUTED}; border-color: {C_BORDER_SOFT}; }}
            """
        )
        self.download_button.clicked.connect(self.start_download)
        row.addWidget(self.download_button)
        lay.addLayout(row)

    # ── state ───────────────────────────────────────────────────────────────

    def refresh(self):
        own = models_dir()
        for model in all_models():
            row = self._rows.get(model.filename)
            if row is None:
                continue
            if depth_model.has_file(model):
                path = depth_model.file_path(model)
                shared = path is not None and path.parent != own
                mark, colour = "✓", C_ACCENT
                where = f"shared from {path.parent}" if shared else "installed"
            else:
                mark, colour = "○", C_TEXT_MUTED
                where = f"not downloaded, {model.approx_bytes / 1048576:.0f} MB"
            licence = model.license if model.commercial_ok else f"{model.license}, non-commercial"
            row.setText(
                f"<span style='color:{colour}'>{mark}</span> "
                f"<span style='color:{C_TEXT_MAIN}'>{model.label}</span>"
                f"<span style='color:{C_TEXT_MUTED}'>&nbsp;&nbsp;{where} &middot; {licence}</span>"
            )

        pending = missing_models()
        total = sum(m.approx_bytes for m in pending) / 1048576
        self.download_button.setEnabled(bool(pending))
        if pending:
            self.download_button.setText(f"Download {len(pending)} ({total:.0f} MB)")
            self.status.setText("")
        else:
            self.download_button.setText("All installed")
            self.status.setText("Everything is present. Auto Depth and Body Relief are ready.")
        self.changed.emit()

    # ── download ────────────────────────────────────────────────────────────

    def start_download(self):
        pending = missing_models()
        if not pending or self.is_busy():
            return
        self.download_button.setEnabled(False)
        self.progress.setVisible(True)
        self._worker = _Worker(pending)
        self._worker.progress.connect(self._on_progress)
        self._worker.one_done.connect(lambda _: self.refresh())
        self._worker.finished_all.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def cancel(self):
        if self.is_busy():
            self._worker.cancel()
            self._worker.wait(3000)
            self._on_done()

    def _on_progress(self, label: str, done: int, total: int):
        if total > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(done * 100 / total))
            self.progress.setFormat(
                f"{label}  {done / 1048576:.0f} / {total / 1048576:.0f} MB"
            )
        else:
            self.progress.setRange(0, 0)
            self.progress.setFormat(label)

    def _on_done(self):
        self.progress.setVisible(False)
        self._worker = None
        self.refresh()

    def _on_failed(self, message: str):
        self.progress.setVisible(False)
        self._worker = None
        self.status.setText(f"Download failed: {message}")
        self.refresh()
