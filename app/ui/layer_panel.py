from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QDrag, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyle,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.layer import Layer
from app.ui.theme import (
    C_ACCENT,
    C_BORDER,
    C_PANEL_BG,
    C_TEXT_MAIN,
    C_TEXT_MUTED,
    C_TEXT_SECONDARY,
)


class AddButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("+", parent)
        self.setFixedSize(34, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Add layer")
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: #111A22;
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                color: {C_TEXT_MAIN};
                font-size: 25px;
                font-weight: 300;
            }}
            QPushButton:hover {{
                color: {C_ACCENT};
                border-color: {C_ACCENT};
            }}
            """
        )


class SymbolButton(QPushButton):
    def __init__(self, kind: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(26, 26)
        self.setToolTip(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 5px;
                color: {C_TEXT_SECONDARY};
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: #17222C;
                color: {C_ACCENT};
            }}
            QPushButton:disabled {{
                color: {C_TEXT_MUTED};
            }}
            """
        )

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(C_ACCENT if self.isDown() else C_TEXT_SECONDARY)
        p.setPen(QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)

        if self.kind == "drag":
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C_TEXT_MUTED))
            for row in range(3):
                for col in range(2):
                    p.drawEllipse(QRectF(7 + col * 6, 7 + row * 6, 2.4, 2.4))
        elif self.kind == "lock":
            body = QRectF(rect.x() + 4, rect.y() + 11, rect.width() - 8, rect.height() - 12)
            p.setBrush(QColor(C_TEXT_SECONDARY))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(body, 2.6, 2.6)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawArc(QRectF(rect.x() + 6, rect.y() + 1, rect.width() - 12, rect.height() - 7), 0, 180 * 16)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C_ACCENT if self.isDown() else C_TEXT_SECONDARY))
            p.drawEllipse(QRectF(rect.center().x() - 1.2, rect.y() + 15, 2.4, 2.4))
        elif self.kind == "trash":
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
            icon.paint(p, self.rect().adjusted(4, 4, -4, -4))
        elif self.kind == "arrow_up":
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
            icon.paint(p, self.rect().adjusted(4, 4, -4, -4))
        elif self.kind == "arrow_down":
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
            icon.paint(p, self.rect().adjusted(4, 4, -4, -4))
        elif self.kind == "move_up":
            p.drawLine(QPointF(rect.center().x(), rect.top() + 6), QPointF(rect.center().x(), rect.bottom() - 7))
            p.drawLine(QPointF(rect.center().x() - 4, rect.top() + 10), QPointF(rect.center().x(), rect.top() + 6))
            p.drawLine(QPointF(rect.center().x() + 4, rect.top() + 10), QPointF(rect.center().x(), rect.top() + 6))
        elif self.kind == "move_down":
            p.drawLine(QPointF(rect.center().x(), rect.top() + 7), QPointF(rect.center().x(), rect.bottom() - 6))
            p.drawLine(QPointF(rect.center().x() - 4, rect.bottom() - 10), QPointF(rect.center().x(), rect.bottom() - 6))
            p.drawLine(QPointF(rect.center().x() + 4, rect.bottom() - 10), QPointF(rect.center().x(), rect.bottom() - 6))
        p.end()


class DragHandle(QWidget):
    dragRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 32)
        self.setToolTip("Drag to reorder")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._press_pos: QPointF | None = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()

    def mouseMoveEvent(self, event):
        if self._press_pos is None:
            return
        delta = event.position() - self._press_pos
        if abs(delta.x()) + abs(delta.y()) < 6:
            return
        self.dragRequested.emit()
        self._press_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseReleaseEvent(self, event):
        self._press_pos = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(163, 179, 190, 210))
        for row in range(3):
            for col in range(2):
                p.drawEllipse(QRectF(2 + col * 5, 8 + row * 6, 2.1, 2.1))


