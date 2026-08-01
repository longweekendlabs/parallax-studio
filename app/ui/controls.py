from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_PANEL_BG,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
)


def _speed_from_slider(value: int) -> float:
    """Slider 0-100 -> 0.25x .. 3.00x. 27 is 1.00x, the concept default."""
    return 0.25 + (value / 100.0) * 2.75


def _slider_from_speed(speed: float) -> int:
    return max(0, min(100, int(round((speed - 0.25) / 2.75 * 100))))


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"background: transparent; color: {C_TEXT_SECONDARY}; font-size: 14px;")
    return lbl


def _value(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFixedSize(76, 34)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(
        f"""
        QLabel {{
            background: #0D141B;
            border: 1px solid {C_BORDER};
            border-radius: 7px;
            color: {C_TEXT_MAIN};
            font-family: 'JetBrains Mono', 'SF Mono', monospace;
            font-size: 14px;
        }}
        """
    )
    return lbl


def _set_tooltip_tree(widget: QWidget, text: str):
    widget.setToolTip(text)
    for child in widget.findChildren(QWidget):
        child.setToolTip(text)


@dataclass(frozen=True)
class BrushSettings:
    # Matches the concept image and the slider defaults in ControlsPanel.
    size: int = 128
    depth_value: float = 0.45
    hardness: float = 0.65
    opacity: float = 1.0
    erase: bool = False


@dataclass(frozen=True)
class MotionSettings:
    motion_scale_x: float = 1.0
    motion_scale_y: float = 1.0
    zoom_strength: float = 0.35
    loop_type: str = "Seamless Loop"
    movement_strength: float = 1.0
    focus_depth: float = 0.5
    layer_intensity: float = 0.65
    global_intensity: float = 0.75
    duration: float = 4.0
    preview_fps: int = 24


class EmbeddedSlider(QWidget):
    valueChanged = Signal(int)

    def __init__(
        self,
        value: int,
        left_text: str,
        center_text: str,
        right_text: str,
        minimum: int = 0,
        maximum: int = 100,
        path_shape_getter=None,
        magnetic_center: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._value = value
        self.left_text = left_text
        self.center_text = center_text
        self.right_text = right_text
        self.path_shape_getter = path_shape_getter
        self.magnetic_center = magnetic_center
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("background: transparent;")

    def value(self) -> int:
        return self._value

    def setValue(self, value: int, emit: bool = True):
        value = max(self._minimum, min(self._maximum, int(value)))
        if value == self._value:
            return
        self._value = value
        self.update()
        if emit:
            self.valueChanged.emit(self._value)

    def _percent(self) -> float:
        span = max(1, self._maximum - self._minimum)
        return (self._value - self._minimum) / span

    def _track_rect(self) -> QRectF:
        return QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)

    def _side_margin(self) -> float:
        return min(74.0, max(52.0, self._track_rect().width() * 0.22))

    def _handle_x(self) -> float:
        track = self._track_rect()
        margin = self._side_margin()
        return track.left() + margin + self._percent() * max(1.0, track.width() - margin * 2)

    def _event_to_value(self, x: float) -> int:
        track = self._track_rect()
        margin = self._side_margin()
        start = track.left() + margin
        width = max(1.0, track.width() - margin * 2)
        percent = max(0.0, min(1.0, (x - start) / width))
        return round(self._minimum + percent * (self._maximum - self._minimum))

    def _apply_magnetic(self, raw: int) -> int:
        if not self.magnetic_center:
            return raw
        center = (self._minimum + self._maximum) // 2
        if abs(raw - center) <= (self._maximum - self._minimum) * 0.03:
            return center
        return raw

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setValue(self._apply_magnetic(self._event_to_value(event.position().x())))

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.setValue(self._apply_magnetic(self._event_to_value(event.position().x())))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = self._track_rect()
        painter.setPen(QPen(QColor("#030607"), 1))
        painter.setBrush(QColor("#070A0D"))
        painter.drawRoundedRect(track, 3, 3)

        handle_x = self._handle_x()

        if self.magnetic_center:
            margin = self._side_margin()
            cx = track.left() + margin + 0.5 * max(1.0, track.width() - margin * 2)
            at_center = self._value == (self._minimum + self._maximum) // 2
            tick_color = "#3DD9C9" if at_center else "#3DD9C948"
            tick_width = 2 if at_center else 1
            painter.setPen(QPen(QColor(tick_color), tick_width))
            painter.drawLine(QPointF(cx, track.top() + 3), QPointF(cx, track.bottom() - 3))

        active_rect = QRectF(handle_x - 34, track.top(), 68, track.height())
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#1A1D1F"))
        painter.drawRect(active_rect.intersected(track))

        center_y = track.center().y()
        painter.setPen(QPen(QColor("#BFC8C8"), 2))
        if self.path_shape_getter is not None:
            scale_x, scale_y = self.path_shape_getter()
            rx = max(1.8, min(10.0, scale_x * 10.0))
            ry = max(1.8, min(10.0, scale_y * 10.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QRectF(handle_x - rx, center_y - ry, rx * 2, ry * 2))
        else:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#C7CECE"))
            painter.drawEllipse(QRectF(handle_x - 5, center_y - 5, 10, 10))

        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        painter.setPen(QColor(C_TEXT_MUTED))
        text_rect = track.adjusted(10, 0, -10, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, self.left_text)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignHCenter, self.center_text)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignRight, self.right_text)
        painter.end()


