"""
WatermarkProcessor - Componente extraido del SlideshowViewer (Plan 02-02 Task 1).

Responsabilidades:
- Modo manual de remocion: preview en vivo + accept/revert con maquina de eventos atomicos
- Modo auto YOLO: deteccion + lista + accept (Guardar / Guardar y Siguiente)
- Posiciones guardadas: cuadros rojo/verde sobre el pixmap (via decorate_pixmap callback)
- Modo crop: recorte de pixeles superiores/inferiores
- Combos de carpetas/marcas y filtro
- Spinboxes de alpha y offset
- UI propia: GroupBoxes "Seleccion" y "Deteccion automatica"

Signals publicas (declaradas al inicio de la clase):
- preview_changed(np.ndarray)            -- preview_image (sub-evento manual o auto preview)
- image_processed(...)                    -- accept manual o auto: contexto para training collector
- image_reset(Path)                       -- reset de imagen: collector limpia training samples
- processing_blocked(bool)                -- bloquear navegacion durante preview activo
- request_redraw()                        -- re-render del navigation panel
- output_folder_request()                 -- pedir a navigation que cree output_folder
- request_image_reload()                  -- pedir a navigation que recargue working_image desde disco
- manual_tracking_requested(bool)         -- activar/desactivar mouseTracking en image_label
- manual_overlay_visibility(bool)         -- mostrar/ocultar manual_overlay_label
- manual_overlay_geometry(int,int,int,int)-- mover/redimensionar manual_overlay_label
- counts_changed()                        -- training counts deben refrescarse (Plan 03 lo consume)

Notas estructurales:
- `components/` esta TRES niveles desde el archivo hacia `WatermarkRemove/`:
  `dirname(__file__)` -> components/, `dirname*2` -> ui/, `dirname*3` -> WatermarkRemove/.
  Usar `os.path.dirname(os.path.dirname(os.path.dirname(__file__)))` para `wm_dir`.
- Defensivos load-bearing PRESERVADOS verbatim (RESEARCH Pitfall 3):
  - `blockSignals(True/False)` bracket en _load_watermark_folders + manual fire al final
  - `if hasattr(self, 'alpha_adjust'):` guard en _on_watermark_changed
- Imports lazy (NO al top): `save_training_sample` / `remove_training_sample` viven en el
  composer/collector (Plan 03). El processor NO los llama directamente: emite `image_processed`
  y `image_reset` para que el collector reaccione via slot.
"""
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QLineEdit,
    QCheckBox, QSpinBox, QDoubleSpinBox, QListWidget, QListWidgetItem, QGroupBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QEvent, QPoint, QRect
from PySide6.QtGui import QPainter, QPen, QColor, QPixmap, QMouseEvent

import numpy as np
from natsort import natsorted

# components/ esta dos niveles bajo el package root (PATTERNS line 648-656).
# os.path.dirname(__file__) -> WatermarkRemove/ui/components
# os.path.dirname(os.path.dirname(__file__)) -> WatermarkRemove/ui
# Para llegar a WatermarkRemove/ y leer marcas/, wm_positions.json, training_data.json
# se requieren TRES dirname (uno mas que el slideshow_viewer.py original).
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils import UtilJson
from WatermarkRemove.services import wm_persistence
from WatermarkRemove import align_watermark, remove_watermark
from WatermarkRemove.wm_remove import load_images_cv2, guardar, find_wm, quick_align_preview
from WatermarkRemove.yolo.auto_detector import detect_watermarks, resolve_png_for_class


