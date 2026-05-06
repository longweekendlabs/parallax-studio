from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QComboBox, QSizePolicy, QFrame, QScrollArea,
)
from PySide6.QtCore import Qt, QSize

from app.ui.theme import (
    C_PANEL_BG, C_RAISED_PANEL, C_ACCENT, C_BORDER, C_BORDER_SOFT,
    C_TEXT_MAIN, C_TEXT_SECONDARY, C_TEXT_MUTED, C_DANGER, C_EXPORT,
)


def _section_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionHeader")
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Plain)
    line.setStyleSheet(f"background: {C_BORDER_SOFT}; max-height: 1px; border: none;")
    return line


def _slider_row(label: str, value: int = 50, mono_suffix: str = "") -> QWidget:
    row = QWidget()
    row.setStyleSheet("background: transparent;")
    layout = QVBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)

    top = QHBoxLayout()
    top.setSpacing(4)
    lbl = QLabel(label)
    lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
    val_lbl = QLabel(f"{value}{mono_suffix}")
    val_lbl.setStyleSheet(
        f"color: {C_ACCENT}; font-size: 11px; "
        f"font-family: 'JetBrains Mono', 'SF Mono', monospace;"
    )
    top.addWidget(lbl)
    top.addStretch()
    top.addWidget(val_lbl)
    layout.addLayout(top)

    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(value)
    slider.setFixedHeight(20)
    layout.addWidget(slider)
    return row


class ControlCard(QWidget):
    """A visually distinct card within the controls panel."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER_SOFT}; border-radius: 8px;"
        )
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(12, 10, 12, 12)
        self._outer.setSpacing(8)

        hdr = QHBoxLayout()
        t = QLabel(title)
        t.setObjectName("sectionHeader")
        hdr.addWidget(t)
        hdr.addStretch()
        self._outer.addLayout(hdr)

        sep = _separator()
        self._outer.addWidget(sep)

        self._content = QVBoxLayout()
        self._content.setSpacing(10)
        self._outer.addLayout(self._content)

    def content(self) -> QVBoxLayout:
        return self._content


def _build_depth_card() -> ControlCard:
    card = ControlCard("DEPTH BRUSH")
    c = card.content()

    for label, val, suffix in [
        ("Brush Size", 40, "px"),
        ("Depth Value", 80, "%"),
        ("Hardness", 60, "%"),
        ("Opacity", 75, "%"),
    ]:
        c.addWidget(_slider_row(label, val, suffix))

    btn_row = QHBoxLayout()
    btn_row.setSpacing(6)
    for text, obj_name, tip in [
        ("Auto Depth", "accentBtn", "Generate depth with AI"),
        ("Clear", "", "Reset depth to mid-grey"),
        ("Invert", "", "Invert depth values"),
        ("Blur", "", "Blur depth map"),
    ]:
        btn = QPushButton(text)
        btn.setToolTip(tip)
        btn.setFixedHeight(26)
        if obj_name:
            btn.setObjectName(obj_name)
        else:
            btn.setStyleSheet(
                f"background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER}; "
                f"color: {C_TEXT_SECONDARY}; border-radius: 4px; font-size: 11px;"
            )
        btn_row.addWidget(btn)
    c.addLayout(btn_row)

    return card


def _build_motion_card() -> ControlCard:
    card = ControlCard("MOTION")
    c = card.content()

    # Motion Style
    style_lbl = QLabel("Motion Style")
    style_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
    c.addWidget(style_lbl)

    style_combo = QComboBox()
    style_combo.addItems([
        "Gentle Float",
        "Horizontal Drift",
        "Vertical Drift",
        "Zoom Breathe",
        "Parallax Orbit",
    ])
    c.addWidget(style_combo)

    # Loop Type — segmented toggle
    loop_lbl = QLabel("Loop Type")
    loop_lbl.setStyleSheet(f"color: {C_TEXT_SECONDARY}; font-size: 12px;")
    c.addWidget(loop_lbl)

    loop_row = QHBoxLayout()
    loop_row.setSpacing(0)
    for i, opt in enumerate(["Seamless", "Bounce"]):
        btn = QPushButton(opt)
        btn.setCheckable(True)
        btn.setChecked(i == 0)
        btn.setFixedHeight(28)
        radius_left = "border-radius: 0; border-top-left-radius: 5px; border-bottom-left-radius: 5px;" if i == 0 else ""
        radius_right = "border-radius: 0; border-top-right-radius: 5px; border-bottom-right-radius: 5px;" if i == 1 else ""
        btn.setStyleSheet(
            f"QPushButton {{ background: {C_RAISED_PANEL}; border: 1px solid {C_BORDER}; "
            f"color: {C_TEXT_SECONDARY}; font-size: 12px; {radius_left}{radius_right} }}"
            f"QPushButton:checked {{ background: {C_ACCENT}22; border-color: {C_ACCENT}; color: {C_ACCENT}; }}"
        )
        loop_row.addWidget(btn)
    c.addLayout(loop_row)

    for label, val, suffix in [
        ("Layer Intensity", 65, "%"),
        ("Global Intensity", 50, "%"),
        ("Speed / Duration", 40, "s"),
        ("Preview FPS", 24, "fps"),
    ]:
        c.addWidget(_slider_row(label, val, suffix))

    return card


class ControlsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self.setMaximumWidth(240)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {C_PANEL_BG};")
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet(f"background: {C_PANEL_BG}; border-bottom: 1px solid {C_BORDER_SOFT};")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 0, 12, 0)
        title = QLabel("CONTROLS")
        title.setObjectName("sectionHeader")
        h_layout.addWidget(title)
        outer.addWidget(header)

        # scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(8, 8, 8, 8)
        content_layout.setSpacing(8)

        content_layout.addWidget(_build_depth_card())
        content_layout.addWidget(_build_motion_card())
        content_layout.addStretch()

        scroll.setWidget(content_widget)
        outer.addWidget(scroll)