class RangeStepper(QWidget):
    changed = Signal()

    def __init__(
        self,
        label: str,
        values: list[tuple[str, object]],
        selected_index: int,
        formatter=None,
        path_preview: bool = False,
        magnetic_center: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.values = values
        self.formatter = formatter or self._default_formatter
        self.path_preview = path_preview
        self.setStyleSheet("background: transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.slider = EmbeddedSlider(
            self._index_to_slider_value(selected_index),
            str(values[0][0]),
            label,
            str(values[-1][0]),
            minimum=0,
            maximum=1000,
            path_shape_getter=self.value if path_preview else None,
            magnetic_center=magnetic_center,
        )
        self.slider.valueChanged.connect(self._update_value)
        col.addWidget(self.slider)

    def _index_to_slider_value(self, index: int) -> int:
        return int(index / max(1, len(self.values) - 1) * 1000)

    def _position(self) -> float:
        return self.slider.value() / 1000 * max(1, len(self.values) - 1)

    def _interpolate(self, left, right, t: float):
        if isinstance(left, tuple) and isinstance(right, tuple):
            return tuple(self._interpolate(a, b, t) for a, b in zip(left, right))
        return left + (right - left) * t

    def _interpolated_value(self):
        pos = self._position()
        left_i = int(pos)
        right_i = min(len(self.values) - 1, left_i + 1)
        t = pos - left_i
        left = self.values[left_i][1]
        right = self.values[right_i][1]
        if left_i == right_i:
            return left
        return self._interpolate(left, right, t)

    def _default_formatter(self, value) -> str:
        if isinstance(value, tuple):
            return f"{value[0]:.2f} × {value[1]:.2f}"
        if isinstance(value, float):
            return f"{value:.2f}"
        return str(value)

    def set_index(self, index: int, emit: bool = False):
        self.slider.setValue(self._index_to_slider_value(index), emit=emit)

    def set_value(self, value, emit: bool = False):
        closest = 0
        best = float("inf")
        for i, (_, candidate) in enumerate(self.values):
            if isinstance(candidate, tuple) and isinstance(value, tuple):
                dist = sum((a - b) ** 2 for a, b in zip(candidate, value)) ** 0.5
            elif isinstance(candidate, (int, float)) and isinstance(value, (int, float)):
                dist = abs(float(candidate) - float(value))
            elif candidate == value:
                dist = 0.0
            else:
                continue
            if dist < best:
                best = dist
                closest = i
        self.set_index(closest, emit=emit)

    def _update_value(self, slider_value: int, emit: bool = True):
        self.slider.update()
        if emit:
            self.changed.emit()

    def value(self):
        return self._interpolated_value()


class LoopButtons(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = "Seamless Loop"
        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.seamless = QPushButton("Seamless")
        self.bounce = QPushButton("Bounce")
        self.seamless.setToolTip("Use for final looping exports. Motion wraps back to the first frame without a visible stop.")
        self.bounce.setToolTip("Use while inspecting depth. Motion goes out and back, which makes warping easier to spot.")
        for button in [self.seamless, self.bounce]:
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(30)
            row.addWidget(button)
        self.seamless.clicked.connect(lambda: self._set_value("Seamless Loop"))
        self.bounce.clicked.connect(lambda: self._set_value("Bounce"))
        self._sync()

    def _style(self, checked: bool) -> str:
        if checked:
            return f"""
                QPushButton {{
                    background: {C_ACCENT}22;
                    border: 1px solid {C_ACCENT};
                    border-radius: 7px;
                    color: {C_ACCENT};
                    font-size: 12px;
                }}
            """
        return f"""
            QPushButton {{
                background: #0D141B;
                border: 1px solid {C_BORDER};
                border-radius: 7px;
                color: {C_TEXT_SECONDARY};
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {C_ACCENT};
                color: {C_TEXT_MAIN};
            }}
        """

    def _set_value(self, value: str):
        self._value = value
        self._sync()
        self.changed.emit()

    def _sync(self):
        seamless = self._value == "Seamless Loop"
        self.seamless.setChecked(seamless)
        self.bounce.setChecked(not seamless)
        self.seamless.setStyleSheet(self._style(seamless))
        self.bounce.setStyleSheet(self._style(not seamless))

    def value(self) -> str:
        return self._value


class SliderRow(QWidget):
    valueChanged = Signal()

    def __init__(
        self,
        label: str,
        value: int,
        formatter,
        left_text: str = "Low",
        right_text: str = "High",
        minimum: int = 0,
        maximum: int = 100,
        magnetic_center: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.formatter = formatter
        self.setStyleSheet("background: transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        self.slider = EmbeddedSlider(
            value, left_text, label, right_text,
            minimum=minimum, maximum=maximum,
            magnetic_center=magnetic_center,
        )
        self.slider.valueChanged.connect(self._update_value)
        col.addWidget(self.slider)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, value: int, emit: bool = False):
        self.slider.blockSignals(not emit)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        if emit:
            self.valueChanged.emit()

    def _update_value(self, value: int):
        self.valueChanged.emit()


class SimpleSliderRow(QWidget):
    valueChanged = Signal()

    def __init__(self, label: str, value: int, formatter, parent=None):
        super().__init__(parent)
        self.formatter = formatter
        self.setStyleSheet("background: transparent;")
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(_label(label))
        top.addStretch()
        self.value_label = _value(formatter(value))
        top.addWidget(self.value_label)
        col.addLayout(top)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(value)
        self.slider.setFixedHeight(14)
        self.slider.valueChanged.connect(self._update_value)
        col.addWidget(self.slider)

    def value(self) -> int:
        return self.slider.value()

    def set_value(self, value: int, emit: bool = False):
        self.slider.blockSignals(not emit)
        self.slider.setValue(int(value))
        self.slider.blockSignals(False)
        # blockSignals suppresses _update_value, so refresh the readout here.
        self.value_label.setText(self.formatter(self.slider.value()))

    def _update_value(self, value: int):
        self.value_label.setText(self.formatter(value))
        self.valueChanged.emit()


class DropdownRow(QWidget):
    """Label on the left, dark dropdown on the right, as in the concept."""

    changed = Signal()

    def __init__(self, label: str, choices: list[tuple[str, object]], index: int = 0, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(_label(label))
        row.addStretch()

        self.combo = QComboBox()
        self.combo.setFixedHeight(30)
        self.combo.setMinimumWidth(148)
        self.combo.setCursor(Qt.PointingHandCursor)
        for text, payload in choices:
            self.combo.addItem(text, payload)
        self.combo.setCurrentIndex(index)
        self.combo.setStyleSheet(
            f"""
            QComboBox {{
                background: #0D141B;
                border: 1px solid {C_BORDER};
                border-radius: 7px;
                color: {C_TEXT_MAIN};
                font-size: 13px;
                padding: 4px 10px;
            }}
            QComboBox:hover {{ border-color: {C_ACCENT}; }}
            QComboBox::drop-down {{ border: none; width: 22px; }}
            QComboBox QAbstractItemView {{
                background: #0D141B;
                border: 1px solid {C_BORDER};
                color: {C_TEXT_MAIN};
                selection-background-color: {C_ACCENT};
                selection-color: #06231F;
                outline: none;
            }}
            """
        )
        self.combo.currentIndexChanged.connect(lambda _i: self.changed.emit())
        row.addWidget(self.combo)

    def value(self):
        return self.combo.currentData()

    def set_value(self, payload, emit: bool = False):
        # findData compares through QVariant and does not reliably match Python
        # tuples, so compare the stored payloads directly.
        index = -1
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == payload:
                index = i
                break
        if index < 0:
            return
        self.combo.blockSignals(not emit)
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        if emit:
            self.changed.emit()


def _slider_row(label: str, value: int, display: str) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    col = QVBoxLayout(w)
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(4)

    top = QHBoxLayout()
    top.addWidget(_label(label))
    top.addStretch()
    top.addWidget(_value(display))
    col.addLayout(top)

    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(value)
    slider.setFixedHeight(14)
    col.addWidget(slider)
    return w


def _compact_value_row(label: str, display: str) -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(_label(label))
    row.addStretch()
    row.addWidget(_value(display))
    return w


class Card(QFrame):
    def __init__(self, icon: str, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("controlCard")
        self.setStyleSheet(
            f"""
            QFrame#controlCard {{
                background: {C_PANEL_BG};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
            """
        )
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 16, 20, 16)
        self.layout.setSpacing(10)

        header = QHBoxLayout()
        mark = QLabel(icon)
        mark.setStyleSheet(f"background: transparent; color: {C_ACCENT}; font-size: 22px;")
        lbl = QLabel(title)
        lbl.setStyleSheet(f"background: transparent; color: {C_TEXT_MAIN}; font-size: 18px; font-weight: 650;")
        chevron = QLabel("^")
        chevron.setStyleSheet(f"background: transparent; color: {C_TEXT_SECONDARY}; font-size: 18px;")
        header.addWidget(mark)
        header.addWidget(lbl)
        header.addStretch()
        header.addWidget(chevron)
        self.layout.addLayout(header)


class SmallAction(QPushButton):
    def __init__(self, text: str, accent: bool = False, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(30)
        self.setCursor(Qt.PointingHandCursor)
        fg = C_ACCENT if accent else C_TEXT_SECONDARY
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: #0D141B;
                border: 1px solid {C_BORDER};
                border-radius: 7px;
                color: {fg};
                font-size: 12px;
            }}
            QPushButton:hover {{
                border-color: {C_ACCENT};
                color: {C_ACCENT};
            }}
            QPushButton:checked {{
                background: {C_ACCENT}22;
                border-color: {C_ACCENT};
                color: {C_ACCENT};
            }}
            QPushButton:disabled {{
                background: #0B1117;
                border-color: #1A252E;
                color: {C_TEXT_MUTED};
            }}
            """
        )


class ControlsPanel(QWidget):
    brushSettingsChanged = Signal(BrushSettings)
    motionSettingsChanged = Signal(MotionSettings)
    clearDepthRequested = Signal()
    invertDepthRequested = Signal()
    blurDepthRequested = Signal()
    autoDepthRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(330)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            f"""
            QScrollArea {{
                border: none;
                background: transparent;
            }}
            QScrollBar:vertical {{
                background: #0B1014;
                width: 8px;
                border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {C_BORDER};
                border-radius: 4px;
                min-height: 32px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
                background: transparent;
            }}
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {{
                background: transparent;
            }}
            """
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        col = QVBoxLayout(content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(12)

        # Not shown in the panel: focus stays neutral (the concept has no
        # control for it) and preview fps lives with the other app preferences.
        self._focus_depth = 0.5
        self._preview_fps = 24

        depth = Card("⌁", "DEPTH BRUSH")
        # Defaults come from the concept image (Size 128, Depth 0.45,
        # Hardness 65%, Opacity 100%). The previous 10% strength moved depth so
        # little per pass that strokes were invisible in the paint overlay.
        self.brush_size = SimpleSliderRow("Brush Size", 58, lambda v: str(max(4, int(v * 2.2))))
        self.depth_value = SimpleSliderRow("Depth Value", 45, lambda v: f"{v / 100:.2f}")
        self.hardness = SimpleSliderRow("Hardness", 65, lambda v: f"{v}%")
        self.opacity = SimpleSliderRow("Opacity", 100, lambda v: f"{v}%")
        _set_tooltip_tree(
            self.brush_size,
            "Width of each depth stroke. Use smaller strokes around object edges; reserve large strokes for broad foreground or background areas."
        )
        _set_tooltip_tree(
            self.depth_value,
            "Depth painted by the brush. 0.50 is neutral, higher comes toward the viewer, lower moves away. The default is close to neutral so one stroke stays subtle."
        )
        _set_tooltip_tree(
            self.hardness,
            "Brush edge falloff. Low values blend into the existing depth map; high values make sharp cutouts that often warp during motion."
        )
        _set_tooltip_tree(
            self.opacity,
            "How much one pass changes depth. Keep this low and build depth with repeated strokes for smoother parallax."
        )
        for row in [self.brush_size, self.depth_value, self.hardness, self.opacity]:
            row.valueChanged.connect(self._emit_brush_settings)
            depth.layout.addWidget(row)

        mode_row = QHBoxLayout()
        mode_row.setContentsMargins(0, 0, 0, 0)
        mode_row.setSpacing(8)
        self.paint_mode_button = SmallAction("Paint", True)
        self.erase_mode_button = SmallAction("Erase")
        for button in [self.paint_mode_button, self.erase_mode_button]:
            button.setCheckable(True)
            mode_row.addWidget(button)
        self.paint_mode_button.setChecked(True)
        self.paint_mode_button.setToolTip("Paint the selected depth value onto the layer.")
        self.erase_mode_button.setToolTip(
            "Erase depth paint by brushing back toward neutral 0.50. Erase uses a stronger stroke than Paint so mistakes clear quickly."
        )
        self.paint_mode_button.clicked.connect(lambda: self._set_brush_mode(False))
        self.erase_mode_button.clicked.connect(lambda: self._set_brush_mode(True))
        depth.layout.addLayout(mode_row)

        buttons = QGridLayout()
        buttons.setHorizontalSpacing(8)
        buttons.setVerticalSpacing(8)
        self.auto_depth_button = SmallAction("Auto Depth", True)
        self.auto_depth_button.setToolTip(
            "Generate a starter depth map from the selected image. This is editable and undoable, not final AI depth."
        )
        self.clear_depth_button = SmallAction("Clear Depth")
        self.invert_depth_button = SmallAction("Invert")
        self.blur_depth_button = SmallAction("Soften Once")
        self.clear_depth_button.setToolTip(
            "Return the selected layer to flat 0.50 depth. Parallax motion will pause until the layer has depth variation again."
        )
        self.invert_depth_button.setToolTip(
            "Swap near and far values on the selected layer. Use this when the foreground and background move backwards."
        )
        self.blur_depth_button.setToolTip(
            "Apply one undoable blur pass to the selected depth map. This is not an on/off toggle; repeated clicks keep softening."
        )
        self.clear_depth_button.clicked.connect(self.clearDepthRequested.emit)
        self.invert_depth_button.clicked.connect(self.invertDepthRequested.emit)
        self.blur_depth_button.clicked.connect(self.blurDepthRequested.emit)
        self.auto_depth_button.clicked.connect(self.autoDepthRequested.emit)
        for i, button in enumerate([
            self.auto_depth_button,
            self.clear_depth_button,
            self.invert_depth_button,
            self.blur_depth_button,
        ]):
            buttons.addWidget(button, i // 2, i % 2)
        depth.layout.addLayout(buttons)
        col.addWidget(depth)

        motion = Card("≈", "MOTION")
        self.motion_notice = QLabel("Open an image and paint subtle depth variation to enable parallax motion.")
        self.motion_notice.setWordWrap(True)
        self.motion_notice.setStyleSheet(
            f"""
            QLabel {{
                background: #0D141B;
                border: 1px solid {C_BORDER};
                border-radius: 7px;
                color: {C_TEXT_SECONDARY};
                font-size: 12px;
                padding: 8px 10px;
            }}
            """
        )
        motion.layout.addWidget(self.motion_notice)
        # The concept image defines exactly four motion controls: Motion Style,
        # Loop Type, Layer Intensity and Speed. The panel had grown to nine
        # rows, three of which (movement / layer / global) multiplied into a
        # single number and produced pixel-identical output for any combination
        # with the same product.
        self.motion_style = DropdownRow(
            "Motion Style",
            [
                ("Parallax Orbit", ("orbit", 1.0, 1.0, 0.35)),
                ("Horizontal Drift", ("horizontal", 1.0, 0.0, 0.0)),
                ("Vertical Drift", ("vertical", 0.0, 1.0, 0.0)),
                ("Zoom Breathe", ("zoom", 0.35, 0.35, 0.9)),
            ],
            0,
        )
        _set_tooltip_tree(
            self.motion_style,
            "Shape of the camera move. Parallax Orbit combines side-to-side and vertical drift with a little push-in.",
        )
        self.motion_style.changed.connect(self._emit_motion_settings)
        motion.layout.addWidget(self.motion_style)

        self.loop_type = DropdownRow(
            "Loop Type",
            [("Seamless Loop", "Seamless Loop"), ("Bounce", "Bounce")],
            0,
        )
        _set_tooltip_tree(
            self.loop_type,
            "Seamless wraps cleanly for export; Bounce moves out and back, which is easier for inspecting depth problems.",
        )
        self.loop_type.changed.connect(self._emit_motion_settings)
        motion.layout.addWidget(self.loop_type)

        self.layer_intensity = SimpleSliderRow("Layer Intensity", 65, lambda v: f"{v / 100:.2f}")
        _set_tooltip_tree(
            self.layer_intensity,
            "How far the image travels. This is the single motion amount: the old movement, layer and global sliders all multiplied into this one value.",
        )
        self.layer_intensity.valueChanged.connect(self._emit_motion_settings)
        motion.layout.addWidget(self.layer_intensity)

        self.speed = SimpleSliderRow("Speed", 27, lambda v: f"{_speed_from_slider(v):.2f}x")
        _set_tooltip_tree(
            self.speed,
            "Loop playback rate. 1.00x is a four second loop; higher is faster.",
        )
        self.speed.valueChanged.connect(self._emit_motion_settings)
        motion.layout.addWidget(self.speed)

        col.addWidget(motion)
        self.motion_widgets = [
            self.motion_style,
            self.loop_type,
            self.layer_intensity,
            self.speed,
        ]
        self.motion_tooltips = {
            self.motion_style: "Shape of the camera move. Parallax Orbit combines side-to-side and vertical drift with a little push-in.",
            self.loop_type: "Seamless wraps cleanly for export; Bounce moves out and back, which is easier for inspecting depth problems.",
            self.layer_intensity: "How far the image travels. This is the single motion amount.",
            self.speed: "Loop playback rate. 1.00x is a four second loop; higher is faster.",
        }

        col.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.set_motion_ready(False, False)
        self._emit_brush_settings()
        self._emit_motion_settings()

    def brush_settings(self) -> BrushSettings:
        return BrushSettings(
            size=max(4, int(self.brush_size.value() * 2.2)),
            depth_value=self.depth_value.value() / 100,
            hardness=self.hardness.value() / 100,
            opacity=self.opacity.value() / 100,
            erase=self.erase_mode_button.isChecked(),
        )

    def _emit_brush_settings(self):
        self.brushSettingsChanged.emit(self.brush_settings())

    def _set_brush_mode(self, erase: bool):
        self.erase_mode_button.blockSignals(True)
        self.paint_mode_button.blockSignals(True)
        self.erase_mode_button.setChecked(erase)
        self.paint_mode_button.setChecked(not erase)
        self.erase_mode_button.blockSignals(False)
        self.paint_mode_button.blockSignals(False)
        self._emit_brush_settings()

    def motion_settings(self) -> MotionSettings:
        _name, scale_x, scale_y, zoom = self.motion_style.value()
        speed = _speed_from_slider(self.speed.value())
        return MotionSettings(
            motion_scale_x=scale_x,
            motion_scale_y=scale_y,
            zoom_strength=zoom,
            loop_type=self.loop_type.value(),
            # Movement and global were two more multipliers on the same number
            # as layer intensity; they are pinned to 1.0 so the single Layer
            # Intensity slider is the whole motion amount.
            movement_strength=1.0,
            focus_depth=self._focus_depth,
            layer_intensity=self.layer_intensity.value() / 100,
            global_intensity=1.0,
            duration=4.0 / speed,
            preview_fps=self._preview_fps,
        )

    def _emit_motion_settings(self):
        self.motionSettingsChanged.emit(self.motion_settings())

    def set_motion_settings(self, settings: MotionSettings):
        self._focus_depth = settings.focus_depth
        self._preview_fps = settings.preview_fps
        self._apply_motion_values(
            settings.motion_scale_x,
            settings.motion_scale_y,
            settings.zoom_strength,
            settings.loop_type,
            settings.movement_strength * settings.layer_intensity * settings.global_intensity,
            settings.duration,
        )

    def _apply_motion_values(self, scale_x, scale_y, zoom, loop_type, amount, duration):
        """Push stored values onto the four visible controls.

        `amount` folds the three old multipliers into one, so projects saved
        before the panel was simplified still preview at the same strength.
        """
        self.motion_style.set_value(self._closest_style(scale_x, scale_y, zoom), emit=False)
        self.loop_type.set_value(loop_type, emit=False)
        self.layer_intensity.set_value(max(0, min(100, int(round(amount * 100)))), emit=False)
        speed = 4.0 / max(0.25, duration)
        self.speed.set_value(_slider_from_speed(speed), emit=False)

    def _closest_style(self, scale_x, scale_y, zoom):
        best, best_dist = None, None
        for index in range(self.motion_style.combo.count()):
            payload = self.motion_style.combo.itemData(index)
            _n, sx, sy, sz = payload
            dist = (sx - scale_x) ** 2 + (sy - scale_y) ** 2 + (sz - zoom) ** 2
            if best_dist is None or dist < best_dist:
                best, best_dist = payload, dist
        return best

    def set_selected_layer_motion(self, layer, locked: bool = False):
        self._focus_depth = layer.focus_depth
        self._apply_motion_values(
            layer.motion_scale_x,
            layer.motion_scale_y,
            layer.zoom_strength,
            layer.loop_type,
            layer.movement_strength * layer.intensity * layer.global_intensity,
            layer.duration,
        )

    def set_motion_ready(self, has_layer: bool, has_depth_motion: bool):
        ready = has_layer and has_depth_motion
        for widget in self.motion_widgets:
            widget.setEnabled(ready)
            _set_tooltip_tree(
                widget,
                self.motion_tooltips.get(widget, "")
                if ready
                else "Motion controls are disabled because the selected layer has flat depth. Paint gentle variation first.",
            )

        if not has_layer:
            self.motion_notice.setText("Open or drop an image layer to begin.")
        elif not has_depth_motion:
            self.motion_notice.setText("Paint depth on the layer. Flat 0.50 has no parallax.")
        else:
            self.motion_notice.setText("If motion looks warped, soften the depth map.")
