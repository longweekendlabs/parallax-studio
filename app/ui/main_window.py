from pathlib import Path

from PySide6.QtCore import QElapsedTimer, Qt, QTimer, QRectF, QPointF, QSize
from PySide6.QtGui import QAction, QColor, QFont, QFontMetricsF, QImage, QKeySequence, QPainter, QBrush, QLinearGradient, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from app.core.animator import loop_phase
from app.core.compositor import composite_animated_layers, composite_layers
from app.core.depth import (
    blur_depth,
    clear_depth,
    depth_to_qimage,
    ensure_depth_map,
    invert_depth,
    paint_depth,
    push_depth_undo,
    redo_depth,
    undo_depth,
)
from app.core.layer import Layer, is_supported_image, load_layer
from app.core.project import ProjectSerializer
from app.ui.canvas import CanvasPanel
from app.ui.controls import BrushSettings, ControlsPanel, MotionSettings
from app.ui.layer_panel import LayerPanel
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
from app.ui.export_dialog import ExportDialog
from app.ui.timeline import TimelineStrip
from app.utils.paths import ensure_app_dirs
from app.utils.settings import AppSettings, load_settings, save_settings
from app.utils.status import StatusController, StatusLevel, StatusMessage


class LogoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(42, 42)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        grad = QLinearGradient(QPointF(4, 4), QPointF(38, 38))
        grad.setColorAt(0, QColor(C_ACCENT))
        grad.setColorAt(1, QColor("#167F77"))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(QRectF(4, 4, 30, 34), 4, 4)

        p.setBrush(QColor("#091013"))
        p.drawRect(QRectF(15, 12, 6, 22))

        p.setBrush(QColor(C_ACCENT))
        p.drawPie(QRectF(15, 5, 24, 24), -90 * 16, 180 * 16)

        p.setBrush(QColor("#0B1014"))
        p.drawPie(QRectF(21, 11, 12, 12), -90 * 16, 180 * 16)


class BrandWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        title_font = QFont("Inter", 17)
        title_font.setWeight(QFont.Weight.DemiBold)
        brand_font = QFont("Inter", 9)
        brand_font.setWeight(QFont.Weight.Medium)
        title_metrics = QFontMetricsF(title_font)
        brand_metrics = QFontMetricsF(brand_font)
        width = int(title_metrics.horizontalAdvance("Parallax Studio") + 16 + brand_metrics.horizontalAdvance("by Long Weekend Labs"))
        return QSize(width, 42)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        title_font = QFont("Inter", 17)
        title_font.setWeight(QFont.Weight.DemiBold)
        brand_font = QFont("Inter", 9)
        brand_font.setWeight(QFont.Weight.Medium)

        title_metrics = QFontMetricsF(title_font)
        brand_metrics = QFontMetricsF(brand_font)

        baseline_y = 26
        title_x = 0
        brand_x = title_metrics.horizontalAdvance("Parallax Studio") + 16

        p.setFont(title_font)
        p.setPen(QColor(C_TEXT_MAIN))
        p.drawText(QPointF(title_x, baseline_y), "Parallax Studio")

        p.setFont(brand_font)
        p.setPen(QColor(145, 161, 173, 165))
        brand_y = baseline_y - (title_metrics.ascent() - brand_metrics.ascent()) * 0.22
        p.drawText(QPointF(brand_x, brand_y), "by Long Weekend Labs")
        p.end()


class IconButton(QPushButton):
    def __init__(self, icon: str, label: str, width: int = 108, parent=None):
        super().__init__(f"{icon}  {label}", parent)
        self.setFixedSize(width, 44)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 8px;
                color: {C_TEXT_MAIN};
                font-size: 15px;
                text-align: left;
                padding-left: 14px;
            }}
            QPushButton:hover {{
                background: {C_RAISED_PANEL};
            }}
            """
        )


class PreviewButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("▶  Preview 24fps  ⌄", parent)
        self.setFixedSize(194, 44)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: #0E151C;
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                color: {C_TEXT_MAIN};
                font-size: 15px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                border-color: {C_ACCENT}88;
            }}
            """
        )


class ExportButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__("⇧  Export MP4", parent)
        self.setFixedSize(168, 44)
        self.setCursor(Qt.PointingHandCursor)
        self.setObjectName("exportBtn")
        self.setStyleSheet(
            f"""
            QPushButton {{
                background: {C_EXPORT};
                border: none;
                border-radius: 8px;
                color: #1D1204;
                font-size: 15px;
                font-weight: 700;
            }}
            QPushButton:hover {{
                background: #FFC979;
            }}
            """
        )


class TopBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(78)
        self.setStyleSheet(
            f"background: #090F13; border-bottom: 1px solid {C_BORDER_SOFT};"
        )
        self._build()

    def _build(self):
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 0, 46, 0)
        row.setSpacing(12)

        row.addWidget(LogoWidget())
        row.addWidget(BrandWidget())

        row.addStretch(1)
        self.new_button = IconButton("⌘", "New", 96)
        self.open_button = IconButton("▰", "Open", 104)
        self.save_button = IconButton("▣", "Save", 100)
        self.undo_button = IconButton("↶", "Undo", 106)
        self.redo_button = IconButton("↷", "Redo", 106)
        row.addWidget(self.new_button)
        row.addWidget(self.open_button)
        row.addWidget(self.save_button)
        row.addWidget(self.undo_button)
        row.addWidget(self.redo_button)
        row.addStretch(2)
        self.preview_button = PreviewButton()
        row.addWidget(self.preview_button)
        row.addSpacing(8)
        self.export_button = ExportButton()
        row.addWidget(self.export_button)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_app_dirs()
        self.settings: AppSettings = load_settings()
        self.status_controller = StatusController(self)
        self.layers: list[Layer] = []
        self.selected_layer_id: str | None = None
        self.current_project_path: Path | None = None
        self.brush_settings = BrushSettings()
        self.motion_settings = MotionSettings()
        self._last_paint_point: tuple[int, int] | None = None
        self._undo_actions: list[tuple] = []
        self._redo_actions: list[tuple] = []
        self._active_transform_before: tuple[str, int, int, float] | None = None
        self._preview_playing = True
        self._elapsed = QElapsedTimer()
        self._elapsed.start()
        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._tick_preview)
        self.setWindowTitle("Parallax Studio")
        self.setMinimumSize(1280, 820)
        self.resize(self.settings.window_width, self.settings.window_height)
        self._build()
        self._build_actions()
        self._connect_status()
        self._update_window_title()

    def _update_window_title(self):
        title = "Parallax Studio"
        if self.current_project_path:
            title += f" — {self.current_project_path.name}"
        else:
            title += " — Unsaved Project"
        self.setWindowTitle(title)

    def _add_recent_project(self, path: Path):
        path_str = str(path.absolute())
        if path_str in self.settings.recent_projects:
            self.settings.recent_projects.remove(path_str)
        self.settings.recent_projects.insert(0, path_str)
        self.settings.recent_projects = self.settings.recent_projects[:10]
        save_settings(self.settings)
        self._update_recent_menu()

    def _update_recent_menu(self):
        self.recent_menu.clear()
        if not self.settings.recent_projects:
            self.recent_menu.addAction("No Recent Projects").setEnabled(False)
            return

        for path_str in self.settings.recent_projects:
            path = Path(path_str)
            action = QAction(path.name, self)
            action.setData(path_str)
            action.triggered.connect(lambda checked=False, p=path: self._open_project_at_path(p))
            self.recent_menu.addAction(action)

        self.recent_menu.addSeparator()
        clear_action = QAction("Clear Recent Projects", self)
        clear_action.triggered.connect(self._clear_recent_projects)
        self.recent_menu.addAction(clear_action)

    def _clear_recent_projects(self):
        self.settings.recent_projects.clear()
        save_settings(self.settings)
        self._update_recent_menu()

    def _build(self):
        central = QWidget()
        central.setStyleSheet(f"background: {C_WINDOW_BG};")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.top_bar = TopBar()
        root.addWidget(self.top_bar)

        body = QHBoxLayout()
        body.setContentsMargins(16, 18, 16, 12)
        body.setSpacing(14)

        self.layer_panel = LayerPanel()
        body.addWidget(self.layer_panel)
        self.canvas = CanvasPanel()
        body.addWidget(self.canvas, stretch=1)
        self.controls = ControlsPanel()
        body.addWidget(self.controls)

        root.addLayout(body, stretch=1)
        root.addWidget(TimelineStrip())

        status_bar = QStatusBar()
        status_bar.setFixedHeight(24)
        status_bar.setStyleSheet(
            f"""
            QStatusBar {{
                background: #090F13;
                border-top: 1px solid {C_BORDER_SOFT};
                color: {C_TEXT_MUTED};
                font-family: 'JetBrains Mono', 'SF Mono', monospace;
                font-size: 11px;
            }}
            """
        )
        self.setStatusBar(status_bar)

        self.canvas.imageFilesDropped.connect(self._handle_dropped_images)
        self.canvas.unsupportedFilesDropped.connect(self._handle_unsupported_drop)
        self.canvas.depthPaintRequested.connect(self._paint_selected_depth)
        self.canvas.layerMoveRequested.connect(self._move_selected_layer)
        self.canvas.layerResizeRequested.connect(self._resize_selected_layer)
        self.canvas.layerTransformStarted.connect(self._begin_transform_edit)
        self.canvas.layerTransformFinished.connect(self._finish_transform_edit)
        self.layer_panel.addLayerRequested.connect(self._add_layers_from_picker)
        self.layer_panel.layerSelected.connect(self._select_layer)
        self.layer_panel.layerRemoveRequested.connect(self._remove_layer)
        self.layer_panel.layerVisibilityToggled.connect(self._toggle_layer_visibility)
        self.layer_panel.layerLockToggled.connect(self._toggle_layer_lock)
        self.layer_panel.layerMoveUpRequested.connect(self._move_layer_up)
        self.layer_panel.layerMoveDownRequested.connect(self._move_layer_down)
        self.layer_panel.layerReorderRequested.connect(self._reorder_layer)
        self.controls.brushSettingsChanged.connect(self._set_brush_settings)
        self.controls.motionSettingsChanged.connect(self._set_motion_settings)
        self.controls.clearDepthRequested.connect(self._clear_selected_depth)
        self.controls.invertDepthRequested.connect(self._invert_selected_depth)
        self.controls.blurDepthRequested.connect(self._blur_selected_depth)
        self.controls.autoDepthRequested.connect(self._auto_depth_placeholder)
        self.canvas.set_brush_preview(self.brush_settings.size, self.brush_settings.opacity)
        self._start_preview_timer()

    def _build_actions(self):
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(True)
        file_menu = menu_bar.addMenu("File")

        self.new_action = QAction("New Project", self)
        self.new_action.setShortcut(QKeySequence.New)
        self.new_action.triggered.connect(self._new_project)

        self.open_action = QAction("Open Project...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self._open_project)

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self._save_project)

        self.save_as_action = QAction("Save As...", self)
        self.save_as_action.setShortcut(QKeySequence.SaveAs)
        self.save_as_action.triggered.connect(self._save_project_as)

        self.recent_menu = QMenu("Open Recent", self)
        self._update_recent_menu()

        self.add_layers_action = QAction("Add Image Layers...", self)
        self.add_layers_action.setShortcut(QKeySequence(Qt.Modifier.SHIFT | Qt.Key.Key_O))
        self.add_layers_action.triggered.connect(self._add_layers_from_picker)

        self.export_action = QAction("Export MP4...", self)
        self.export_action.triggered.connect(self._export_project)

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.undo_action.triggered.connect(self._undo_selected_depth)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.redo_action.triggered.connect(self._redo_selected_depth)

        for action in [
            self.new_action,
            self.open_action,
        ]:
            file_menu.addAction(action)

        file_menu.addMenu(self.recent_menu)
        file_menu.addSeparator()

        for action in [
            self.save_action,
            self.save_as_action,
            self.add_layers_action,
            self.export_action,
            self.undo_action,
            self.redo_action,
        ]:
            file_menu.addAction(action)

        self.top_bar.new_button.clicked.connect(self.new_action.trigger)
        self.top_bar.open_button.clicked.connect(self.open_action.trigger)
        self.top_bar.save_button.clicked.connect(self.save_action.trigger)
        self.top_bar.undo_button.clicked.connect(self.undo_action.trigger)
        self.top_bar.redo_button.clicked.connect(self.redo_action.trigger)
        self.top_bar.export_button.clicked.connect(self.export_action.trigger)
        self.top_bar.preview_button.clicked.connect(self._toggle_preview)
        self.addActions([
            self.new_action,
            self.open_action,
            self.save_action,
            self.save_as_action,
            self.add_layers_action,
            self.export_action,
            self.undo_action,
            self.redo_action,
        ])

        # Keep the approved custom top bar visually dominant during the shell phase.
        menu_bar.hide()

    def _connect_status(self):
        self.status_controller.changed.connect(self._show_status)
        self.status_controller.info("Ready  ·  No project loaded")

    def _show_status(self, message: StatusMessage):
        prefix = {
            StatusLevel.INFO: "",
            StatusLevel.WARNING: "Warning: ",
            StatusLevel.ERROR: "Error: ",
        }[message.level]
        self.statusBar().showMessage(prefix + message.text)

    def _new_project(self):
        self.layers.clear()
        self.selected_layer_id = None
        self.current_project_path = None
        self._undo_actions.clear()
        self._redo_actions.clear()
        self._active_transform_before = None
        self._last_paint_point = None
        self._refresh_layers()
        self._update_window_title()
        self.status_controller.info("New project ready")

    def _open_project(self):
        path, selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open Project or Image",
            self.settings.last_open_dir,
            "All Supported (*.parlx *.png *.jpg *.jpeg *.webp);;Parallax Project (*.parlx);;Images (*.png *.jpg *.jpeg *.webp)",
        )
        if path:
            file_path = Path(path)
            if file_path.suffix.lower() == ".parlx":
                self._open_project_at_path(file_path)
            else:
                self._import_image_paths([path])

    def _open_project_at_path(self, project_path: Path):
        self.settings.last_open_dir = str(project_path.parent)
        try:
            with open(project_path, "r", encoding="utf-8") as f:
                content = f.read()
            layers, motion_settings, selected_id = ProjectSerializer.deserialize(content)
            self.layers = layers
            self.motion_settings = motion_settings
            self.selected_layer_id = selected_id
            self.current_project_path = project_path
            self.controls.set_motion_settings(self.motion_settings)
            self._add_recent_project(project_path)
            self._undo_actions.clear()
            self._redo_actions.clear()
            self._last_paint_point = None
            self._refresh_layers()
            self._update_window_title()
            self.status_controller.info(f"Opened project: {project_path.name}")
        except Exception as e:
            self.status_controller.error(f"Failed to open project: {str(e)}")

    def _save_project(self):
        if not self.current_project_path:
            self._save_project_as()
            return

        try:
            content = ProjectSerializer.serialize(self.layers, self.motion_settings, self.selected_layer_id)
            with open(self.current_project_path, "w", encoding="utf-8") as f:
                f.write(content)
            self._add_recent_project(self.current_project_path)
            self.status_controller.info(f"Saved project: {self.current_project_path.name}")
        except Exception as e:
            self.status_controller.error(f"Failed to save project: {str(e)}")

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            self.settings.last_open_dir,
            "Parallax Studio Projects (*.parlx)",
        )
        if not path:
            return

        project_path = Path(path)
        if project_path.suffix != ".parlx":
            project_path = project_path.with_suffix(".parlx")

        self.settings.last_open_dir = str(project_path.parent)
        self.current_project_path = project_path
        self._save_project()
        self._update_window_title()

    def _export_project(self):
        if not self.layers:
            self.status_controller.warning("Add layers before exporting")
            return

        was_playing = self._preview_playing
        self._preview_timer.stop()

        dlg = ExportDialog(
            self.layers,
            self.motion_settings,
            last_export_dir=self.settings.last_export_dir,
            parent=self,
        )
        dlg.exportCompleted.connect(self._on_export_completed)
        dlg.exec()

        if dlg.last_used_dir:
            self.settings.last_export_dir = dlg.last_used_dir
            save_settings(self.settings)

        if was_playing:
            self._elapsed.restart()
            self._start_preview_timer()

    def _on_export_completed(self, output_path: str) -> None:
        self.status_controller.info(f"Exported: {Path(output_path).name}")

    def _toggle_preview(self):
        self._preview_playing = not self._preview_playing
        if self._preview_playing:
            self._elapsed.restart()
            self._start_preview_timer()
            self.status_controller.info("Preview playing")
        else:
            self._preview_timer.stop()
            self._refresh_layers(refresh_panel=False)
            self.status_controller.info("Preview paused")

    def _handle_dropped_images(self, paths: list[str]):
        self._import_image_paths(paths)

    def _handle_unsupported_drop(self, paths: list[str]):
        count = len(paths)
        noun = "file" if count == 1 else "files"
        self.status_controller.warning(f"Ignored {count} unsupported dropped {noun}")

    def _add_layers_from_picker(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Image Layers",
            self.settings.last_open_dir,
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if files:
            self.settings.last_open_dir = str(Path(files[0]).parent)
            self._import_image_paths(files)

    def _import_image_paths(self, paths: list[str]):
        supported = [path for path in paths if is_supported_image(path)]
        unsupported_count = len(paths) - len(supported)
        imported: list[Layer] = []
        errors: list[str] = []

        for path in supported:
            try:
                imported.append(load_layer(path))
            except ValueError as exc:
                errors.append(str(exc))

        if imported:
            before = self._project_snapshot()
            first_import = not self.layers
            sel = self._selected_layer()
            src = sel if sel is not None else None
            for layer in imported:
                if first_import and layer is imported[0]:
                    layer.locked = True
                layer.intensity = src.intensity if src else self.motion_settings.layer_intensity
                layer.movement_strength = src.movement_strength if src else self.motion_settings.movement_strength
                layer.zoom_strength = src.zoom_strength if src else self.motion_settings.zoom_strength
                layer.motion_scale_x = src.motion_scale_x if src else self.motion_settings.motion_scale_x
                layer.motion_scale_y = src.motion_scale_y if src else self.motion_settings.motion_scale_y
                layer.focus_depth = src.focus_depth if src else self.motion_settings.focus_depth
                layer.global_intensity = src.global_intensity if src else self.motion_settings.global_intensity
                layer.duration = src.duration if src else self.motion_settings.duration
                layer.loop_type = src.loop_type if src else self.motion_settings.loop_type
            self.layers.extend(imported)
            self.selected_layer_id = imported[-1].id
            self._last_paint_point = None
            self._refresh_layers()
            after = self._project_snapshot()
            self._record_project_action(before, after, "Imported layers")

        if unsupported_count:
            self.status_controller.warning(f"Ignored {unsupported_count} unsupported file(s)")
        elif errors:
            self.status_controller.error(errors[0])
        elif imported:
            count = len(imported)
            noun = "layer" if count == 1 else "layers"
            self.status_controller.info(f"Imported {count} {noun}")

    def _refresh_layers(self, refresh_panel: bool = True):
        if self.layers and self.selected_layer_id not in {layer.id for layer in self.layers}:
            self.selected_layer_id = self.layers[-1].id

        selected_layer = self._selected_layer()
        if selected_layer is not None:
            self.controls.set_selected_layer_motion(selected_layer, selected_layer.locked)
        selected_visible = selected_layer is not None and selected_layer.visible
        if selected_visible:
            ensure_depth_map(selected_layer)
        composite = composite_layers(self.layers)
        if refresh_panel:
            self.layer_panel.set_layers(self.layers, self.selected_layer_id)
        self.canvas.set_composite(
            composite,
            selected_layer.name if selected_layer else "",
        )
        self.canvas.set_depth_overlay(self._depth_overlay_for_selected(composite, selected_layer))
        # Push selection bounding box to canvas for move/resize handles
        if selected_visible and composite is not None:
            offset = self._composite_layer_offset(composite, selected_layer)
            if offset is not None:
                sw = max(1, int(selected_layer.image.width() * selected_layer.scale))
                sh = max(1, int(selected_layer.image.height() * selected_layer.scale))
                self.canvas.set_selected_layer_bounds(
                    (offset[0], offset[1], sw, sh),
                    selected_layer.scale,
                    locked=bool(selected_layer.locked),
                )
            else:
                self.canvas.set_selected_layer_bounds(None)
        else:
            self.canvas.set_selected_layer_bounds(None)
        if self._preview_playing:
            self._tick_preview()

    def _selected_layer(self) -> Layer | None:
        if self.selected_layer_id is None:
            return None
        return next((layer for layer in self.layers if layer.id == self.selected_layer_id), None)

    def _layer_index(self, layer_id: str) -> int | None:
        for index, layer in enumerate(self.layers):
            if layer.id == layer_id:
                return index
        return None

    def _layer_snapshot(self, layer: Layer) -> dict:
        return {
            "source_path": str(layer.source_path),
            "image": layer.image.copy(),
            "name": layer.name,
            "id": layer.id,
            "visible": layer.visible,
            "locked": layer.locked,
            "opacity": layer.opacity,
            "intensity": layer.intensity,
            "motion_scale_x": layer.motion_scale_x,
            "motion_scale_y": layer.motion_scale_y,
            "zoom_strength": layer.zoom_strength,
            "movement_strength": layer.movement_strength,
            "focus_depth": layer.focus_depth,
            "x_offset": layer.x_offset,
            "y_offset": layer.y_offset,
            "scale": layer.scale,
            "depth_map": None if layer.depth_map is None else layer.depth_map.copy(),
            "depth_undo_stack": [depth.copy() for depth in layer.depth_undo_stack],
            "depth_redo_stack": [depth.copy() for depth in layer.depth_redo_stack],
        }

    def _project_snapshot(self) -> tuple[list[dict], str | None]:
        return ([self._layer_snapshot(layer) for layer in self.layers], self.selected_layer_id)

    def _restore_project_snapshot(self, snapshot: tuple[list[dict], str | None]):
        layers_data, selected_id = snapshot
        restored: list[Layer] = []
        for data in layers_data:
            layer = Layer(
                source_path=Path(data["source_path"]),
                image=data["image"].copy(),
                name=data["name"],
                id=data["id"],
                visible=data["visible"],
                locked=data["locked"],
                opacity=data["opacity"],
                intensity=data["intensity"],
                motion_scale_x=data["motion_scale_x"],
                motion_scale_y=data["motion_scale_y"],
                zoom_strength=data["zoom_strength"],
                movement_strength=data["movement_strength"],
                focus_depth=data["focus_depth"],
                x_offset=data["x_offset"],
                y_offset=data["y_offset"],
                scale=data["scale"],
                depth_map=None if data["depth_map"] is None else data["depth_map"].copy(),
            )
            layer.depth_undo_stack = [depth.copy() for depth in data["depth_undo_stack"]]
            layer.depth_redo_stack = [depth.copy() for depth in data["depth_redo_stack"]]
            restored.append(layer)
        self.layers = restored
        self.selected_layer_id = selected_id if selected_id in {layer.id for layer in restored} else (restored[-1].id if restored else None)
        self._last_paint_point = None
        self._active_transform_before = None
        self._refresh_layers()

    def _record_project_action(self, before: tuple[list[dict], str | None], after: tuple[list[dict], str | None], label: str):
        self._undo_actions.append(("state", before, after, label))
        if len(self._undo_actions) > 50:
            self._undo_actions.pop(0)
        self._redo_actions.clear()

    def _select_layer(self, layer_id: str):
        self.selected_layer_id = layer_id
        self._last_paint_point = None
        layer = self._selected_layer()
        if layer is not None:
            self.controls.set_selected_layer_motion(layer, layer.locked)
        self._refresh_layers()
        if layer:
            self.status_controller.info(f"Selected {layer.name}")

    def _rename_layer(self, layer_id: str):
        layer = next((item for item in self.layers if item.id == layer_id), None)
        if layer is None:
            return
        before = self._project_snapshot()
        name, accepted = QInputDialog.getText(self, "Rename Layer", "Layer name:", text=layer.name)
        clean_name = name.strip()
        if accepted and clean_name:
            layer.name = clean_name
            self.selected_layer_id = layer.id
            self._last_paint_point = None
            self._refresh_layers()
            after = self._project_snapshot()
            self._record_project_action(before, after, "Renamed layer")
            self.status_controller.info(f"Renamed layer to {clean_name}")

    def _duplicate_layer(self, layer_id: str):
        index = self._layer_index(layer_id)
        if index is None:
            return
        before = self._project_snapshot()
        duplicate = self.layers[index].duplicate()
        duplicate.locked = False
        self.layers.insert(index + 1, duplicate)
        self.selected_layer_id = duplicate.id
        self._last_paint_point = None
        self._refresh_layers()
        after = self._project_snapshot()
        self._record_project_action(before, after, "Duplicated layer")
        self.status_controller.info(f"Duplicated {self.layers[index].name}")

    def _remove_layer(self, layer_id: str):
        index = self._layer_index(layer_id)
        if index is None:
            return
        before = self._project_snapshot()
        removed = self.layers.pop(index)
        if self.layers:
            next_index = min(index, len(self.layers) - 1)
            self.selected_layer_id = self.layers[next_index].id
        else:
            self.selected_layer_id = None
        self._last_paint_point = None
        self._refresh_layers()
        after = self._project_snapshot()
        self._record_project_action(before, after, "Removed layer")
        self.status_controller.info(f"Removed {removed.name}")

    def _toggle_layer_visibility(self, layer_id: str):
        layer = next((item for item in self.layers if item.id == layer_id), None)
        if layer is None:
            return
        before = self._project_snapshot()
        layer.visible = not layer.visible
        self.selected_layer_id = layer.id
        self._last_paint_point = None
        self._refresh_layers()
        after = self._project_snapshot()
        self._record_project_action(before, after, "Toggled visibility")
        state = "visible" if layer.visible else "hidden"
        self.status_controller.info(f"{layer.name} is {state}")

    def _toggle_layer_lock(self, layer_id: str):
        layer = next((item for item in self.layers if item.id == layer_id), None)
        if layer is None:
            return
        before = self._project_snapshot()
        layer.locked = not layer.locked
        self.selected_layer_id = layer.id
        self._last_paint_point = None
        self._refresh_layers()
        after = self._project_snapshot()
        self._record_project_action(before, after, "Toggled lock")
        state = "locked" if layer.locked else "unlocked"
        self.status_controller.info(f"{layer.name} transform is {state}")

    def _reorder_layer(self, layer_id: str, target_display_index: int):
        index = self._layer_index(layer_id)
        if index is None:
            return
        display_layers = list(reversed(self.layers))
        try:
            source_display_index = next(i for i, layer in enumerate(display_layers) if layer.id == layer_id)
        except StopIteration:
            return
        target_display_index = max(0, min(len(display_layers), target_display_index))
        if source_display_index == target_display_index or source_display_index + 1 == target_display_index:
            return
        before = self._project_snapshot()
        layer = display_layers.pop(source_display_index)
        if source_display_index < target_display_index:
            target_display_index -= 1
        display_layers.insert(target_display_index, layer)
        self.layers = list(reversed(display_layers))
        self.selected_layer_id = layer_id
        self._last_paint_point = None
        self._refresh_layers()
        after = self._project_snapshot()
        self._record_project_action(before, after, "Reordered layers")

    def _move_layer_up(self, layer_id: str):
        index = self._layer_index(layer_id)
        if index is None:
            return
        display_index = len(self.layers) - 1 - index
        self._reorder_layer(layer_id, max(0, display_index - 1))

    def _move_layer_down(self, layer_id: str):
        index = self._layer_index(layer_id)
        if index is None:
            return
        display_index = len(self.layers) - 1 - index
        self._reorder_layer(layer_id, min(len(self.layers), display_index + 1))

    def _set_brush_settings(self, settings: BrushSettings):
        self.brush_settings = settings
        self.canvas.set_brush_preview(settings.size, settings.opacity)

    def _set_motion_settings(self, settings: MotionSettings):
        self.motion_settings = settings
        selected = self._selected_layer()
        if selected is not None:
            selected.intensity = settings.layer_intensity
            selected.motion_scale_x = settings.motion_scale_x
            selected.motion_scale_y = settings.motion_scale_y
            selected.zoom_strength = settings.zoom_strength
            selected.movement_strength = settings.movement_strength
            selected.focus_depth = settings.focus_depth
            selected.global_intensity = settings.global_intensity
            selected.duration = settings.duration
            selected.loop_type = settings.loop_type
        self._start_preview_timer()
        self._tick_preview()

    def _start_preview_timer(self):
        interval = max(1, int(1000 / max(1, self.motion_settings.preview_fps)))
        self._preview_timer.start(interval)

    def _tick_preview(self):
        if not self.layers or not self._preview_playing:
            return
        sel = self._selected_layer() or self.layers[0]
        phase = loop_phase(
            self._elapsed.elapsed() / 1000,
            sel.duration,
            1.0,
            sel.loop_type,
        )
        amplitude = 20.0
        frame = composite_animated_layers(
            self.layers,
            phase,
            amplitude,
            global_intensity=sel.global_intensity,
            depth_focus=sel.focus_depth,
            loop_type=sel.loop_type,
        )
        selected_layer = self._selected_layer()
        self.canvas.set_composite(frame, selected_layer.name if selected_layer else "")
        self.canvas.set_depth_overlay(self._depth_overlay_for_selected(frame, selected_layer))

    def _composite_layer_offset(self, composite: QImage | None, layer: Layer) -> tuple[int, int] | None:
        if composite is None:
            return None
        scaled_w = int(layer.image.width() * layer.scale)
        scaled_h = int(layer.image.height() * layer.scale)
        return (
            (composite.width() - scaled_w) // 2 + layer.x_offset,
            (composite.height() - scaled_h) // 2 + layer.y_offset,
        )

    def _depth_overlay_for_selected(self, composite: QImage | None, layer: Layer | None) -> QImage | None:
        if composite is None or layer is None or not layer.visible:
            return None
        depth_image = depth_to_qimage(ensure_depth_map(layer))
        if depth_image is None:
            return None
        if layer.scale != 1.0:
            sw = max(1, int(depth_image.width() * layer.scale))
            sh = max(1, int(depth_image.height() * layer.scale))
            depth_image = depth_image.scaled(sw, sh, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        offset = self._composite_layer_offset(composite, layer)
        if offset is None:
            return None
        overlay = QImage(composite.width(), composite.height(), QImage.Format.Format_ARGB32_Premultiplied)
        overlay.fill(QColor(0, 0, 0, 0))
        painter = QPainter(overlay)
        painter.drawImage(offset[0], offset[1], depth_image)
        painter.end()
        return overlay

    def _paint_selected_depth(self, composite_x: int, composite_y: int, begin_stroke: bool):
        layer = self._selected_layer()
        if layer is None or not layer.visible:
            return
        # Reuse the already-displayed composite image for offset — avoids a full recomposite per stroke
        composite = self.canvas.stage.composite_image
        if composite is None:
            return
        offset = self._composite_layer_offset(composite, layer)
        if offset is None:
            return
        layer_x = composite_x - offset[0]
        layer_y = composite_y - offset[1]
        if layer.scale != 1.0:
            layer_x = int(layer_x / layer.scale)
            layer_y = int(layer_y / layer.scale)
        if layer_x < 0 or layer_y < 0 or layer_x >= layer.image.width() or layer_y >= layer.image.height():
            return
        if begin_stroke:
            push_depth_undo(layer)
            self._record_depth_action(layer)
            self._last_paint_point = None

        points = [(layer_x, layer_y)]
        if self._last_paint_point is not None:
            last_x, last_y = self._last_paint_point
            dx = layer_x - last_x
            dy = layer_y - last_y
            # Euclidean distance so diagonal strokes get correct stamp density
            dist = (dx * dx + dy * dy) ** 0.5
            step = max(2, int(self.brush_settings.size * 0.18))
            count = max(1, int(dist / step))
            points = [
                (
                    int(last_x + dx * i / count),
                    int(last_y + dy * i / count),
                )
                for i in range(1, count + 1)
            ]

        for x, y in points:
            paint_depth(
                layer,
                x,
                y,
                self.brush_settings.size,
                self.brush_settings.depth_value,
                self.brush_settings.hardness,
                self.brush_settings.opacity,
            )
        self._last_paint_point = (layer_x, layer_y)
        self._refresh_layers(refresh_panel=False)

    def _move_selected_layer(self, dx: int, dy: int):
        layer = self._selected_layer()
        if layer is None or not layer.visible or layer.locked:
            return
        layer.x_offset += dx
        layer.y_offset += dy
        self._refresh_layers(refresh_panel=False)

    def _resize_selected_layer(self, scale: float):
        layer = self._selected_layer()
        if layer is None or not layer.visible or layer.locked:
            return
        layer.scale = max(0.1, min(4.0, scale))
        self._refresh_layers(refresh_panel=False)

    def _transform_state(self, layer: Layer) -> tuple[str, int, int, float]:
        return (layer.id, layer.x_offset, layer.y_offset, layer.scale)

    def _begin_transform_edit(self):
        layer = self._selected_layer()
        if layer is None or not layer.visible or layer.locked:
            self._active_transform_before = None
            return
        self._active_transform_before = self._transform_state(layer)

    def _finish_transform_edit(self):
        before = self._active_transform_before
        self._active_transform_before = None
        if before is None:
            return
        layer = next((item for item in self.layers if item.id == before[0]), None)
        if layer is None:
            return
        after = self._transform_state(layer)
        if before == after:
            return
        self._undo_actions.append(("transform", before, after))
        if len(self._undo_actions) > 50:
            self._undo_actions.pop(0)
        self._redo_actions.clear()

    def _restore_transform_state(self, state: tuple[str, int, int, float]) -> Layer | None:
        layer = next((item for item in self.layers if item.id == state[0]), None)
        if layer is None:
            return None
        layer.x_offset = state[1]
        layer.y_offset = state[2]
        layer.scale = state[3]
        self.selected_layer_id = layer.id
        return layer

    def _record_depth_action(self, layer: Layer):
        self._undo_actions.append(("depth", layer.id))
        if len(self._undo_actions) > 50:
            self._undo_actions.pop(0)
        self._redo_actions.clear()

    def _clear_selected_depth(self):
        layer = self._selected_layer()
        if layer is None:
            self.status_controller.warning("Select a layer before editing depth")
            return
        clear_depth(layer)
        self._record_depth_action(layer)
        self._refresh_layers(refresh_panel=False)
        self.status_controller.info(f"Cleared depth for {layer.name}")

    def _invert_selected_depth(self):
        layer = self._selected_layer()
        if layer is None:
            self.status_controller.warning("Select a layer before editing depth")
            return
        invert_depth(layer)
        self._record_depth_action(layer)
        self._refresh_layers(refresh_panel=False)
        self.status_controller.info(f"Inverted depth for {layer.name}")

    def _blur_selected_depth(self):
        layer = self._selected_layer()
        if layer is None:
            self.status_controller.warning("Select a layer before editing depth")
            return
        blur_depth(layer)
        self._record_depth_action(layer)
        self._refresh_layers(refresh_panel=False)
        self.status_controller.info(f"Blurred depth for {layer.name}")

    def _undo_selected_depth(self):
        if self._undo_actions:
            action = self._undo_actions.pop()
            if action[0] == "state":
                self._restore_project_snapshot(action[1])
                self._redo_actions.append(action)
                self.status_controller.info(f"Undid {action[3].lower()}")
                return
            if action[0] == "transform":
                self._restore_transform_state(action[1])
                self._last_paint_point = None
                self._redo_actions.append(action)
                self._refresh_layers(refresh_panel=False)
                self.status_controller.info("Undid layer transform")
                return
            if action[0] == "depth":
                layer = next((item for item in self.layers if item.id == action[1]), None)
                if layer is not None and undo_depth(layer):
                    self.selected_layer_id = layer.id
                    self._last_paint_point = None
                    self._redo_actions.append(action)
                    self._refresh_layers(refresh_panel=False)
                    self.status_controller.info("Undid depth edit")
                return
        layer = self._selected_layer()
        if layer is not None and undo_depth(layer):
            self._last_paint_point = None
            self._refresh_layers(refresh_panel=False)
            self.status_controller.info("Undid depth edit")

    def _redo_selected_depth(self):
        if self._redo_actions:
            action = self._redo_actions.pop()
            if action[0] == "state":
                self._restore_project_snapshot(action[2])
                self._undo_actions.append(action)
                self.status_controller.info(f"Redid {action[3].lower()}")
                return
            if action[0] == "transform":
                self._restore_transform_state(action[2])
                self._last_paint_point = None
                self._undo_actions.append(action)
                self._refresh_layers(refresh_panel=False)
                self.status_controller.info("Redid layer transform")
                return
            if action[0] == "depth":
                layer = next((item for item in self.layers if item.id == action[1]), None)
                if layer is not None and redo_depth(layer):
                    self.selected_layer_id = layer.id
                    self._last_paint_point = None
                    self._undo_actions.append(action)
                    self._refresh_layers(refresh_panel=False)
                    self.status_controller.info("Redid depth edit")
                return
        layer = self._selected_layer()
        if layer is not None and redo_depth(layer):
            self._last_paint_point = None
            self._refresh_layers(refresh_panel=False)
            self.status_controller.info("Redid depth edit")

    def _auto_depth_placeholder(self):
        self.status_controller.info("Auto Depth is reserved for Phase 7; manual painting is active")

    def closeEvent(self, event):
        size = self.size()
        self.settings.window_width = size.width()
        self.settings.window_height = size.height()
        save_settings(self.settings)
        super().closeEvent(event)
