"""Application preferences.

Laid out as a navigation rail beside a stack of pages, the way Topivo's
settings are, because the single scrolling column this replaced had stopped
working as soon as there was more than a screenful in it: a scrollbar in a
preferences window means the user has to go looking for a setting rather than
seeing where it lives. Each page here is short enough to need no scrolling.

The structure is borrowed. The look is not: this uses Parallax Studio's own
palette and type, and none of Topivo's visual language.
"""
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
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core import depth_model
from app.core.exporter import is_cuda_available, is_nvenc_available
from app.ui.model_panel import ModelPanel
from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_BORDER_SOFT,
    C_PANEL_BG,
    C_RAISED_PANEL,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
    C_WINDOW_BG,
)
from app.utils.settings import AppSettings

NAV_WIDTH = 168


def _caption(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setStyleSheet(
        f"font-size: 9px; font-weight: 700; color: {C_TEXT_MUTED};"
        f" letter-spacing: 1.4px; background: transparent;"
    )
    return label


def _page_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet(
        f"font-size: 15px; font-weight: 600; color: {C_TEXT_MAIN}; background: transparent;"
    )
    return label


def _row(label: str, description: str, control: QWidget, control_width: int = 190) -> QWidget:
    """Name and explanation on the left, the control itself on the right."""
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    outer = QHBoxLayout(row)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(14)

    text = QVBoxLayout()
    text.setSpacing(2)
    name = QLabel(label)
    name.setStyleSheet(
        f"font-size: 12.5px; color: {C_TEXT_MAIN}; font-weight: 500; background: transparent;"
    )
    text.addWidget(name)
    if description:
        hint = QLabel(description)
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"font-size: 10.5px; color: {C_TEXT_MUTED}; background: transparent;"
        )
        text.addWidget(hint)
    outer.addLayout(text, 1)
    control.setFixedWidth(control_width)
    outer.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
    return row


def _rule() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {C_BORDER_SOFT}; border: none;")
    return line


