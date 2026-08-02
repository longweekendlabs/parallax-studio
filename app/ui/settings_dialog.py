from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
)

from app.core import depth_model
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

        layout.addWidget(_section("AUTO DEPTH MODEL"))
        self.model_combo = QComboBox()
        for model in depth_model.MODELS:
            suffix = "" if depth_model.is_downloaded(model.id) or not model.filename else "  (not downloaded)"
            self.model_combo.addItem(model.label + suffix, model.id)
        index = self.model_combo.findData(self._settings.depth_model)
        self.model_combo.setCurrentIndex(index if index >= 0 else 0)
        self.model_combo.currentIndexChanged.connect(self._sync_model_hint)
        layout.addWidget(self.model_combo)
        self.model_hint = _hint("")
        layout.addWidget(self.model_hint)
        if not depth_model.is_available():
            self.model_combo.setEnabled(False)
        self._sync_model_hint()

        layout.addSpacing(6)
        layout.addWidget(_rule())
        layout.addSpacing(6)

        layout.addWidget(_section("BODY RELIEF STRENGTH"))
        strength_row = QHBoxLayout()
        self.relief_slider = QSlider(Qt.Orientation.Horizontal)
        # Tenths. Above ~1.3 the figure starts reading as rubbery rather than
        # photographic, but it stays free of tearing across the whole range.
        self.relief_slider.setRange(2, 20)
        self.relief_slider.setValue(
            max(2, min(20, int(round(self._settings.body_relief_strength * 10))))
        )
        self.relief_value = QLabel(f"{self.relief_slider.value() / 10:.1f}")
        self.relief_value.setStyleSheet(
            f"color: {C_TEXT_MAIN}; font-size: 12px; background: transparent;"
        )
        self.relief_slider.valueChanged.connect(
            lambda v: self.relief_value.setText(f"{v / 10:.1f}")
        )
        strength_row.addWidget(self.relief_slider, stretch=1)
        strength_row.addWidget(self.relief_value)
        layout.addLayout(strength_row)
        layout.addWidget(_hint(
            "How far apart Body Relief pushes chest, hips and legs. Higher "
            "separates the parts more; the figure looks less like a photograph "
            "and more like a paper cut-out as it climbs."
        ))

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

    def _sync_model_hint(self):
        model = depth_model.get_model(self.model_combo.currentData())
        text = model.note
        if not depth_model.is_available():
            text = "Unavailable: ONNX Runtime is not installed in this build."
        elif model.filename and not depth_model.is_downloaded(model.id):
            size = model.approx_bytes // 1048576
            text += f"  Downloads once ({size} MB) the first time you press Auto Depth."
        if not model.commercial_ok:
            text += f"  Licence: {model.license}, non-commercial use only."
        self.model_hint.setText(text)

    def _encode_hint(self) -> str:
        if not self._nvenc:
            return "Unavailable: this system's ffmpeg has no h264_nvenc encoder."
        return "Hands H.264 encoding to the GPU instead of the CPU."

    # ── result ──────────────────────────────────────────────────────────────

    def result_settings(self) -> AppSettings:
        """Return the edited settings; call after exec() returns Accepted."""
        # A disabled control reflects missing hardware, not a user choice.
        # Writing its unchecked state would silently turn the feature off for
        # good once the hardware came back.
        if self.gpu_export_check.isEnabled():
            self._settings.gpu_export = self.gpu_export_check.isChecked()
        if self.gpu_encode_check.isEnabled():
            self._settings.gpu_encode = self.gpu_encode_check.isChecked()
        if self.model_combo.isEnabled():
            self._settings.depth_model = self.model_combo.currentData()
        self._settings.body_relief_strength = self.relief_slider.value() / 10.0
        return self._settings
