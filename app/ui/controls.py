from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
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


# Brush size is a share of the image's long edge, not a fixed pixel count. A
# fixed 220px ceiling is a broad brush on a 900px picture and a pinprick on a
# 4000px photo, so the same slider position meant something different for every
# image and the widest brush still could not cover a person in one pass. Tying
# it to the picture also keeps the depth gradient a stroke leaves behind roughly
# constant, and that gradient is what decides whether the moving edge tears.
BRUSH_MIN_FRACTION = 0.01
BRUSH_MAX_FRACTION = 0.25
BRUSH_REFERENCE_DEFAULT = 1200


def brush_pixels(slider_value: int, long_edge: int) -> int:
    fraction = BRUSH_MIN_FRACTION + (
        max(0, min(100, slider_value)) / 100.0
    ) * (BRUSH_MAX_FRACTION - BRUSH_MIN_FRACTION)
    return max(4, int(round(max(64, long_edge) * fraction)))


@dataclass(frozen=True)
class BrushSettings:
    size: int = 128
    # Neutral is 0.50 and the background is meant to stay there, so the only
    # thing that decides how far a brushed area travels is how far the stroke
    # pushes away from neutral. At 0.62 a default stroke moved about 1% of the
    # frame, which is not enough to read as a separate plane, which is why
    # painting an area looked like it had done nothing at all.
    depth_value: float = 0.75
    hardness: float = 0.18
    # Depthy defaults its brush to 0.25; 0.10 moved depth so little per pass
    # that strokes were invisible in the paint overlay.
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
        self.setFixedHeight(34)
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

    def _update_value(self, value: int):
        self.value_label.setText(self.formatter(value))
        self.valueChanged.emit()

    def refresh_label(self):
        """Re-run the formatter without emitting; for formatters that depend on
        something other than the slider position, such as the image size."""
        self.value_label.setText(self.formatter(self.slider.value()))


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
    bodyReliefRequested = Signal()
    portraitRequested = Signal()
    flauntRequested = Signal()
    bounceRequested = Signal()

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
        col.setSpacing(6)

        self._preview_fps = 24

        depth = Card("⌁", "DEPTH BRUSH")
        self._brush_reference = BRUSH_REFERENCE_DEFAULT
        self.brush_size = SimpleSliderRow(
            "Brush Size", 58, lambda v: f"{brush_pixels(v, self._brush_reference)} px"
        )
        self.depth_value = SimpleSliderRow("Depth Value", 75, lambda v: f"{v / 100:.2f}")
        self.hardness = SimpleSliderRow("Hardness", 18, lambda v: f"{v}%")
        self.opacity = SimpleSliderRow("Brush Strength", 100, lambda v: f"{v}%")
        _set_tooltip_tree(
            self.brush_size,
            "Width of each depth stroke, scaled to the image so the same setting covers the "
            "same share of any picture. Use small strokes around object edges and large ones "
            "for a whole figure or a background."
        )
        _set_tooltip_tree(
            self.depth_value,
            "Depth painted by the brush. 0.50 is neutral and stays still; higher comes toward "
            "the viewer, lower moves away. How far from 0.50 you paint is what decides how far "
            "that area travels, so the default sits well clear of neutral."
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
        self.body_relief_button = SmallAction("Body Relief", True)
        self.body_relief_button.setToolTip(
            "For photos of people. Finds the figure and its pose, then rebuilds the depth "
            "inside it so chest, waist, hips, knees and arms each carry their own parallax "
            "instead of the figure sliding as one cutout. Downloads two small models the "
            "first time. Needs a mostly unobstructed person; falls back with a message if "
            "it cannot find one."
        )
        self.portrait_button = SmallAction("Portrait", True)
        self.portrait_button.setToolTip(
            "For a single person, best on a cut-out portrait. Finds the face, then plays an "
            "idle motion instead of the depth slide: the head turns and nods as one rigid "
            "piece so the face never stretches, the body turns in depth around the head, "
            "the hips sway and the chest breathes. A background stays still. Sets the loop "
            "to 8 seconds. Body Relief or Clear switch back to the normal motion."
        )
        self.flaunt_button = SmallAction("Flaunt", True)
        self.flaunt_button.setToolTip(
            "Portrait's rigid head with a rhythm on top: the hips swing side to side while "
            "the shoulders lean against them, the raised hip tips up, the chest bounces "
            "with each step and the head tilts toward the hip. A background stays still. "
            "Sets the loop to 4 seconds, two swings."
        )
        self.bounce_button = SmallAction("Bounce", True)
        self.bounce_button.setToolTip(
            "A slow, smooth bounce on the spot, driven from the hips: her body rises and "
            "falls, her legs bend instead of her lifting off, her head rides it, and her "
            "breasts move in time with it, further, trailing it slightly. Nothing moves "
            "sideways. A background stays still. Sets the loop to 6 seconds, four bounces. "
            "Not the same as the Bounce loop type below."
        )
        self.clear_depth_button = SmallAction("Clear")
        self.invert_depth_button = SmallAction("Invert")
        # Checkable purely so the button can show whether the map is currently
        # flipped. Inverting is still one undoable edit per click; without the
        # lit state there was nothing on screen saying which way round the
        # depth was, so a second click looked like a different bug.
        self.invert_depth_button.setCheckable(True)
        self.blur_depth_button = SmallAction("Soften")
        self.clear_depth_button.setToolTip(
            "Return the selected layer to flat 0.50 depth. Parallax motion will pause until the layer has depth variation again."
        )
        self.invert_depth_button.setToolTip(
            "Swap near and far on the selected layer, so whatever was moving stays put and "
            "the rest moves instead. The button stays lit and reads Inverted while the map is "
            "flipped. Click again to flip it back."
        )
        self.blur_depth_button.setToolTip(
            "Apply one undoable blur pass to the selected depth map. This is not an on/off toggle; repeated clicks keep softening."
        )
        self.clear_depth_button.clicked.connect(self.clearDepthRequested.emit)
        self.invert_depth_button.clicked.connect(self.invertDepthRequested.emit)
        self.blur_depth_button.clicked.connect(self.blurDepthRequested.emit)
        self.body_relief_button.clicked.connect(self.bodyReliefRequested.emit)
        self.portrait_button.clicked.connect(self.portraitRequested.emit)
        self.flaunt_button.clicked.connect(self.flauntRequested.emit)
        self.bounce_button.clicked.connect(self.bounceRequested.emit)
        # Six columns: the four motion generators in pairs, the three edits
        # sharing the last row.
        buttons.addWidget(self.body_relief_button, 0, 0, 1, 3)
        buttons.addWidget(self.portrait_button, 0, 3, 1, 3)
        buttons.addWidget(self.flaunt_button, 1, 0, 1, 3)
        buttons.addWidget(self.bounce_button, 1, 3, 1, 3)
        buttons.addWidget(self.clear_depth_button, 2, 0, 1, 2)
        buttons.addWidget(self.invert_depth_button, 2, 2, 1, 2)
        buttons.addWidget(self.blur_depth_button, 2, 4, 1, 2)
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
        self.focus_depth = RangeStepper(
            "focus",
            [("Near", 0.0), ("Middle", 0.5), ("Far", 1.0)],
            1,
            formatter=lambda value: f"{value:.2f}",
            magnetic_center=True,
        )
        _set_tooltip_tree(
            self.focus_depth,
            "Depth plane that stays most anchored. Near steadies foreground subjects; Far steadies the background."
        )
        self.motion_path = RangeStepper(
            "path",
            [("Horizontal", (1.0, 0.0)), ("Circular", (1.0, 1.0)), ("Vertical", (0.0, 1.0))],
            1,
            path_preview=True,
            magnetic_center=True,
        )
        _set_tooltip_tree(
            self.motion_path,
            "Direction of camera motion. Horizontal is easiest to judge; Circular combines side-to-side and vertical drift."
        )
        self.zoom_strength = SliderRow("zoom", 35, lambda v: f"{v / 100:.2f}", "Still", "Breathe", magnetic_center=True)
        _set_tooltip_tree(
            self.zoom_strength,
            "Push-in and pull-back breathing. Too much zoom exaggerates rough depth paint, so keep it subtle while editing."
        )
        self.zoom_strength.valueChanged.connect(self._emit_motion_settings)
        for stepper in [self.focus_depth, self.motion_path]:
            stepper.changed.connect(self._emit_motion_settings)
            motion.layout.addWidget(stepper)
        motion.layout.insertWidget(2, self.zoom_strength)
        self.duration = SliderRow("duration", 43, lambda v: f"{1.0 + v / 100 * 7.0:.1f}s", "Short", "Long", magnetic_center=True)
        _set_tooltip_tree(
            self.duration,
            "Length of one loop. Short loops feel faster; longer loops make the same motion calmer."
        )
        self.duration.valueChanged.connect(self._emit_motion_settings)
        motion.layout.addWidget(self.duration)
        motion.layout.addWidget(_label("Loop"))
        self.loop_type = LoopButtons()
        self.loop_type.changed.connect(self._emit_motion_settings)
        motion.layout.addWidget(self.loop_type)
        self.layer_intensity = SliderRow("intensity", 65, lambda v: f"{v / 100:.2f}", "Subtle", "Strong", magnetic_center=True)
        _set_tooltip_tree(
            self.layer_intensity,
            "Motion multiplier for the selected layer only. Lower this if this image layer warps more than the rest of the scene."
        )
        for row in [self.layer_intensity]:
            row.valueChanged.connect(self._emit_motion_settings)
            motion.layout.addWidget(row)
        col.addWidget(motion)
        self.motion_widgets = [
            self.focus_depth,
            self.motion_path,
            self.zoom_strength,
            self.duration,
            self.loop_type,
            self.layer_intensity,
        ]
        self.motion_tooltips = {
            self.focus_depth: "Depth plane that stays most anchored. Near steadies foreground subjects; Far steadies the background.",
            self.motion_path: "Direction of camera motion. Horizontal is easiest to judge; Circular combines side-to-side and vertical drift.",
            self.zoom_strength: "Push-in and pull-back breathing. Too much zoom exaggerates rough depth paint, so keep it subtle while editing.",
            self.duration: "Length of one loop. Short loops feel faster; longer loops make the same motion calmer.",
            self.loop_type: "Seamless wraps cleanly for export; Bounce moves out and back, which is easier for inspecting depth problems.",
            self.layer_intensity: "Motion multiplier for the selected layer only. Lower this if this image layer warps more than the rest of the scene.",
        }

        col.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)
        self.set_motion_ready(False, False)
        self._emit_brush_settings()
        self._emit_motion_settings()

    def set_brush_reference(self, long_edge: int):
        """Tell the brush how big the image it is painting on is."""
        long_edge = max(64, int(long_edge))
        if long_edge == self._brush_reference:
            return
        self._brush_reference = long_edge
        self.brush_size.refresh_label()
        self._emit_brush_settings()

    def brush_settings(self) -> BrushSettings:
        return BrushSettings(
            size=brush_pixels(self.brush_size.value(), self._brush_reference),
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
        scale_x, scale_y = self.motion_path.value()
        return MotionSettings(
            motion_scale_x=scale_x,
            motion_scale_y=scale_y,
            zoom_strength=self.zoom_strength.value() / 100,
            loop_type=self.loop_type.value(),
            movement_strength=1.0,
            focus_depth=self.focus_depth.value(),
            layer_intensity=self.layer_intensity.value() / 100,
            global_intensity=1.0,
            duration=1.0 + self.duration.value() / 100 * 7.0,
            preview_fps=self._preview_fps,
        )

    def _emit_motion_settings(self):
        self.motionSettingsChanged.emit(self.motion_settings())

    def set_motion_settings(self, settings: MotionSettings):
        self.focus_depth.set_value(settings.focus_depth, emit=False)
        self.motion_path.set_value((settings.motion_scale_x, settings.motion_scale_y), emit=False)
        self.zoom_strength.setValue(max(0, min(100, int(round(settings.zoom_strength * 100)))), emit=False)
        self.duration.setValue(max(0, min(100, int(round((settings.duration - 1.0) / 7.0 * 100)))), emit=False)
        self.loop_type._value = settings.loop_type
        self.loop_type._sync()
        self.layer_intensity.setValue(max(0, min(100, int(round(settings.layer_intensity * 100)))), emit=False)
        self._preview_fps = settings.preview_fps

    def set_preview_fps(self, fps: int):
        """Preview rate lives in the transport bar, but is carried in
        MotionSettings, so the panel has to hold it across re-emits."""
        self._preview_fps = int(fps)

    def set_depth_inverted(self, inverted: bool):
        self.invert_depth_button.setChecked(bool(inverted))
        self.invert_depth_button.setText("Inverted" if inverted else "Invert")

    def set_selected_layer_motion(self, layer, locked: bool = False):
        self.set_depth_inverted(getattr(layer, "depth_inverted", False))
        self.set_brush_reference(max(layer.image.width(), layer.image.height()))
        self.focus_depth.set_value(layer.focus_depth, emit=False)
        self.motion_path.set_value((layer.motion_scale_x, layer.motion_scale_y), emit=False)
        self.zoom_strength.setValue(max(0, min(100, int(round(layer.zoom_strength * 100)))), emit=False)
        self.duration.setValue(max(0, min(100, int(round((layer.duration - 1.0) / 7.0 * 100)))), emit=False)
        self.loop_type._value = layer.loop_type
        self.loop_type._sync()
        self.layer_intensity.setValue(max(0, min(100, int(round(layer.intensity * 100)))), emit=False)
        self.layer_intensity.slider.setEnabled(True)

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

        # Once motion is usable the notice is just telling the user something
        # they have already done, at the cost of ~75px of panel height.
        self.motion_notice.setVisible(not ready)
        if not has_layer:
            self.motion_notice.setText("Open or drop an image layer first. Motion controls stay disabled until there is artwork and depth variation.")
        elif not has_depth_motion:
            self.motion_notice.setText("Paint gentle depth variation on the selected layer. Flat 0.50 depth has no parallax to animate.")
        else:
            self.motion_notice.setText("Preview uses the selected layer depth map. If motion looks warped, lower brush strength or blur the depth map.")