class _NavRow(QPushButton):
    def __init__(self, page_id: str, label: str, on_select):
        super().__init__(label)
        self.page_id = page_id
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.clicked.connect(lambda: on_select(page_id))
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 7px;
                color: {C_TEXT_SECONDARY};
                font-size: 12.5px;
                padding: 0 10px;
                text-align: left;
            }}
            QPushButton:hover {{ background: {C_PANEL_BG}; color: {C_TEXT_MAIN}; }}
            QPushButton:checked {{
                background: {C_RAISED_PANEL};
                color: {C_ACCENT};
                font-weight: 600;
            }}
            """
        )


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None, page: str = "depth"):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setFixedSize(760, 520)
        self._settings = settings
        self._cuda = is_cuda_available()
        self._nvenc = is_nvenc_available()
        self._pages: dict[str, int] = {}
        self._nav: dict[str, _NavRow] = {}
        self._build()
        self._select(page if page in self._pages else "depth")

    # ── build ───────────────────────────────────────────────────────────────

    def _build(self):
        self.setStyleSheet(
            f"""
            QDialog {{ background: {C_WINDOW_BG}; color: {C_TEXT_MAIN}; }}
            QLabel {{ background: transparent; }}
            QCheckBox {{ color: {C_TEXT_MAIN}; font-size: 12.5px; background: transparent; spacing: 8px; }}
            QCheckBox::indicator {{
                width: 16px; height: 16px; border-radius: 4px;
                border: 1px solid {C_BORDER}; background: {C_PANEL_BG};
            }}
            QCheckBox::indicator:checked {{ background: {C_ACCENT}; border-color: {C_ACCENT}; }}
            QCheckBox:disabled {{ color: {C_TEXT_MUTED}; }}
            QComboBox {{
                background: {C_PANEL_BG}; border: 1px solid {C_BORDER};
                border-radius: 6px; color: {C_TEXT_MAIN}; padding: 5px 10px; font-size: 12px;
            }}
            QComboBox:hover {{ border-color: {C_ACCENT}; }}
            QPushButton#footerBtn {{
                background: {C_PANEL_BG}; border: 1px solid {C_BORDER};
                border-radius: 6px; color: {C_TEXT_MAIN}; padding: 6px 18px; font-size: 12.5px;
            }}
            QPushButton#footerBtn:hover {{ border-color: {C_ACCENT}; color: {C_ACCENT}; }}
            """
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_nav())

        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background: {C_WINDOW_BG};")
        body.addWidget(self.stack, 1)
        outer.addLayout(body, 1)

        self._add_page("depth", self._depth_page())
        self._add_page("models", self._models_page())
        self._add_page("hardware", self._hardware_page())

        outer.addWidget(self._build_footer())

    def _build_nav(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("navRail")
        rail.setFixedWidth(NAV_WIDTH)
        rail.setStyleSheet(
            f"QWidget#navRail {{ background: {C_PANEL_BG}; "
            f"border-right: 1px solid {C_BORDER_SOFT}; }}"
        )
        lay = QVBoxLayout(rail)
        lay.setContentsMargins(10, 16, 10, 12)
        lay.setSpacing(2)

        def add(page_id: str, label: str):
            row = _NavRow(page_id, label, self._select)
            self._nav[page_id] = row
            lay.addWidget(row)

        lay.addWidget(_caption("Depth"))
        lay.addSpacing(2)
        add("depth", "Auto Depth")
        lay.addSpacing(14)
        lay.addWidget(_caption("System"))
        lay.addSpacing(2)
        add("models", "Models")
        add("hardware", "Hardware")
        lay.addStretch()
        return rail

    def _build_footer(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            f"background: {C_WINDOW_BG}; border-top: 1px solid {C_BORDER_SOFT};"
        )
        row = QHBoxLayout(bar)
        row.setContentsMargins(22, 12, 22, 14)
        row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.setObjectName("footerBtn")
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        save = QPushButton("Save")
        save.setObjectName("footerBtn")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        row.addWidget(save)
        return bar

    def _page(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(page)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(14)
        lay.addWidget(_page_title(title))
        return page, lay

    def _add_page(self, page_id: str, widget: QWidget):
        self._pages[page_id] = self.stack.addWidget(widget)

    def _select(self, page_id: str):
        self.stack.setCurrentIndex(self._pages[page_id])
        for pid, row in self._nav.items():
            row.setChecked(pid == page_id)

    # ── pages ───────────────────────────────────────────────────────────────

    def _depth_page(self) -> QWidget:
        page, lay = self._page("Auto Depth")

        self.model_combo = QComboBox()
        for model in depth_model.MODELS:
            suffix = "" if depth_model.is_downloaded(model.id) or not model.filename else "  (not downloaded)"
            self.model_combo.addItem(model.label + suffix, model.id)
        index = self.model_combo.findData(self._settings.depth_model)
        self.model_combo.setCurrentIndex(index if index >= 0 else 0)
        self.model_combo.currentIndexChanged.connect(self._sync_model_hint)
        self.model_combo.setEnabled(depth_model.is_available())
        lay.addWidget(_row(
            "Depth model",
            "Estimates how far every pixel is from the camera. Everything else "
            "is built on top of this.",
            self.model_combo, 260,
        ))
        self.model_hint = QLabel()
        self.model_hint.setWordWrap(True)
        self.model_hint.setStyleSheet(
            f"font-size: 11px; color: {C_TEXT_SECONDARY}; background: transparent;"
        )
        lay.addWidget(self.model_hint)
        self._sync_model_hint()
        lay.addStretch()
        return page

    def _models_page(self) -> QWidget:
        page, lay = self._page("Models")
        self.model_panel = ModelPanel()
        lay.addWidget(self.model_panel, 1)
        return page

    def _hardware_page(self) -> QWidget:
        page, lay = self._page("Hardware")

        provider = QLabel(self._provider_text())
        provider.setWordWrap(True)
        provider.setStyleSheet(
            f"font-size: 11.5px; color: {C_TEXT_SECONDARY}; background: transparent;"
        )
        lay.addWidget(_caption("Depth and pose inference"))
        lay.addWidget(provider)
        lay.addWidget(_rule())

        self.gpu_export_check = QCheckBox("")
        self.gpu_export_check.setChecked(self._settings.gpu_export and self._cuda)
        self.gpu_export_check.setEnabled(self._cuda)
        lay.addWidget(_row("GPU export rendering", self._render_hint(),
                           self.gpu_export_check, 30))

        self.gpu_encode_check = QCheckBox("")
        self.gpu_encode_check.setChecked(self._settings.gpu_encode and self._nvenc)
        self.gpu_encode_check.setEnabled(self._nvenc)
        lay.addWidget(_row("GPU video encoding (NVENC)", self._encode_hint(),
                           self.gpu_encode_check, 30))

        lay.addStretch()
        return page

    # ── hints ───────────────────────────────────────────────────────────────

    def _provider_text(self) -> str:
        try:
            import onnxruntime as ort

            available = list(ort.get_available_providers())
        except Exception:
            return "ONNX Runtime is not installed, so Auto Depth, Portrait, Flaunt and Bounce are unavailable."
        if "CUDAExecutionProvider" in available:
            return (
                "Running on CUDA. Auto Depth and the figure motions use the GPU, which "
                "is roughly twice as fast as the CPU on this machine."
            )
        return (
            "Running on the CPU. Installing onnxruntime-gpu would use the "
            "graphics card instead; results are identical either way."
        )

    def _render_hint(self) -> str:
        if not self._cuda:
            return (
                "Unavailable: no CUDA-capable PyTorch found. That is a separate "
                "optional install. Export works on the CPU and produces identical frames."
            )
        return "Renders export frames on the GPU. Output matches the CPU renderer exactly."

    def _encode_hint(self) -> str:
        if not self._nvenc:
            return "Unavailable: this system's ffmpeg has no h264_nvenc encoder."
        return "Hands H.264 encoding to the GPU instead of the CPU."

    def _sync_model_hint(self):
        model = depth_model.get_model(self.model_combo.currentData())
        text = model.note
        if not depth_model.is_available():
            text = "Unavailable: ONNX Runtime is not installed in this build."
        elif model.filename and not depth_model.is_downloaded(model.id):
            text += f"  Downloads once ({model.approx_bytes // 1048576} MB) on first use."
        if not model.commercial_ok:
            text += f"  Licence: {model.license}, non-commercial use only."
        self.model_hint.setText(text)

    # ── result ──────────────────────────────────────────────────────────────

    def result_settings(self) -> AppSettings:
        """Return the edited settings; call after exec() returns Accepted."""
        # A disabled control reflects missing hardware, not a user choice.
        if self.gpu_export_check.isEnabled():
            self._settings.gpu_export = self.gpu_export_check.isChecked()
        if self.gpu_encode_check.isEnabled():
            self._settings.gpu_encode = self.gpu_encode_check.isChecked()
        if self.model_combo.isEnabled():
            self._settings.depth_model = self.model_combo.currentData()
        return self._settings