class LayerThumbnail(QWidget):
    def __init__(self, pixmap: QPixmap | None, parent=None):
        super().__init__(parent)
        self.pixmap = pixmap or QPixmap()
        self.setFixedSize(92, 132)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 5, 5)
        p.setClipPath(path)

        if self.pixmap.isNull():
            grad = QLinearGradient(QPointF(0, 0), QPointF(92, 132))
            grad.setColorAt(0, QColor("#2B3546"))
            grad.setColorAt(1, QColor("#101820"))
            p.fillRect(self.rect(), grad)
        else:
            x = (self.width() - self.pixmap.width()) // 2
            y = (self.height() - self.pixmap.height()) // 2
            p.fillRect(self.rect(), QColor("#0B1117"))
            p.drawPixmap(x, y, self.pixmap)

        p.setClipping(False)
        p.setPen(QPen(QColor(255, 255, 255, 50), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 5, 5)


class EyeIcon(QWidget):
    clicked = Signal()

    def __init__(self, visible: bool, parent=None):
        super().__init__(parent)
        self.visible_state = visible
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Toggle visibility")

    def mousePressEvent(self, event):
        self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(C_ACCENT if self.visible_state else C_TEXT_MUTED)
        p.setPen(QPen(color, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QRectF(4, 7, 12, 7))
        p.setBrush(color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(8, 9, 4, 4))
        if not self.visible_state:
            p.setPen(QPen(color, 1.5))
            p.drawLine(QPointF(4, 16), QPointF(16, 4))


class DragDots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(14, 28)
        self.setToolTip("Layer order")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C_TEXT_MUTED))
        for row in range(3):
            for col in range(2):
                p.drawEllipse(QRectF(1 + col * 6, 8 + row * 7, 2.4, 2.4))


class LayerCard(QWidget):
    selected = Signal(str)
    removeRequested = Signal(str)
    visibilityToggled = Signal(str)
    lockToggled = Signal(str)
    moveUpRequested = Signal(str)
    moveDownRequested = Signal(str)
    reorderRequested = Signal(str, int)

    def __init__(
        self,
        layer: Layer,
        selected: bool,
        display_index: int,
        parent=None,
    ):
        super().__init__(parent)
        self.layer = layer
        self.selected_state = selected
        self.display_index = display_index
        self.setFixedHeight(156)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build()

    def _build(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 12, 12, 12)
        row.setSpacing(10)

        order = QVBoxLayout()
        order.setSpacing(2)
        drag = DragHandle()
        drag.dragRequested.connect(self._start_drag)
        up = SymbolButton("arrow_up", "Move layer up")
        up.clicked.connect(lambda: self.moveUpRequested.emit(self.layer.id))
        down = SymbolButton("arrow_down", "Move layer down")
        down.clicked.connect(lambda: self.moveDownRequested.emit(self.layer.id))
        order.addStretch()
        order.addWidget(drag, alignment=Qt.AlignmentFlag.AlignHCenter)
        order.addWidget(up)
        order.addWidget(down)
        order.addStretch()
        row.addLayout(order)

        row.addWidget(LayerThumbnail(self.layer.thumbnail()))

        info = QVBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(6)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(4)
        eye = EyeIcon(self.layer.visible)
        eye.clicked.connect(lambda: self.visibilityToggled.emit(self.layer.id))
        controls.addWidget(eye)
        lock = SymbolButton("lock", "Lock transform" if not self.layer.locked else "Unlock transform")
        lock.clicked.connect(lambda: self.lockToggled.emit(self.layer.id))
        controls.addWidget(lock)
        remove = SymbolButton("trash", "Remove layer")
        remove.clicked.connect(lambda: self.removeRequested.emit(self.layer.id))
        controls.addWidget(remove)
        controls.addStretch()
        info.addLayout(controls)

        name = QLabel(self.layer.name)
        name.setToolTip(self.layer.name)
        name.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 16px; font-weight: 650;")
        name.setMaximumWidth(132)
        name.setText(self._display_name(self.layer.name))
        name.setWordWrap(False)
        info.addWidget(name)

        meta = QLabel(self.layer.info_label)
        meta.setStyleSheet(
            f"color: {C_ACCENT if self.selected_state else C_TEXT_SECONDARY}; "
            "font-family: 'JetBrains Mono', 'SF Mono', monospace; font-size: 11px;"
        )
        if self.layer.locked:
            meta.setText(f"Transform locked  •  {self.layer.info_label}")
        info.addWidget(meta)

        row.addLayout(info, stretch=1)

    def mousePressEvent(self, event):
        self.selected.emit(self.layer.id)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-parallax-layer-id", self.layer.id.encode("utf-8"))
        mime.setData("application/x-parallax-layer-display-index", str(self.display_index).encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(self.rect().center())
        drag.exec(Qt.DropAction.MoveAction)

    @staticmethod
    def _display_name(name: str) -> str:
        return name if len(name) <= 12 else f"{name[:9]}..."

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)

        bg = QColor("#101820") if not self.selected_state else QColor("#0F3435")
        if self.layer.locked:
            bg = QColor("#10151A") if not self.selected_state else QColor("#173036")
        p.setBrush(bg)
        p.setPen(QPen(QColor(C_ACCENT if self.selected_state else C_BORDER), 1.25))
        p.drawRoundedRect(rect, 8, 8)

        if self.selected_state:
            p.setPen(QPen(QColor(C_ACCENT), 3))
            p.drawLine(QPointF(rect.left() + 1, rect.top() + 8), QPointF(rect.left() + 1, rect.bottom() - 8))
            p.setBrush(QColor(61, 217, 201, 16))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)