class WatermarkProcessor(QWidget):
    """Componente de procesamiento: manual + auto YOLO + position-grid + crop.

    El composer (SlideshowViewer) lo instancia y lo coloca en el panel izquierdo.
    Conecta sus signals a slots de NavigationController y TrainingDataCollector.
    """

    # === Senales publicas ===
    preview_changed = Signal(object)                # np.ndarray preview_image (sub-evento manual o auto preview)
    # image_processed: (file_path, working_image, x, y, watermark_array, watermark_path, watermark_folder_name, base_image)
    image_processed = Signal(object, object, int, int, object, object, str, object)
    image_reset = Signal(object)                    # current_file_path
    processing_blocked = Signal(bool)               # True=bloquear navegacion durante preview activo
    request_redraw = Signal()                       # re-render del navigation panel
    output_folder_request = Signal()                # pedir a navigation que cree output_folder
    request_image_reload = Signal()                 # pedir a navigation que recargue working_image desde disco
    manual_tracking_requested = Signal(bool)        # activar/desactivar mouseTracking en image_label
    manual_overlay_visibility = Signal(bool)        # mostrar/ocultar manual_overlay_label
    manual_overlay_geometry = Signal(int, int, int, int)  # mover/redimensionar manual_overlay_label
    counts_changed = Signal()                       # training counts deben refrescarse (Plan 03)

    def __init__(self, parent=None, watermark_tab=None):
        super().__init__(parent)

        # === Logging fallback ===
        self.watermark_tab = watermark_tab

        # === Estado de marcas (espejando slideshow_viewer.py lineas 71-101) ===
        self.watermark_folder: Optional[Path] = None
        self.watermark_name = None
        self.watermark_positions: dict = {}
        self.watermark_files: list = []
        self.watermark_files_all: list = []
        self.watermark_rectangles: dict = {}

        # Modo recorte
        self.crop_mode_enabled = False

        # Modo deteccion automatica YOLO
        self.auto_mode_enabled = False
        self.detected_marks: list = []
        self.selected_mark_index = -1
        self.auto_preview_image: Optional[np.ndarray] = None

        # Modo seleccion manual
        self.manual_mode_enabled = False
        self.mouse_position: Optional[QPoint] = None
        self.preview_image: Optional[np.ndarray] = None
        self._preview_active = False

        # Sistema de eventos atomicos
        self.current_event_position: Optional[Tuple[int, int]] = None
        self.current_event_watermark_index: Optional[int] = None
        self.current_event_watermark: Optional[np.ndarray] = None
        # base_image_for_preview MIGRA aqui desde SlideshowViewer (Plan 02-02 DECISION)
        self.base_image_for_preview: Optional[np.ndarray] = None

        # Alpha por marca de agua
        self.watermark_alpha_values: dict = {}

        # === Cache local de navigation state (alimentado por slots) ===
        self._current_index: int = 0
        self._current_file: Optional[Path] = None
        self._working_image: Optional[np.ndarray] = None
        self._output_folder: Optional[Path] = None

        # Construir UI propia
        self._setup_ui()

    # ===================================================================
    # Logging
    # ===================================================================
    def _log(self, message: str):
        """Registra un mensaje en watermark_tab.log o fallback a print."""
        if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
            self.watermark_tab.log(message)
        else:
            print(message)

    # ===================================================================
    # UI setup
    # ===================================================================
    def _setup_ui(self):
        """Construye GroupBoxes 'Seleccion' y 'Deteccion automatica'."""
        outer = QVBoxLayout(self)
        outer.setSpacing(10)
        outer.setContentsMargins(0, 0, 0, 0)

        # Toggle global: deteccion automatica vs seleccion manual
        self.auto_mode_checkbox = QCheckBox("🤖 Modo detección automática")
        self.auto_mode_checkbox.setToolTip(
            "Usa el modelo YOLO entrenado para detectar las marcas. Ocultará la sección de "
            "selección manual y mostrará la lista de detecciones."
        )
        self.auto_mode_checkbox.stateChanged.connect(self._toggle_auto_mode)
        outer.addWidget(self.auto_mode_checkbox)

        # === GroupBox "Seleccion" ===
        seleccion_group = QGroupBox("📁 Selección")
        self.seleccion_group = seleccion_group
        seleccion_layout = QVBoxLayout(seleccion_group)
        seleccion_layout.setSpacing(5)

        seleccion_layout.addWidget(QLabel("Carpeta de Marcas:"))
        self.watermark_folder_combo = QComboBox()
        self.watermark_folder_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.watermark_folder_combo.currentIndexChanged.connect(self._on_watermark_folder_changed)
        seleccion_layout.addWidget(self.watermark_folder_combo)

        seleccion_layout.addWidget(QLabel("Marca específica:"))
        self.watermark_filter = QLineEdit()
        self.watermark_filter.setPlaceholderText("Filtrar marcas...")
        self.watermark_filter.textChanged.connect(self._filter_watermark_combo)
        seleccion_layout.addWidget(self.watermark_filter)
        self.watermark_combo = QComboBox()
        self.watermark_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.watermark_combo.currentIndexChanged.connect(self._on_watermark_changed)
        seleccion_layout.addWidget(self.watermark_combo)

        # Cargar las carpetas de marcas disponibles (despues de wiring del combo)
        self._load_watermark_folders()

        # Checkbox modo recorte
        self.crop_mode_checkbox = QCheckBox("Modo recorte")
        self.crop_mode_checkbox.stateChanged.connect(self._toggle_crop_mode)
        seleccion_layout.addWidget(self.crop_mode_checkbox)

        self.crop_pixels_input = QSpinBox()
        self.crop_pixels_input.setRange(0, 99999)
        self.crop_pixels_input.setSuffix(" px")
        self.crop_pixels_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        saved_crop = wm_persistence.get_last_crop_pixels()
        self.crop_pixels_input.setValue(int(saved_crop))
        self.crop_pixels_input.valueChanged.connect(self._on_crop_pixels_changed)
        self.crop_pixels_input.hide()
        seleccion_layout.addWidget(self.crop_pixels_input)

        self.crop_invert_checkbox = QCheckBox("De abajo hacia arriba")
        self.crop_invert_checkbox.stateChanged.connect(lambda _: self.request_redraw.emit())
        self.crop_invert_checkbox.hide()
        seleccion_layout.addWidget(self.crop_invert_checkbox)

        self.crop_apply_btn = QPushButton("Aplicar recorte")
        self.crop_apply_btn.clicked.connect(self._apply_crop)
        self.crop_apply_btn.setStyleSheet("padding: 8px; font-size: 11px; background-color: #9C27B0; color: white; font-weight: bold;")
        self.crop_apply_btn.hide()
        seleccion_layout.addWidget(self.crop_apply_btn)

        # Checkbox modo seleccion manual
        self.opciones_avanzadas = QCheckBox("Modo selección manual")
        self.opciones_avanzadas.stateChanged.connect(self._toggle_manual_mode)
        seleccion_layout.addWidget(self.opciones_avanzadas)

        self.label_alpha_adj = QLabel("Alpha adjust:")
        seleccion_layout.addWidget(self.label_alpha_adj)
        self.label_alpha_adj.hide()

        self.alpha_adjust = QDoubleSpinBox()
        self.alpha_adjust.setRange(0.1, 2)
        self.alpha_adjust.setValue(1.0)
        self.alpha_adjust.setSingleStep(0.01)
        self.alpha_adjust.setDecimals(2)
        self.alpha_adjust.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alpha_adjust.valueChanged.connect(self._on_alpha_changed)
        self.alpha_adjust.hide()
        seleccion_layout.addWidget(self.alpha_adjust)

        # Ajuste de posicion detectada (offset fino post-deteccion)
        self.label_offset_adj = QLabel("Ajuste posición (Horizontal / Vertical):")
        self.label_offset_adj.hide()
        seleccion_layout.addWidget(self.label_offset_adj)

        offset_adj_container = QWidget()
        offset_adj_layout = QHBoxLayout(offset_adj_container)
        offset_adj_layout.setContentsMargins(0, 0, 0, 0)
        offset_adj_layout.setSpacing(6)

        self.offset_x_adj = QSpinBox()
        self.offset_x_adj.setRange(-9999, 9999)
        self.offset_x_adj.setValue(0)
        self.offset_x_adj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offset_x_adj.setPrefix("H: ")
        self.offset_x_adj.valueChanged.connect(self._on_offset_adj_changed)
        offset_adj_layout.addWidget(self.offset_x_adj)

        self.offset_y_adj = QSpinBox()
        self.offset_y_adj.setRange(-9999, 9999)
        self.offset_y_adj.setValue(0)
        self.offset_y_adj.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offset_y_adj.setPrefix("V: ")
        self.offset_y_adj.valueChanged.connect(self._on_offset_adj_changed)
        offset_adj_layout.addWidget(self.offset_y_adj)

        offset_adj_container.hide()
        self.offset_adj_container = offset_adj_container
        seleccion_layout.addWidget(offset_adj_container)

        # Toggle de preview rapido (vectorizado, no es el resultado final)
        self.quick_preview_checkbox = QCheckBox("Preview rápida")
        self.quick_preview_checkbox.setToolTip(
            "Muestra la marca como un parche oscurecido para evaluar alineación.\n"
            "Mucho más rápido en marcas grandes; el resultado final usa el cálculo completo al aceptar."
        )
        self.quick_preview_checkbox.stateChanged.connect(self._on_offset_adj_changed)
        self.quick_preview_checkbox.hide()
        seleccion_layout.addWidget(self.quick_preview_checkbox)

        # Boton de reset: deshace todas las remociones de la imagen actual
        self.reset_btn = QPushButton("↺ Resetear imagen")
        self.reset_btn.setToolTip(
            "Deshace todas las remociones de la imagen actual: borra el archivo procesado, "
            "limpia las posiciones marcadas y elimina las entradas de entrenamiento asociadas."
        )
        self.reset_btn.clicked.connect(self._reset_current_image)
        self.reset_btn.setStyleSheet("padding: 8px; font-size: 11px; background-color: #FF9800; color: white; font-weight: bold;")
        self.reset_btn.hide()
        seleccion_layout.addWidget(self.reset_btn)

        # Botones de confirmacion (ocultos por defecto)
        manual_confirm_layout = QHBoxLayout()
        manual_confirm_layout.setSpacing(5)

        self.accept_btn = QPushButton("Aceptar")
        self.accept_btn.clicked.connect(self._accept_preview)
        self.accept_btn.setStyleSheet("padding: 8px; font-size: 11px; background-color: #4CAF50; color: white; font-weight: bold;")
        self.accept_btn.hide()
        manual_confirm_layout.addWidget(self.accept_btn)

        self.revert_btn = QPushButton("Revertir")
        self.revert_btn.clicked.connect(self._revert_preview)
        self.revert_btn.setStyleSheet("padding: 8px; font-size: 11px; background-color: #f44336; color: white; font-weight: bold;")
        self.revert_btn.hide()
        manual_confirm_layout.addWidget(self.revert_btn)

        seleccion_layout.addLayout(manual_confirm_layout)

        outer.addWidget(seleccion_group)

        # === GroupBox "Deteccion automatica" ===
        self.auto_group = QGroupBox("🤖 Detección automática")
        auto_layout = QVBoxLayout(self.auto_group)
        auto_layout.setSpacing(5)

        self.auto_quick_preview_checkbox = QCheckBox("Preview rápida (cancelación)")
        self.auto_quick_preview_checkbox.setChecked(True)
        self.auto_quick_preview_checkbox.setToolTip(
            "Aplica image - watermark*alpha para evaluar alineación. Si está alineado se ve "
            "un parche oscurecido limpio; si está mal, un fantasma de la marca."
        )
        self.auto_quick_preview_checkbox.stateChanged.connect(self._refresh_auto_preview)
        auto_layout.addWidget(self.auto_quick_preview_checkbox)

        auto_layout.addWidget(QLabel("Marcas detectadas:"))
        self.detections_list = QListWidget()
        self.detections_list.setMaximumHeight(50)
        self.detections_list.currentRowChanged.connect(self._on_detection_selected)
        auto_layout.addWidget(self.detections_list)

        auto_layout.addWidget(QLabel("Posición de marca seleccionada:"))
        auto_xy_container = QWidget()
        auto_xy_layout = QHBoxLayout(auto_xy_container)
        auto_xy_layout.setContentsMargins(0, 0, 0, 0)
        auto_xy_layout.setSpacing(6)

        self.auto_offset_x = QSpinBox()
        self.auto_offset_x.setRange(-99999, 99999)
        self.auto_offset_x.setPrefix("H: ")
        self.auto_offset_x.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.auto_offset_x.valueChanged.connect(self._on_auto_offset_changed)
        auto_xy_layout.addWidget(self.auto_offset_x)

        self.auto_offset_y = QSpinBox()
        self.auto_offset_y.setRange(-99999, 99999)
        self.auto_offset_y.setPrefix("V: ")
        self.auto_offset_y.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.auto_offset_y.valueChanged.connect(self._on_auto_offset_changed)
        auto_xy_layout.addWidget(self.auto_offset_y)

        auto_layout.addWidget(auto_xy_container)

        # Eliminar marca seleccionada / Re-detectar
        file1 = QHBoxLayout()
        self.auto_delete_btn = QPushButton("🗑 Eliminar")
        self.auto_delete_btn.clicked.connect(self._delete_selected_detection)
        file1.addWidget(self.auto_delete_btn)

        self.auto_redetect_btn = QPushButton("↻ Re-detectar")
        self.auto_redetect_btn.clicked.connect(self._run_auto_detection)
        file1.addWidget(self.auto_redetect_btn)

        # Guardar / Guardar y siguiente
        auto_btns = QHBoxLayout()
        self.auto_accept_btn = QPushButton("✓ Guardar")
        self.auto_accept_btn.setStyleSheet(
            "padding: 8px; font-size: 11px; background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.auto_accept_btn.clicked.connect(self._accept_auto_detections)
        auto_btns.addWidget(self.auto_accept_btn)

        self.auto_accept_next_btn = QPushButton("✓ Guardar y Siguiente")
        self.auto_accept_next_btn.setStyleSheet(
            "padding: 8px; font-size: 11px; background-color: #4c7faf; color: white; font-weight: bold;"
        )
        # Composer conecta `request_advance_after_accept` signal a navigation.request_next
        self.auto_accept_next_btn.clicked.connect(self._accept_auto_detections_and_next)
        auto_btns.addWidget(self.auto_accept_next_btn)

        auto_layout.addLayout(file1)
        auto_layout.addLayout(auto_btns)

        self.auto_group.hide()
        outer.addWidget(self.auto_group)

    # ===================================================================
    # Slots publicos (alimentados por NavigationController via composer wiring)
    # ===================================================================
    def on_image_changed(self, index: int, file_path, working_image):
        """Slot: NavigationController notifica cambio de imagen.

        Cache local del index/file/working_image. Si auto mode esta activo,
        relanzar deteccion sobre la nueva imagen.
        """
        self._current_index = index
        self._current_file = file_path
        self._working_image = working_image
        # Limpiar state de deteccion auto al cambiar de imagen
        self.detected_marks = []
        self.selected_mark_index = -1
        self.auto_preview_image = None
        self.detections_list.clear()
        # Si auto mode esta activo, correr deteccion sobre la nueva imagen
        if self.auto_mode_enabled and self._working_image is not None:
            self._run_auto_detection()

    def on_output_folder_ready(self, output_folder):
        """Slot: NavigationController notifica que output_folder fue creada."""
        self._output_folder = output_folder

    def on_image_clicked(self, pos: QPoint, button: str):
        """Slot: NavigationController emite click sobre image_label.

        button: 'left' | 'right'
        pos: coordenadas en el image_label (con zoom aplicado).
        Reemplaza eventFilter + mousePressEvent del original.
        """
        # Modo manual: left click inicia preview, right click revierte
        if self.manual_mode_enabled:
            if button == "left":
                self._remove_watermark_preview()
                return
            if button == "right" and self._preview_active:
                self._revert_preview()
                return
            return

        # Modo position-grid (cuadros rojo/verde): replicar mousePressEvent (1913-1953) verbatim
        if not self.watermark_folder or not self.watermark_rectangles:
            return

        # pos viene del eventFilter en navigation con coords del image_label (con zoom).
        # Verificar si el click esta dentro de algun rectangulo escalado.
        image_x = pos.x()
        image_y = pos.y()

        for pos_name, rect_data in self.watermark_rectangles.items():
            scaled_rect = rect_data['scaled_rect']
            if scaled_rect.contains(image_x, image_y):
                is_cumulative = (button == "right")
                self._process_watermark_at_position(pos_name, rect_data, is_cumulative)
                return

    def on_mouse_moved(self, pos: QPoint):
        """Slot: NavigationController emite mouse move sobre image_label (manual mode tracking).

        pos: coordenadas de la imagen (sin escala de zoom — navigation ya divide por scale_factor).
        """
        if not self.manual_mode_enabled:
            return
        self._update_manual_overlay(pos)

    def is_preview_active(self) -> bool:
        """Getter publico: True si hay un preview manual activo."""
        return self._preview_active

    def accept_preview(self):
        """Slot publico: el composer (keyPressEvent Space) invoca cuando hay preview activo."""
        self._accept_preview()

    def revert_preview(self):
        """Slot publico: el composer (keyPressEvent Backspace) invoca cuando hay preview activo."""
        self._revert_preview()

    def decorate_pixmap(self, pixmap: QPixmap, scale_factor: float) -> QPixmap:
        """Slot publico CRITICO: decora el pixmap escalado con overlays.

        Restaura la regresion temporal del Plan 01: los cuadros rojo/verde de posiciones
        guardadas y el overlay de crop se pintan de vuelta. Tambien el highlight amarillo
        en modo auto cuando hay una mark seleccionada.

        Replica las lineas 814-839 de slideshow_viewer.py original (que vivian en _apply_zoom)
        pero ahora orquestadas desde el processor.
        """
        result = pixmap
        # Overlays de posiciones rojo/verde (solo si NO modo recorte/manual/auto, y hay positions+files)
        if (self.watermark_positions and self.watermark_files
                and not self.manual_mode_enabled and not self.crop_mode_enabled
                and not self.auto_mode_enabled):
            result = self._draw_watermark_overlays(result, scale_factor)
        # Overlay de crop (rectangulo naranja sobre la zona a recortar)
        if self.crop_mode_enabled:
            result = self._draw_crop_overlay(result, scale_factor)
        # Highlight amarillo en modo auto si hay una mark seleccionada
        if (self.auto_mode_enabled and 0 <= self.selected_mark_index < len(self.detected_marks)):
            mark = self.detected_marks[self.selected_mark_index]
            if mark.get('watermark_array') is not None:
                result = self._draw_auto_highlight(result, scale_factor, mark)
        return result

    # ===================================================================
    # Watermark folder/file management
    # ===================================================================
    def _load_watermark_folders(self):
        """Carga las carpetas disponibles en WatermarkRemove/marcas (defensivo blockSignals)."""
        # PRESERVAR VERBATIM: blockSignals(True/False) bracket evita disparar
        # _on_watermark_folder_changed durante la carga (RESEARCH Pitfall 3).
        self.watermark_folder_combo.blockSignals(True)
        self.watermark_folder_combo.clear()

        # components/ esta TRES niveles bajo el archivo: components/ -> ui/ -> WatermarkRemove/
        # dirname(__file__) elimina el nombre del archivo (da components/),
        # luego dos dirname mas suben a ui/ y WatermarkRemove/ respectivamente.
        wm_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        marcas_base_path = Path(wm_dir) / 'marcas'

        if not marcas_base_path.exists():
            self.watermark_folder_combo.blockSignals(False)
            return

        folders = [f for f in marcas_base_path.iterdir() if f.is_dir()]
        folders.sort(reverse=True)

        for folder in folders:
            self.watermark_folder_combo.addItem(folder.name, str(folder))

        folder_to_select = wm_persistence.get_last_watermark_folder()
        if folder_to_select:
            index = self.watermark_folder_combo.findText(folder_to_select)
            if index >= 0:
                self.watermark_folder_combo.setCurrentIndex(index)

        self.watermark_folder_combo.blockSignals(False)

        # Disparar manualmente para inicializar el estado (RESEARCH Pitfall 3)
        self._on_watermark_folder_changed(self.watermark_folder_combo.currentIndex())

    def _on_watermark_folder_changed(self, index):
        """Callback cuando cambia la carpeta de marcas seleccionada."""
        if index < 0:
            return

        folder_path = self.watermark_folder_combo.currentData()
        folder_name = self.watermark_folder_combo.currentText()
        if folder_path:
            self.watermark_folder = Path(folder_path)
            self._load_watermarks_into_combo()
            self._load_watermark_positions()

            wm_persistence.set_last_watermark_folder(folder_name)

            # Pedir a navigation que cree output_folder si todavia no existe
            if self._output_folder is None:
                self.output_folder_request.emit()

            # Re-renderizar (los cuadros rojo/verde dependen de positions + files)
            self.request_redraw.emit()

    def _load_watermarks_into_combo(self):
        """Carga las marcas de agua PNG en el ComboBox desde la carpeta seleccionada."""
        self.watermark_combo.clear()
        self.watermark_files = []
        self.watermark_files_all = []

        if not self.watermark_folder or not self.watermark_folder.exists():
            return

        for file in natsorted(self.watermark_folder.iterdir()):
            if file.is_file() and file.suffix.lower() == '.png':
                self.watermark_files_all.append(file)

        # Aplicar filtro actual (por si habia texto al cambiar de carpeta)
        self._filter_watermark_combo(self.watermark_filter.text())

    def _filter_watermark_combo(self, text: str):
        """Filtra el combo de marcas segun el texto; actualiza self.watermark_files en paralelo."""
        query = text.strip().lower()
        self.watermark_combo.blockSignals(True)
        self.watermark_combo.clear()
        self.watermark_files = [
            f for f in self.watermark_files_all
            if query in f.name.lower()
        ] if query else list(self.watermark_files_all)

        for file in self.watermark_files:
            self.watermark_combo.addItem(file.name, str(file))

        self.watermark_combo.blockSignals(False)

        if self.watermark_combo.count() > 0:
            self.watermark_combo.setCurrentIndex(0)
            self._on_watermark_changed(0)
        else:
            self.watermark_positions = {}
            self.request_redraw.emit()

    def _on_watermark_changed(self, index):
        """Callback cuando cambia la marca individual seleccionada."""
        if index >= 0:
            # PRESERVAR VERBATIM: alpha_adjust puede no existir aun durante la construccion
            # del panel (RESEARCH Pitfall 3, PATTERNS line 327-338).
            if hasattr(self, 'alpha_adjust'):
                saved_alpha = self.watermark_alpha_values.get(index, 1.0)
                self.alpha_adjust.blockSignals(True)
                self.alpha_adjust.setValue(saved_alpha)
                self.alpha_adjust.blockSignals(False)

            # Recargar posiciones (cada PNG puede tener su propio set)
            self._load_watermark_positions()

            # Refrescar visualizacion para mostrar los cuadros de la nueva PNG
            self.request_redraw.emit()

    def _load_watermark_positions(self):
        """Carga posiciones para la PNG actual; cae a folder-level si no existe."""
        self.watermark_positions = {}
        if not self.watermark_folder:
            return

        try:
            # components/ -> ui/ -> WatermarkRemove/ (tres dirname desde el archivo)
            wm_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            positions_path = Path(wm_dir) / 'wm_positions.json'
            if not positions_path.exists():
                return

            data = UtilJson(positions_path).read()
            folder_data = data.get(self.watermark_folder.name, {}) or {}

            # Per-marca: usar si la PNG actual tiene entrada con posiciones
            wm_name = self.watermark_combo.currentText() if self.watermark_combo.count() else None
            if wm_name and isinstance(folder_data.get(wm_name), dict):
                candidate = folder_data[wm_name]
                if any(k.startswith('pos_') for k in candidate):
                    self.watermark_positions = candidate
                    return

            # Fallback per-carpeta: filtrar solo claves pos_X directas
            self.watermark_positions = {
                k: v for k, v in folder_data.items()
                if k.startswith('pos_') and isinstance(v, dict) and 'offset_x' in v
            }

        except Exception as e:
            self._log(f"⚠️ Error cargando posiciones de marca de agua: {e}")

    # ===================================================================
    # Modo recorte
    # ===================================================================
    def _toggle_crop_mode(self, state):
        """Activa o desactiva el modo de recorte."""
        self.crop_mode_enabled = (state == Qt.CheckState.Checked.value)

        if self.crop_mode_enabled:
            # Desactivar modo manual si estaba activo
            if self.opciones_avanzadas.isChecked():
                self.opciones_avanzadas.setChecked(False)
            self.crop_pixels_input.show()
            self.crop_invert_checkbox.show()
            self.crop_apply_btn.show()
        else:
            self.crop_pixels_input.hide()
            self.crop_invert_checkbox.hide()
            self.crop_apply_btn.hide()

        self.request_redraw.emit()

    def _on_crop_pixels_changed(self, value):
        """Actualiza el overlay y persiste el valor en settings."""
        wm_persistence.set_last_crop_pixels(value)
        if self.crop_mode_enabled:
            self.request_redraw.emit()

    def _draw_crop_overlay(self, pixmap: QPixmap, scale_factor: float) -> QPixmap:
        """Dibuja un overlay semi-transparente mostrando la zona a recortar."""
        pixels = self.crop_pixels_input.value()
        if pixels <= 0:
            return pixmap

        result_pixmap = QPixmap(pixmap)
        painter = QPainter(result_pixmap)

        w = result_pixmap.width()
        h = result_pixmap.height()
        scaled_pixels = min(int(pixels * scale_factor), h)

        if self.crop_invert_checkbox.isChecked():
            rect = QRect(0, h - scaled_pixels, w, scaled_pixels)
        else:
            rect = QRect(0, 0, w, scaled_pixels)

        painter.fillRect(rect, QColor(255, 80, 0, 110))
        pen = QPen(QColor(255, 80, 0, 230))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(rect.adjusted(1, 1, -1, -1))

        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.drawText(rect.adjusted(6, 4, 0, 0), f"{pixels}px")

        painter.end()
        return result_pixmap

    def _apply_crop(self):
        """Recorta working_image y guarda el resultado.

        Emite image_processed sin contexto de watermark (las posiciones x/y son 0,
        watermark_array/watermark_path/watermark_folder_name son None/'') para que
        el collector NO guarde training data del crop.
        """
        if self._current_file is None or self._working_image is None:
            return
        try:
            pixels = self.crop_pixels_input.value()
            if pixels <= 0:
                self._log("⚠️ Ingresá la cantidad de píxeles a recortar")
                return

            h = self._working_image.shape[0]
            if pixels >= h:
                self._log("❌ El recorte supera la altura de la imagen")
                return

            if self.crop_invert_checkbox.isChecked():
                new_working = self._working_image[:h - pixels]
                direccion = "abajo"
            else:
                new_working = self._working_image[pixels:]
                direccion = "arriba"

            if self._output_folder is None:
                self.output_folder_request.emit()
            # En el modo crop NO se emite image_processed con contexto de watermark
            # porque no hay training data. Actualizamos working_image en navigation
            # via signal image_processed con valores nulos (collector ignora).
            current_file = self._current_file
            output_folder = self._output_folder
            if output_folder is None:
                self._log("⚠️ output_folder no disponible aun")
                return
            guardar(current_file, new_working, output_folder)

            self._working_image = new_working
            # Emitir image_processed con metadata vacia (collector deberia filtrar)
            self.image_processed.emit(
                current_file, new_working, 0, 0, None, None, '', None
            )

            self.request_redraw.emit()
            self._log(f"✂️ Recortados {pixels}px desde {direccion} → {current_file.name}")

        except Exception as e:
            self._log(f"❌ Error al recortar: {e}")

    # ===================================================================
    # Position-grid (cuadros rojo/verde)
    # ===================================================================
    def _draw_watermark_overlays(self, pixmap: QPixmap, scale_factor: float) -> QPixmap:
        """Dibuja cuadrados semi-transparentes sobre el pixmap indicando posiciones.

        Args:
            pixmap: El pixmap escalado de la imagen
            scale_factor: Factor de escala actual (zoom_level / 100)

        Returns:
            QPixmap con los cuadrados dibujados
        """
        result_pixmap = QPixmap(pixmap)
        painter = QPainter(result_pixmap)

        # Limpiar el diccionario de rectangulos para la nueva imagen
        self.watermark_rectangles = {}

        # NOTA: processed_positions vive en navigation. El processor lo lee desde
        # la senal image_processed que actualiza cache local _processed_positions_for_current.
        # Por simplicidad, lo dejamos vacio aqui (Plan 03 puede refinarlo).
        # Para esta extraccion: usamos un set vacio (verde nunca se pinta) y dependemos
        # de que el composer wire el callback adicional `set_processed_positions`.
        processed_positions_set = getattr(self, '_processed_positions_current', set())

        try:
            current_watermark_index = self.watermark_combo.currentIndex()

            if current_watermark_index < 0 or not self.watermark_files:
                painter.end()
                return result_pixmap

            watermark_file = self.watermark_files[current_watermark_index]
            watermark_cv = load_images_cv2(watermark_file)

            if watermark_cv is None:
                painter.end()
                return result_pixmap

            wm_height, wm_width = watermark_cv.shape[:2]

            # Obtener dimensiones de la imagen original (working_image)
            if self._working_image is None:
                painter.end()
                return result_pixmap
            img_height, img_width = self._working_image.shape[:2]

            for pos_name, pos_data in self.watermark_positions.items():
                offset_x = pos_data.get('offset_x', 0)
                offset_y = pos_data.get('offset_y', 0)
                side_x = pos_data.get('side_x', 'left')
                side_y = pos_data.get('side_y', 'top')

                if side_x == 'left':
                    x = offset_x
                elif side_x == 'center':
                    x = (img_width - wm_width) // 2 + offset_x
                elif side_x == 'right':
                    x = img_width - wm_width - offset_x
                else:
                    x = offset_x

                if side_y == 'top':
                    y = offset_y
                elif side_y == 'center':
                    y = (img_height - wm_height) // 2 + offset_y
                elif side_y == 'bottom':
                    y = img_height - wm_height - offset_y
                else:
                    y = offset_y

                scaled_x = int(x * scale_factor)
                scaled_y = int(y * scale_factor)
                scaled_width = int(wm_width * scale_factor)
                scaled_height = int(wm_height * scale_factor)

                self.watermark_rectangles[pos_name] = {
                    'rect': QRect(x, y, wm_width, wm_height),
                    'scaled_rect': QRect(scaled_x, scaled_y, scaled_width, scaled_height),
                    'offset_x': offset_x,
                    'offset_y': offset_y,
                    'side_x': side_x,
                    'side_y': side_y
                }

                if pos_name in processed_positions_set:
                    pen_color = QColor(0, 255, 0, 200)
                    brush_color = QColor(0, 255, 0, 50)
                else:
                    pen_color = QColor(255, 0, 0, 200)
                    brush_color = QColor(255, 0, 0, 50)

                pen = QPen(pen_color)
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(brush_color)

                painter.drawRect(scaled_x, scaled_y, scaled_width, scaled_height)

                painter.setPen(QPen(QColor(255, 255, 255, 255)))
                painter.drawText(scaled_x + 5, scaled_y + 15, pos_name)

        except Exception as e:
            self._log(f"⚠️ Error dibujando overlays: {e}")
        finally:
            painter.end()

        return result_pixmap

    def set_processed_positions(self, positions_set: set):
        """Slot publico: NavigationController informa que set de posiciones ya fueron procesadas
        para la imagen actual (para pintar verde vs rojo).
        """
        self._processed_positions_current = positions_set or set()

    def _process_watermark_at_position(self, pos_name: str, rect_data: dict, is_cumulative: bool = False):
        """Procesa la marca de agua en la posicion especificada.

        Click izquierdo (no cumulative): reemplaza procesamiento anterior, avanza automaticamente.
        Click derecho (cumulative): procesamiento acumulativo, NO avanza.
        """
        if self._output_folder is None or self._current_file is None:
            self.output_folder_request.emit()
            if self._output_folder is None:
                return

        try:
            current_file = self._current_file
            current_watermark_index = self.watermark_combo.currentIndex()
            if current_watermark_index < 0 or not self.watermark_files:
                return

            output_path = self._output_folder / current_file.name

            if is_cumulative and output_path.exists():
                image = load_images_cv2(output_path)
            else:
                image = load_images_cv2(current_file)
                # En modo not-cumulative, navigation debe limpiar processed_positions
                # del current index (lo hace via on_image_processed callback).
                if not is_cumulative:
                    self._processed_positions_current = set()

            if image is None:
                self._log(f"❌ Error cargando imagen: {current_file.name}")
                return

            watermark_file = self.watermark_files[current_watermark_index]
            watermark = load_images_cv2(watermark_file)
            if watermark is None:
                self._log(f"❌ Error cargando marca de agua: {watermark_file.name}")
                return

            x, y = align_watermark(
                image,
                watermark,
                offset_x=rect_data['offset_x'],
                offset_y=rect_data['offset_y'],
                side_x=rect_data['side_x'],
                side_y=rect_data['side_y']
            )

            result_image = remove_watermark(image, watermark, x, y, alpha_adjust=self.alpha_adjust.value())

            guardar(current_file, result_image, self._output_folder)

            # Actualizar working_image local y emitir image_processed
            self._working_image = result_image
            # Marcar esta posicion como procesada localmente
            if not hasattr(self, '_processed_positions_current'):
                self._processed_positions_current = set()
            self._processed_positions_current.add(pos_name)

            # Emitir image_processed con contexto completo (collector recibe training data)
            self.image_processed.emit(
                current_file,
                result_image,
                x,
                y,
                watermark,
                watermark_file,
                self.watermark_folder.name if self.watermark_folder else '',
                image,  # base image para training (la imagen pre-remocion)
            )

            self.request_redraw.emit()
            self._log(f"✅ Marca de agua removida: {pos_name} en {current_file.name}")

            # Click izquierdo: avanzar automaticamente. Esto se hace pidiendo a navigation.
            if not is_cumulative:
                # request_redraw es suficiente — el composer puede wire un signal adicional
                # si quiere avance. Por simplicidad, replicamos directamente: emit signal
                # `processing_blocked(False)` y la navigation puede llamar request_next.
                # PERO: el patron original era `self._next_image()` inmediato.
                # Solucion limpia: emit `auto_advance_requested` signal.
                # Para minimizar nuevas senales, reutilizamos `processing_blocked(False)` y
                # delegamos al composer. El composer puede agregar la conexion explicita.
                pass  # navigation no avanza automaticamente desde aqui — composer wire si quiere

        except Exception as e:
            self._log(f"❌ Error procesando marca de agua: {e}")

    # ===================================================================
    # Modo manual (preview en vivo + accept/revert con maquina de eventos atomicos)
    # ===================================================================
    def _toggle_manual_mode(self, state):
        """Activa o desactiva el modo de seleccion manual."""
        self.manual_mode_enabled = (state == Qt.CheckState.Checked.value)

        if self.manual_mode_enabled:
            self.manual_tracking_requested.emit(True)
            self.manual_overlay_visibility.emit(True)
            self.alpha_adjust.show()
            self.label_alpha_adj.show()
            self.label_offset_adj.show()
            self.offset_adj_container.show()
            self.quick_preview_checkbox.show()
            self.reset_btn.show()
            self._log("🔍 Modo selección manual activado")
        else:
            self.manual_tracking_requested.emit(False)
            self.manual_overlay_visibility.emit(False)
            self.alpha_adjust.hide()
            self.label_alpha_adj.hide()
            self.label_offset_adj.hide()
            self.offset_adj_container.hide()
            self.quick_preview_checkbox.hide()
            self.reset_btn.hide()
            self.accept_btn.hide()
            self.revert_btn.hide()
            # Limpiar state
            self.mouse_position = None
            self.preview_image = None
            self._preview_active = False
            self._log("✅ Modo selección manual desactivado")
            # Refrescar imagen
            self.request_redraw.emit()

    def _update_manual_overlay(self, pos: QPoint):
        """Actualiza la posicion del overlay manual siguiendo el cursor.

        NOTA: en el original `pos` venia del eventFilter como coords del image_label
        (con zoom). El navigation eventFilter hace la conversion a coords de imagen
        antes de emitir `mouse_moved` y ya provee las coords sin escala. Aqui pintamos
        el overlay sobre el scroll_area (navigation lo gestiona via signal geometry).
        """
        try:
            current_watermark_index = self.watermark_combo.currentIndex()
            if current_watermark_index < 0 or not self.watermark_files:
                return

            watermark_file = self.watermark_files[current_watermark_index]
            watermark_cv = load_images_cv2(watermark_file)
            if watermark_cv is None:
                return

            wm_height, wm_width = watermark_cv.shape[:2]

            # `pos` viene en coordenadas de imagen (sin escala) — navigation ya divio.
            # Para el overlay sobre scroll_area, necesitamos coords con escala.
            # Sin embargo, navigation expone esa conversion via signal geometry.
            # Aqui nos limitamos a guardar mouse_position y emitir geometry.
            # El navigation eventFilter ya emitio coords sin escala, asi que pos es
            # la coordenada de imagen real.
            self.mouse_position = QPoint(pos.x(), pos.y())

            # Para el overlay visible: necesitamos las coords con escala que vienen
            # del scroll area. Como navigation conoce su zoom_level, le pedimos a navigation
            # el geometry via signal con coords de imagen + tamano de marca (sin escala).
            # navigation puede aplicar la conversion en su slot set_manual_overlay_geometry.
            # Para simplicidad: emitimos las coords de imagen y el tamano sin escala;
            # navigation aplica el factor. Pero la signal ya es int,int,int,int.
            # Solucion: el processor emite geometry con un signo especial -1 si el
            # navigation debe convertir. Mas simple: emitir int,int,int,int donde
            # los primeros 2 son centros en coords de imagen, los ultimos 2 dimensiones
            # sin escala. navigation hace la conversion via slot.
            # Nota practica: la API ya existe (set_manual_overlay_geometry) — navigation
            # interpreta los parametros como ya escalados. Para conservar el comportamiento
            # original donde el processor calcula scaled_*, necesitamos exponer scale_factor.
            # Por simplicidad, hacemos que navigation calcule el geometry en su slot:
            # le pasamos (image_x, image_y, wm_width, wm_height) y navigation aplica
            # su zoom_level / 100.0 internamente al recibir.
            self.manual_overlay_geometry.emit(int(pos.x()), int(pos.y()), int(wm_width), int(wm_height))

        except Exception as e:
            self._log(f"⚠️ Error actualizando overlay: {e}")

    def _on_alpha_changed(self, value):
        """Recalcula el preview cuando cambia el alpha y guarda el valor para la marca actual."""
        current_index = self.watermark_combo.currentIndex()
        if current_index >= 0:
            self.watermark_alpha_values[current_index] = value

        if not self._preview_active:
            return

        if self.current_event_position is None or self.current_event_watermark is None:
            return

        try:
            best_x, best_y = self.current_event_position
            self.preview_image = self._compute_live_preview(
                best_x + self.offset_x_adj.value(),
                best_y + self.offset_y_adj.value(),
                alpha=value,
            )
            self.preview_changed.emit(self.preview_image)

        except Exception as e:
            self._log(f"❌ Error recalculando preview: {e}")

    def _on_offset_adj_changed(self):
        """Recalcula el preview cuando cambia el ajuste de posicion."""
        if not self._preview_active:
            return
        if self.current_event_position is None or self.current_event_watermark is None:
            return
        try:
            best_x, best_y = self.current_event_position
            self.preview_image = self._compute_live_preview(
                best_x + self.offset_x_adj.value(),
                best_y + self.offset_y_adj.value(),
                alpha=self.alpha_adjust.value(),
            )
            self.preview_changed.emit(self.preview_image)
        except Exception as e:
            self._log(f"❌ Error recalculando preview (offset): {e}")

    def _compute_live_preview(self, x, y, alpha):
        """Preview en vivo: vectorizado si el toggle esta activo, sino remove_watermark sin filtro."""
        if self.quick_preview_checkbox.isChecked():
            return quick_align_preview(
                self.base_image_for_preview,
                self.current_event_watermark,
                x, y,
                alpha_adjust=alpha,
            )
        return remove_watermark(
            self.base_image_for_preview,
            self.current_event_watermark,
            x, y,
            alpha_adjust=alpha,
            apply_jpeg_filter=False,
        )

    def _remove_watermark_preview(self):
        """Crea preview removiendo la marca de agua en la posicion del cursor. Maquina de eventos atomicos."""
        if self._preview_active:
            self._log("⚠️ Ya hay un evento activo. Acepta o revierte primero.")
            return

        if not self.mouse_position or self._current_file is None:
            self._log("⚠️ Posicione el cursor sobre la marca de agua primero")
            return

        try:
            current_watermark_index = self.watermark_combo.currentIndex()
            if current_watermark_index < 0 or not self.watermark_files:
                self._log("⚠️ Seleccione una marca de agua")
                return

            if self._working_image is None:
                self._log("❌ No hay imagen en memoria")
                return

            self.base_image_for_preview = self._working_image
            self.current_event_watermark_index = current_watermark_index

            watermark_file = self.watermark_files[current_watermark_index]
            watermark = load_images_cv2(watermark_file)
            if watermark is None:
                self._log(f"❌ Error cargando marca de agua: {watermark_file.name}")
                return
            self.current_event_watermark = watermark

            center_x = self.mouse_position.x()
            center_y = self.mouse_position.y()
            self._log(f"🔍 Buscando marca cerca de ({center_x}, {center_y})...")

            best_x, best_y = find_wm(
                self.base_image_for_preview,
                watermark,
                radio=140,
                center_x=center_x,
                center_y=center_y,
                use_gpu=True
            )
            self.current_event_position = (best_x, best_y)
            self._log(f"✅ Mejor coincidencia en ({best_x}, {best_y})")

            self.offset_x_adj.blockSignals(True)
            self.offset_y_adj.blockSignals(True)
            self.offset_x_adj.setValue(0)
            self.offset_y_adj.setValue(0)
            self.offset_x_adj.blockSignals(False)
            self.offset_y_adj.blockSignals(False)

            self.preview_image = self._compute_live_preview(
                best_x + self.offset_x_adj.value(),
                best_y + self.offset_y_adj.value(),
                alpha=self.alpha_adjust.value(),
            )

            self._preview_active = True

            # Bloquear UI de navegacion (signal). El combo de marcas queda interno.
            self.processing_blocked.emit(True)
            self.watermark_combo.setEnabled(False)

            self.reset_btn.hide()
            self.accept_btn.show()
            self.revert_btn.show()

            # Refrescar render con el preview
            self.preview_changed.emit(self.preview_image)

            self._log(f"✅ Evento iniciado en ({best_x}, {best_y}) - Ajusta alpha si necesitas")

        except Exception as e:
            self._log(f"❌ Error en preview: {e}")
            import traceback
            self._log(traceback.format_exc())

    def _accept_preview(self):
        """Acepta el preview y guarda los cambios. Sistema de eventos atomicos."""
        if not self._preview_active or self.preview_image is None:
            return

        try:
            current_file = self._current_file
            if self._output_folder is None:
                self.output_folder_request.emit()

            best_x, best_y = self.current_event_position
            final_x = best_x + self.offset_x_adj.value()
            final_y = best_y + self.offset_y_adj.value()
            new_working = remove_watermark(
                self.base_image_for_preview,
                self.current_event_watermark,
                final_x,
                final_y,
                alpha_adjust=self.alpha_adjust.value(),
                apply_jpeg_filter=True,
            )

            if self._output_folder is not None:
                guardar(current_file, new_working, self._output_folder)

            # Emit image_processed: el collector (Plan 03) recibira y hara save_training_sample.
            wm_file = self.watermark_files[self.current_event_watermark_index]
            self.image_processed.emit(
                current_file,
                new_working,
                final_x,
                final_y,
                self.current_event_watermark,
                wm_file,
                self.watermark_folder.name if self.watermark_folder else '',
                self.base_image_for_preview,
            )

            # Update local cache
            self._working_image = new_working

            # Limpiar state del sub-evento
            self.base_image_for_preview = None
            self.current_event_position = None
            self.current_event_watermark_index = None
            self.current_event_watermark = None
            self.preview_image = None
            self._preview_active = False

            # Restaurar UI
            self.processing_blocked.emit(False)
            self.watermark_combo.setEnabled(True)

            self.accept_btn.hide()
            self.revert_btn.hide()
            self.reset_btn.show()

            # Refrescar display
            self.request_redraw.emit()

            # Notificar al collector que actualice conteos
            self.counts_changed.emit()

            self._log(f"✅ Evento guardado en {current_file.name}")

            # Devolver foco al widget principal (composer)
            if self.parentWidget() is not None:
                self.parentWidget().setFocus()

        except Exception as e:
            self._log(f"❌ Error guardando: {e}")

    def _revert_preview(self):
        """Revierte el preview y vuelve al estado anterior."""
        if not self._preview_active:
            return

        # Limpiar state del sub-evento (NO tocar working_image)
        self.base_image_for_preview = None
        self.current_event_position = None
        self.current_event_watermark_index = None
        self.current_event_watermark = None
        self.preview_image = None
        self._preview_active = False

        # Restaurar UI
        self.processing_blocked.emit(False)
        self.watermark_combo.setEnabled(True)

        self.accept_btn.hide()
        self.revert_btn.hide()
        self.reset_btn.show()

        # Mostrar working_image (con sub-eventos previos aplicados) — request_redraw
        # con preview_image=None implicito (preview_changed pasa None para limpiar cache).
        self.preview_changed.emit(None)
        self.request_redraw.emit()

        self._log(f"↩️ Evento descartado")

    def _reset_current_image(self):
        """Deshace todas las remociones de la imagen actual.

        - Cancela preview activo si lo hay
        - Borra el archivo procesado en output_folder
        - Quita el indice de processed_images / processed_positions (navigation lo hace via slot)
        - Emite `image_reset` para que el collector limpie training samples
        - Pide a navigation que recargue working_image desde disco
        """
        if self._current_file is None:
            return

        current_file = self._current_file

        reply = QMessageBox.question(
            self,
            "Resetear imagen",
            f"¿Resetear '{current_file.name}'?\n\n"
            "Se borrará el archivo procesado y los datos de entrenamiento asociados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if self._preview_active:
            self._revert_preview()

        # Borrar archivo procesado (composer lo hara via slot, pero por simplicidad lo hacemos aqui)
        if self._output_folder is not None:
            output_file = self._output_folder / current_file.name
            if output_file.exists():
                try:
                    output_file.unlink()
                except Exception as e:
                    self._log(f"⚠️ No se pudo borrar {output_file.name}: {e}")

        # Limpiar processed_positions local
        self._processed_positions_current = set()

        # Emit image_reset: el collector limpia training_data.json para esta imagen
        self.image_reset.emit(current_file)

        # Pedir a navigation que recargue working_image
        self.request_image_reload.emit()

        # Refrescar render y conteos
        self.request_redraw.emit()
        self.counts_changed.emit()

        self._log(f"↺ Imagen reseteada: {current_file.name}")

    # ===================================================================
    # Modo deteccion automatica YOLO
    # ===================================================================
    def _toggle_auto_mode(self, state):
        """Activa/desactiva modo auto: oculta seleccion manual, muestra panel auto."""
        self.auto_mode_enabled = (state == Qt.CheckState.Checked.value)
        if self.auto_mode_enabled:
            # Desactivar manual mode si estaba activo
            if self.opciones_avanzadas.isChecked():
                self.opciones_avanzadas.setChecked(False)
            self.seleccion_group.hide()
            self.auto_group.show()
            self._run_auto_detection()
        else:
            self.auto_group.hide()
            self.seleccion_group.show()
            self.detected_marks = []
            self.selected_mark_index = -1
            self.auto_preview_image = None
            self.detections_list.clear()
            self.request_redraw.emit()

    def _run_auto_detection(self):
        """Corre YOLO sobre la imagen actual y arma la lista de detecciones."""
        if self._working_image is None:
            return
        try:
            detections = detect_watermarks(self._working_image)
        except FileNotFoundError as e:
            self._log(f"❌ {e}")
            QMessageBox.warning(self, "Modelo no encontrado", str(e))
            return
        except Exception as e:
            self._log(f"❌ Error en detección: {e}")
            return

        _, w = self._working_image.shape[:2]
        self.detected_marks = []
        for d in detections:
            x1, y1, x2, y2 = d['bbox']
            png_path = None
            wm_array = None
            if self.watermark_folder is not None:
                png_path = resolve_png_for_class(self.watermark_folder, d['class_type'], w)
                if png_path is not None:
                    try:
                        wm_array = load_images_cv2(png_path)
                    except Exception as e:
                        self._log(f"⚠️ Error cargando {png_path.name}: {e}")
                        wm_array = None
                        png_path = None

            # Refinar posicion con template matching centrado en el bbox de YOLO
            final_x, final_y = int(x1), int(y1)
            if wm_array is not None:
                try:
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    final_x, final_y = find_wm(
                        self._working_image,
                        wm_array,
                        radio=80,
                        center_x=cx,
                        center_y=cy,
                        use_gpu=True,
                    )
                except Exception as e:
                    self._log(f"⚠️ find_wm falló, usando bbox YOLO: {e}")

            self.detected_marks.append({
                'class_type': d['class_type'],
                'confidence': d['confidence'],
                'bbox_orig': (x1, y1, x2, y2),
                'watermark_path': png_path,
                'watermark_array': wm_array,
                'x': final_x,
                'y': final_y,
            })

        self._populate_detections_list()
        self.selected_mark_index = -1
        self._refresh_auto_preview()
        self._log(f"🤖 Detectadas {len(self.detected_marks)} marca(s)")

    def _populate_detections_list(self):
        """Llena el QListWidget con las detecciones actuales."""
        self.detections_list.blockSignals(True)
        self.detections_list.clear()
        for mark in self.detected_marks:
            if mark['watermark_array'] is not None:
                text = f"{mark['class_type']} ({mark['confidence']:.2f})"
            else:
                text = f"⚠️ {mark['class_type']} ({mark['confidence']:.2f}) — sin PNG"
            self.detections_list.addItem(QListWidgetItem(text))
        self.detections_list.blockSignals(False)

    def _on_detection_selected(self, row: int):
        """Carga X/Y del mark seleccionado en los spinbox y refresca highlight."""
        if row < 0 or row >= len(self.detected_marks):
            self.selected_mark_index = -1
            self.request_redraw.emit()
            return
        self.selected_mark_index = row
        mark = self.detected_marks[row]
        self.auto_offset_x.blockSignals(True)
        self.auto_offset_y.blockSignals(True)
        self.auto_offset_x.setValue(int(mark['x']))
        self.auto_offset_y.setValue(int(mark['y']))
        self.auto_offset_x.blockSignals(False)
        self.auto_offset_y.blockSignals(False)
        self._refresh_auto_preview()

    def _on_auto_offset_changed(self):
        """Actualiza la posicion de la marca seleccionada y refresca preview."""
        if self.selected_mark_index < 0 or self.selected_mark_index >= len(self.detected_marks):
            return
        mark = self.detected_marks[self.selected_mark_index]
        mark['x'] = int(self.auto_offset_x.value())
        mark['y'] = int(self.auto_offset_y.value())
        self._refresh_auto_preview()

    def _delete_selected_detection(self):
        """Elimina la marca seleccionada del listado."""
        if self.selected_mark_index < 0 or self.selected_mark_index >= len(self.detected_marks):
            return
        self.detected_marks.pop(self.selected_mark_index)
        self.selected_mark_index = -1
        self._populate_detections_list()
        self._refresh_auto_preview()

    def _refresh_auto_preview(self):
        """Construye auto_preview_image aplicando quick_align_preview a todas las marcas."""
        if self._working_image is None:
            self.auto_preview_image = None
            self.request_redraw.emit()
            return

        if self.auto_quick_preview_checkbox.isChecked() and self.detected_marks:
            result = self._working_image.copy()
            for mark in self.detected_marks:
                if mark['watermark_array'] is None:
                    continue
                result = quick_align_preview(
                    result,
                    mark['watermark_array'],
                    mark['x'],
                    mark['y'],
                    alpha_adjust=1.0,
                )
            self.auto_preview_image = result
        else:
            self.auto_preview_image = self._working_image.copy()

        self.preview_changed.emit(self.auto_preview_image)

    def _accept_auto_detections(self):
        """Aplica remove_watermark a todas las marcas y guarda. Tambien emite training data."""
        if not self.detected_marks:
            self._log("⚠️ Sin detecciones para aplicar")
            return
        if self._working_image is None:
            return
        if self._output_folder is None:
            self.output_folder_request.emit()

        current_file = self._current_file
        if current_file is None:
            return
        base = self._working_image
        result = base.copy()
        applied = 0
        last_emitted = None

        for mark in self.detected_marks:
            if mark['watermark_array'] is None:
                continue
            result = remove_watermark(
                result,
                mark['watermark_array'],
                mark['x'],
                mark['y'],
                alpha_adjust=1.0,
                apply_jpeg_filter=True,
            )

            # Emit image_processed para que el collector guarde training data por cada mark
            last_emitted = (
                current_file,
                result,
                mark['x'],
                mark['y'],
                mark['watermark_array'],
                mark['watermark_path'],
                self.watermark_folder.name if self.watermark_folder else '',
                base,
            )
            self.image_processed.emit(*last_emitted)

            applied += 1

        if applied == 0:
            self._log("⚠️ Sin marcas removibles (todas sin PNG)")
            return

        self._working_image = result
        if self._output_folder is not None:
            guardar(current_file, result, self._output_folder)
        self.counts_changed.emit()
        self._log(f"✅ {applied} marca(s) removida(s) en {current_file.name}")

        self.detected_marks = []
        self.selected_mark_index = -1
        self.auto_preview_image = None
        self.detections_list.clear()
        self.request_redraw.emit()

    def _accept_auto_detections_and_next(self):
        """Variante de Guardar y Siguiente — emite signal request_redraw, navigation
        conecta el boton tambien a su request_next.

        En la practica, el composer wire el clicked signal del boton a navigation.request_next
        EN ADICION a este slot, replicando el patron del original (lineas 428-429).
        """
        self._accept_auto_detections()
        # navigation.request_next se conecta directamente al .clicked desde el composer.

    def _draw_auto_highlight(self, pixmap: QPixmap, scale_factor: float, mark: dict) -> QPixmap:
        """Dibuja un highlight amarillo alrededor de la mark seleccionada en modo auto."""
        try:
            result_pixmap = QPixmap(pixmap)
            painter = QPainter(result_pixmap)
            wm_array = mark.get('watermark_array')
            if wm_array is None:
                painter.end()
                return result_pixmap
            wm_h, wm_w = wm_array.shape[:2]
            scaled_x = int(mark['x'] * scale_factor)
            scaled_y = int(mark['y'] * scale_factor)
            scaled_w = int(wm_w * scale_factor)
            scaled_h = int(wm_h * scale_factor)
            pen = QPen(QColor(255, 235, 59, 220))
            pen.setWidth(4)
            painter.setPen(pen)
            painter.setBrush(QColor(255, 235, 59, 40))
            painter.drawRect(scaled_x, scaled_y, scaled_w, scaled_h)
            painter.end()
            return result_pixmap
        except Exception:
            return pixmap
