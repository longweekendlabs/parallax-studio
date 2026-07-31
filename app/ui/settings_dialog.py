from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.core.exporter import is_cuda_available, is_nvenc_available
from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_PANEL_BG,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
    C_WINDOW_BG,
)
from app.utils.settings import AppSettings


def _section(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"color: {C_TEXT_MUTED}; font-size: 10px; font-weight: 700; "
        f"letter-spacing: 1.5px; background: transparent;"
    )
    return label


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 11px; background: transparent;")
    return label


def _rule() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {C_BORDER}; border: none;")
    return line


class SettingsDialog(QDialog):
    """Application preferences. Hardware acceleration is opt-in."""

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setFixedWidth(470)
        self._settings = settings
        self._cuda = is_cuda_available()
        self._nvenc = is_nvenc_available()
        self._build()

    # ── build ───────────────────────────────────────────────────────────────

    def _build(self):
        self.setStyleSheet(
            f"""
            QDialog {{ background: {C_WINDOW_BG}; color: {C_TEXT_MAIN}; }}
            QLabel {{ background: transparent; }}
            QCheckBox {{ color: {C_TEXT_MAIN}; font-size: 13px; background: transparent; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px; border-radius: 4px;
                border: 1px solid {C_BORDER}; background: {C_PANEL_BG};
            }}
            QCheckBox::indicator:checked {{ background: {C_ACCENT}; border-color: {C_ACCENT}; }}
            QCheckBox:disabled {{ color: {C_TEXT_MUTED}; }}
            QPushButton {{
                background: {C_PANEL_BG}; border: 1px solid {C_BORDER}; border-radius: 6px;
                color: {C_TEXT_MAIN}; padding: 6px 16px;
            }}
            QPushButton:hover {{ border-color: {C_ACCENT}; color: {C_ACCENT}; }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(10)

        layout.addWidget(_section("HARDWARE ACCELERATION"))

        self.gpu_export_check = QCheckBox("Use GPU for rendering export frames")
        self.gpu_export_check.setChecked(self._settings.gpu_export and self._cuda)
        self.gpu_export_check.setEnabled(self._cuda)
        layout.addWidget(self.gpu_export_check)
        layout.addWidget(_hint(self._render_hint()))

        layout.addSpacing(4)
        self.gpu_encode_check = QCheckBox("Use GPU video encoder (NVENC) when available")
        self.gpu_encode_check.setChecked(self._settings.gpu_encode and self._nvenc)
        self.gpu_encode_check.setEnabled(self._nvenc)
        layout.addWidget(self.gpu_encode_check)
        layout.addWidget(_hint(self._encode_hint()))

        layout.addSpacing(6)
        layout.addWidget(_rule())
        layout.addSpacing(6)
        layout.addWidget(_hint(
            "Preview frame rate lives with the other motion controls in the "
            "right-hand panel."
        ))

        layout.addSpacing(10)
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        save = QPushButton("Save")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    # ── hints ───────────────────────────────────────────────────────────────

    def _render_hint(self) -> str:
        if not self._cuda:
            return (
                "Unavailable: no CUDA-capable PyTorch found. This is an optional "
                "~4GB install and is not bundled with the app. Export still works "
                "on the CPU and produces identical frames."
            )
        return (
            "Roughly 9x faster frame rendering on this machine. Output is "
            "identical to the CPU renderer. Projects using scaled or offset "
            "layers fall back to the CPU automatically."
        )

    def _encode_hint(self) -> str:
        if not self._nvenc:
            return "Unavailable: this system's ffmpeg has no h264_nvenc encoder."
        return "Hands H.264 encoding to the GPU instead of the CPU."

    # ── result ──────────────────────────────────────────────────────────────

    def result_settings(self) -> AppSettings:
        """Return the edited settings; call after exec() returns Accepted."""
        self._settings.gpu_export = self.gpu_export_check.isChecked() and self._cuda
        self._settings.gpu_encode = self.gpu_encode_check.isChecked() and self._nvenc
        return self._settings