class EmptyLayers(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(C_BORDER), 1, Qt.PenStyle.DashLine))
        p.setBrush(QColor("#101820"))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), 8, 8)
        p.setPen(QColor(C_TEXT_SECONDARY))
        p.drawText(self.rect().adjusted(20, 0, -20, 0), Qt.AlignmentFlag.AlignCenter, "Add or drop image layers")


class LayerPanel(QWidget):
    addLayerRequested = Signal()
    layerSelected = Signal(str)
    layerRemoveRequested = Signal(str)
    layerVisibilityToggled = Signal(str)
    layerLockToggled = Signal(str)
    layerMoveUpRequested = Signal(str)
    layerMoveDownRequested = Signal(str)
    layerReorderRequested = Signal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layers: list[Layer] = []
        self.selected_layer_id: str | None = None
        self.setFixedWidth(312)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("panelShell")
        shell.setStyleSheet(
            f"""
            QFrame#panelShell {{
                background: {C_PANEL_BG};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
            """
        )
        root.addWidget(shell)

        col = QVBoxLayout(shell)
        col.setContentsMargins(10, 10, 10, 12)
        col.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("LAYERS")
        title.setStyleSheet(f"color: {C_TEXT_MAIN}; font-size: 18px; font-weight: 650;")
        header.addWidget(title)
        header.addStretch()
        self.add_button = AddButton()
        self.add_button.clicked.connect(self.addLayerRequested.emit)
        header.addWidget(self.add_button)
        col.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        self.scroll.viewport().setAcceptDrops(True)
        self.scroll.viewport().installEventFilter(self)

        self.inner = QWidget()
        self.inner.setStyleSheet("background: transparent;")
        self.stack = QVBoxLayout(self.inner)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSpacing(10)
        self.scroll.setWidget(self.inner)
        col.addWidget(self.scroll)
        self.set_layers([], None)

    def set_layers(self, layers: list[Layer], selected_layer_id: str | None):
        self.layers = layers
        self.selected_layer_id = selected_layer_id
        self._refresh()

    def _refresh(self):
        while self.stack.count():
            item = self.stack.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not self.layers:
            self.stack.addWidget(EmptyLayers())
            self.stack.addStretch()
            return

        display_layers = list(reversed(self.layers))
        for display_index, layer in enumerate(display_layers):
            card = LayerCard(
                layer,
                layer.id == self.selected_layer_id,
                display_index,
            )
            card.selected.connect(self.layerSelected.emit)
            card.removeRequested.connect(self.layerRemoveRequested.emit)
            card.visibilityToggled.connect(self.layerVisibilityToggled.emit)
            card.lockToggled.connect(self.layerLockToggled.emit)
            card.moveUpRequested.connect(self.layerMoveUpRequested.emit)
            card.moveDownRequested.connect(self.layerMoveDownRequested.emit)
            self.stack.addWidget(card)

        self.stack.addStretch()

    def eventFilter(self, obj, event):
        if obj is self.scroll.viewport():
            etype = event.type()
            if etype in {QEvent.Type.DragEnter, QEvent.Type.DragMove}:
                if self._event_has_layer_mime(event):
                    event.acceptProposedAction()
                    return True
            if etype == QEvent.Type.Drop:
                if self._event_has_layer_mime(event):
                    source_id = bytes(event.mimeData().data("application/x-parallax-layer-id")).decode("utf-8")
                    target_index = self._drop_display_index(event.position().toPoint())
                    self.layerReorderRequested.emit(source_id, target_index)
                    event.acceptProposedAction()
                    return True
        return super().eventFilter(obj, event)

    def _event_has_layer_mime(self, event) -> bool:
        return event.mimeData().hasFormat("application/x-parallax-layer-id")

    def _drop_display_index(self, pos: QPoint) -> int:
        cards = [self.stack.itemAt(i).widget() for i in range(self.stack.count())]
        cards = [card for card in cards if isinstance(card, LayerCard)]
        if not cards:
            return 0

        y = pos.y()
        for index, card in enumerate(cards):
            top_left = card.mapTo(self.scroll.viewport(), QPoint(0, 0))
            center_y = top_left.y() + card.height() / 2
            if y < center_y:
                return index
        return len(cards)
