"""
Visor de imágenes tipo slideshow - Navega con Space y Backspace
"""
import os
import sys
from pathlib import Path
from typing import Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QGridLayout,
    QScrollArea, QComboBox, QGroupBox, QCheckBox, QDoubleSpinBox, QMessageBox, QLineEdit, QSpinBox,
    QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QRect, QEvent, QPoint
from PySide6.QtGui import QPixmap, QKeyEvent, QWheelEvent, QPainter, QPen, QColor, QMouseEvent, QImage

# Agregar el directorio raíz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils import UtilJson
from core.utils.constants import SETTINGS_REL_DIR
import numpy as np
from natsort import natsorted
from WatermarkRemove import align_watermark, remove_watermark
from WatermarkRemove.wm_remove import load_images_cv2, guardar, find_wm, quick_align_preview
from WatermarkRemove.auto_detector import detect_watermarks, resolve_png_for_class

class SlideshowViewer(QDialog):
    """
    Visor de imágenes estilo slideshow con navegación por teclado y procesamiento de marcas de agua

    Controles de navegación:
        - Space: Siguiente imagen
        - Backspace: Imagen anterior
        - Enter: Finalizar revisión
        - Escape: Cancelar proceso

    Controles de zoom:
        - Ctrl + Rueda: Zoom in/out
        - Ctrl + Plus/Minus: Zoom in/out
        - Ctrl + 0: Reset zoom al 100%

    Procesamiento de marcas de agua:
        - Click Izquierdo: Reemplaza procesamiento (solo un cuadro verde), avanza automáticamente
        - Click Derecho: Procesamiento acumulativo (múltiples cuadros verdes), NO avanza
    """

    # Señal que se emite cuando el usuario finaliza la revisión
    review_completed = Signal(bool)  # True = continuar, False = cancelar

    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tga', '.psd', '.psb', '.jfif')

    def __init__(self, folder_path: str, parent=None, watermark_tab=None):
        super().__init__(parent)
        self.folder_path = Path(folder_path) if folder_path else None
        self.image_files = []
        self.current_index = 0
        self.user_approved = False
        self.current_pixmap = None  # Pixmap original sin zoom
        self.zoom_level = 100  # Nivel de zoom actual
        self.controls_panel_width = 280  # Ancho del panel de controles para cálculos

        # Referencia al watermark_tab para logging
        self.watermark_tab = watermark_tab

        # Información de marca de agua (se setean al elegir carpeta en el combo)
        self.watermark_folder = None
        self.watermark_name = None
        self.watermark_positions = {}  # Posiciones cargadas desde JSON
        self.watermark_files = []      # Archivos PNG visibles en el combo (subset filtrado)
        self.watermark_files_all = []  # Lista completa sin filtro

        # Procesamiento de marcas de agua
        self.output_folder = None  # Carpeta donde se guardarán las imágenes procesadas
        self.processed_images = set()  # Set de índices de imágenes ya procesadas
        self.processed_positions = {}  # Diccionario: {image_index: set(pos_names)} - posiciones procesadas por imagen
        self.watermark_rectangles = {}  # Diccionario: pos_name -> QRect (para detección de clicks)

        # Modo recorte
        self.crop_mode_enabled = False

        # Modo detección automática YOLO
        self.auto_mode_enabled = False
        self.detected_marks: list = []        # lista de dicts (ver _run_auto_detection)
        self.selected_mark_index = -1
        self.auto_preview_image: Optional[np.ndarray] = None

        # Modo selección manual
        self.manual_mode_enabled = False  # Si está activado el modo manual
        self.manual_overlay_label = None  # Label flotante para el overlay
        self.mouse_position = None  # Posición actual del cursor (QPoint)
        self.preview_image = None  # Imagen con marca removida (temporal, numpy array)
        self.is_preview_active = False  # Si hay un preview activo esperando confirmación

        # Sistema de eventos atómicos para remoción de marcas
        self.current_event_position: Optional[Tuple[int, int]] = None  # Coordenadas del click del evento actual (best_x, best_y)
        self.current_event_watermark_index: Optional[int] = None  # Índice de la marca de agua usada en el evento actual
        self.current_event_watermark: Optional[np.ndarray] = None  # Marca cacheada (BGRA) para sub-eventos del evento actual
        self.base_image_for_preview: Optional[np.ndarray] = None  # Imagen base para el sub-evento actual

        # Imagen de trabajo en memoria (fuente de verdad para edición)
        self.working_image: Optional[np.ndarray] = None

        # Alpha por marca de agua (índice -> valor alpha)
        self.watermark_alpha_values: dict = {}  # {0: 1.0, 1: 1.5, ...}

        self._setup_ui()
        self._load_image_list()

        if self.image_files:
            self._show_current_image()

    def _update_counts_label(self):
        """Lee training_data.json y actualiza el conteo de muestras por clase."""
        import json as _json

        training_json = Path(os.path.dirname(current_dir)) / 'training_data.json'
        try:
            if not training_json.exists():
                self.training_counts_label.setText("Sin datos aún")
                return
            data = _json.loads(training_json.read_text(encoding='utf-8'))
            if not data:
                self.training_counts_label.setText("Sin datos aún")
                return

            counts: dict = {}
            for entry in data:
                cls = entry.get('class_type', '?')
                counts[cls] = counts.get(cls, 0) + 1

            lines = [f"{cls}: {n}" for cls, n in sorted(counts.items())]
            total = sum(counts.values())
            lines.append(f"─────────\nTotal: {total}")
            self.training_counts_label.setText("\n".join(lines))
        except Exception:
            self.training_counts_label.setText("Sin datos aún")

    def _log(self, message: str):
        """
        Registra un mensaje en la consola de proceso del watermark_tab.
        Si no hay watermark_tab disponible, usa print como fallback.
        """
        if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
            self.watermark_tab.log(message)
        else:
            print(message)

    def _setup_ui(self):
        """Configura la interfaz de usuario con layout horizontal"""
        self.setWindowTitle("Revisión de Imágenes")
        self.setModal(True)  # Bloquea la ventana principal
        self.resize(900, 650)

        # Layout principal HORIZONTAL
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === PANEL IZQUIERDO: Controles (fijo 280px) ===
        left_panel = self._create_controls_panel()
        main_layout.addWidget(left_panel)

        # === PANEL DERECHO: Imagen con zoom ===
        right_panel = self._create_image_panel()
        main_layout.addWidget(right_panel, 1)  # stretch=1 para que use todo el espacio

    def _create_controls_panel(self) -> QWidget:
        """Crea el panel de controles (izquierda) con scroll vertical."""
        panel = QWidget()
        panel.setFixedWidth(self.controls_panel_width)

        # Scroll area que envuelve todo el contenido
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 6, 0)

        scroll.setWidget(content)

        outer = QVBoxLayout(panel)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

        # Información de carpeta  ////////////////////////////////////////
        info_group = QGroupBox("ℹ️ Info")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(5)

        # Contador de imágenes
        info_layout.addWidget(QLabel("Imagen:"))
        self.counter_label = QLabel("0 / 0")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.counter_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #2196F3; padding: 5px;")
        info_layout.addWidget(self.counter_label)

        # Nombre del archivo actual
        self.filename_label = QLabel("Sin archivo")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setStyleSheet("font-size: 12px; color: #888; padding: 10px; background-color: #1e1e1e; border-radius: 5px;")
        self.filename_label.setWordWrap(True)
        self.filename_label.setMaximumHeight(60)  # Limitar altura
        info_layout.addWidget(self.filename_label)

        layout.addWidget(info_group)

        # Toggle global: detección automática vs selección manual ////////////////////////////
        self.auto_mode_checkbox = QCheckBox("🤖 Modo detección automática")
        self.auto_mode_checkbox.setToolTip(
            "Usa el modelo YOLO entrenado para detectar las marcas. Ocultará la sección de "
            "selección manual y mostrará la lista de detecciones."
        )
        self.auto_mode_checkbox.stateChanged.connect(self._toggle_auto_mode)
        layout.addWidget(self.auto_mode_checkbox)

        # Selección  ////////////////////////////////////////
        seleccion_group = QGroupBox("📁 Selección")
        self.seleccion_group = seleccion_group
        seleccion_layout = QVBoxLayout(seleccion_group)
        seleccion_layout.setSpacing(5)

        # Selector de carpeta de marcas (desde WatermarkRemove/marcas)
        seleccion_layout.addWidget(QLabel("Carpeta de Marcas:"))
        self.watermark_folder_combo = QComboBox()
        self.watermark_folder_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.watermark_folder_combo.currentIndexChanged.connect(self._on_watermark_folder_changed)
        seleccion_layout.addWidget(self.watermark_folder_combo)

        # Selector de marca individual dentro de la carpeta
        seleccion_layout.addWidget(QLabel("Marca específica:"))
        self.watermark_filter = QLineEdit()
        self.watermark_filter.setPlaceholderText("Filtrar marcas...")
        self.watermark_filter.textChanged.connect(self._filter_watermark_combo)
        seleccion_layout.addWidget(self.watermark_filter)
        self.watermark_combo = QComboBox()
        self.watermark_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.watermark_combo.currentIndexChanged.connect(self._on_watermark_changed)
        seleccion_layout.addWidget(self.watermark_combo)

        # Cargar las carpetas de marcas disponibles
        self._load_watermark_folders()

        # Checkbox modo recorte
        self.crop_mode_checkbox = QCheckBox("Modo recorte")
        self.crop_mode_checkbox.stateChanged.connect(self._toggle_crop_mode)
        seleccion_layout.addWidget(self.crop_mode_checkbox)

        self.crop_pixels_input = QSpinBox()
        self.crop_pixels_input.setRange(0, 99999)
        self.crop_pixels_input.setSuffix(" px")
        self.crop_pixels_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Cargar último valor persistido en settings
        saved_crop = UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).get('last_crop_pixels', 0) or 0
        self.crop_pixels_input.setValue(int(saved_crop))
        self.crop_pixels_input.valueChanged.connect(self._on_crop_pixels_changed)
        self.crop_pixels_input.hide()
        seleccion_layout.addWidget(self.crop_pixels_input)

        self.crop_invert_checkbox = QCheckBox("De abajo hacia arriba")
        self.crop_invert_checkbox.stateChanged.connect(lambda _: self._apply_zoom())
        self.crop_invert_checkbox.hide()
        seleccion_layout.addWidget(self.crop_invert_checkbox)

        self.crop_apply_btn = QPushButton("Aplicar recorte")
        self.crop_apply_btn.clicked.connect(self._apply_crop)
        self.crop_apply_btn.setStyleSheet("padding: 8px; font-size: 11px; background-color: #9C27B0; color: white; font-weight: bold;")
        self.crop_apply_btn.hide()
        seleccion_layout.addWidget(self.crop_apply_btn)

        # Checkbox modo selección manual
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

        # Ajuste de posición detectada (offset fino post-detección)
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

        # Toggle de preview rápido (vectorizado, no es el resultado final)
        self.quick_preview_checkbox = QCheckBox("Preview rápida")
        self.quick_preview_checkbox.setToolTip(
            "Muestra la marca como un parche oscurecido para evaluar alineación.\n"
            "Mucho más rápido en marcas grandes; el resultado final usa el cálculo completo al aceptar."
        )
        self.quick_preview_checkbox.stateChanged.connect(self._on_offset_adj_changed)
        self.quick_preview_checkbox.hide()
        seleccion_layout.addWidget(self.quick_preview_checkbox)

        # Botón de reset: deshace todas las remociones de la imagen actual
        self.reset_btn = QPushButton("↺ Resetear imagen")
        self.reset_btn.setToolTip(
            "Deshace todas las remociones de la imagen actual: borra el archivo procesado, "
            "limpia las posiciones marcadas y elimina las entradas de entrenamiento asociadas."
        )
        self.reset_btn.clicked.connect(self._reset_current_image)
        self.reset_btn.setStyleSheet("padding: 8px; font-size: 11px; background-color: #FF9800; color: white; font-weight: bold;")
        self.reset_btn.hide()
        seleccion_layout.addWidget(self.reset_btn)

        # Botones de confirmación (ocultos por defecto)
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

        layout.addWidget(seleccion_group)

        # Detección automática YOLO  ////////////////////////////////////////
        self.auto_group = QGroupBox("🤖 Detección automática")
        auto_layout = QVBoxLayout(self.auto_group)
        auto_layout.setSpacing(5)

        # Preview vectorizado (default True)
        self.auto_quick_preview_checkbox = QCheckBox("Preview rápida (cancelación)")
        self.auto_quick_preview_checkbox.setChecked(True)
        self.auto_quick_preview_checkbox.setToolTip(
            "Aplica image - watermark*alpha para evaluar alineación. Si está alineado se ve "
            "un parche oscurecido limpio; si está mal, un fantasma de la marca."
        )
        self.auto_quick_preview_checkbox.stateChanged.connect(self._refresh_auto_preview)
        auto_layout.addWidget(self.auto_quick_preview_checkbox)

        # Lista de detecciones
        auto_layout.addWidget(QLabel("Marcas detectadas:"))
        self.detections_list = QListWidget()
        self.detections_list.setMaximumHeight(50)
        self.detections_list.currentRowChanged.connect(self._on_detection_selected)
        auto_layout.addWidget(self.detections_list)

        # Ajuste X / Y de la marca seleccionada
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

        # Eliminar marca seleccionada
        self.auto_delete_btn = QPushButton("🗑 Eliminar marca seleccionada")
        self.auto_delete_btn.clicked.connect(self._delete_selected_detection)
        auto_layout.addWidget(self.auto_delete_btn)

        # Re-detectar + Aceptar
        auto_btns = QHBoxLayout()
        self.auto_redetect_btn = QPushButton("↻ Re-detectar")
        self.auto_redetect_btn.clicked.connect(self._run_auto_detection)
        auto_btns.addWidget(self.auto_redetect_btn)

        self.auto_accept_btn = QPushButton("✓ Aceptar y guardar")
        self.auto_accept_btn.setStyleSheet(
            "padding: 8px; font-size: 11px; background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self.auto_accept_btn.clicked.connect(self._accept_auto_detections)
        auto_btns.addWidget(self.auto_accept_btn)

        auto_layout.addLayout(auto_btns)

        self.auto_group.hide()
        layout.addWidget(self.auto_group)

        # Botones de navegación y acción en cuadrícula 2x2 ////////////////////////////////////////
        nav_group = QGroupBox("✳️ Navegación")
        grid_layout = QGridLayout(nav_group)
        grid_layout.setSpacing(5)  # Reducir espacio entre botones

        # Fila 1: Navegación
        self.prev_btn = QPushButton("Anterior")
        self.prev_btn.clicked.connect(self._previous_image)
        self.prev_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #555; color: white;")
        self.prev_btn.setMaximumHeight(40)  # Altura fija
        grid_layout.addWidget(self.prev_btn, 0, 0)  # Fila 0, Columna 0

        self.next_btn = QPushButton("Siguiente")
        self.next_btn.clicked.connect(self._next_image)
        self.next_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #4CAF50; color: white; font-weight: bold;")
        self.next_btn.setMaximumHeight(40)  # Altura fija
        grid_layout.addWidget(self.next_btn, 0, 1)  # Fila 0, Columna 1

        # Fila 2: Acción
        self.finish_btn = QPushButton("Finalizar y Procesar")
        self.finish_btn.clicked.connect(self._finish_review)
        self.finish_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #2196F3; color: white; font-weight: bold;")
        self.finish_btn.setMaximumHeight(40)  # Altura fija
        grid_layout.addWidget(self.finish_btn, 1, 0)  # Fila 1, Columna 0

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel_review)
        self.cancel_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #f44336; color: white;")
        self.cancel_btn.setMaximumHeight(40)  # Altura fija
        grid_layout.addWidget(self.cancel_btn, 1, 1)  # Fila 1, Columna 1

        layout.addWidget(nav_group)

        # Conteo de datos de entrenamiento recopilados ////////////////////////////////////////
        conteo_group = QGroupBox("📊 Datos recopilados")
        conteo_layout = QVBoxLayout(conteo_group)
        conteo_layout.setSpacing(4)
        conteo_layout.setContentsMargins(8, 6, 8, 6)

        self.training_counts_label = QLabel("Sin datos aún")
        self.training_counts_label.setStyleSheet(
            "color: #aaaaaa; font-size: 10px; font-family: monospace;"
        )
        self.training_counts_label.setWordWrap(True)
        conteo_layout.addWidget(self.training_counts_label)

        layout.addWidget(conteo_group)
        self._update_counts_label()

        layout.addStretch(1)

        return panel

    def _create_image_panel(self) -> QWidget:
        """Crea el panel de imagen con zoom (derecha)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Área de scroll con imagen
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)  # Importante para que funcione el zoom
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("border: 2px solid #444; background-color: #2b2b2b;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2b2b2b;")
        scroll.setWidget(self.image_label)

        # Label flotante de zoom (encima de la imagen)
        self.zoom_overlay_label = QLabel(scroll)
        self.zoom_overlay_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 180); "
            "color: white; "
            "padding: 8px 16px; "
            "border-radius: 5px; "
            "font-size: 16px; "
            "font-weight: bold;"
        )
        self.zoom_overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_overlay_label.hide()  # Oculto por defecto

        # Timer para ocultar el label de zoom
        self.zoom_hide_timer = QTimer(self)
        self.zoom_hide_timer.timeout.connect(self._hide_zoom_overlay)
        self.zoom_hide_timer.setSingleShot(True)

        # Label flotante para overlay de selección manual
        self.manual_overlay_label = QLabel(scroll)
        self.manual_overlay_label.setStyleSheet(
            "background-color: rgba(33, 150, 243, 50); "
            "border: 3px solid rgba(33, 150, 243, 200); "
        )
        self.manual_overlay_label.hide()
        self.manual_overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(scroll, 1)

        self.scroll_area = scroll  # Guardar referencia para uso posterior

        # Instalar event filter en image_label para capturar eventos de mouse
        self.image_label.installEventFilter(self)

        return panel

    def _create_output_folder(self):
        """Crea la carpeta de salida para las imágenes procesadas"""
        if not self.folder_path:
            return

        # Nombre de la carpeta: "{nombre_original} [sin marca]"
        folder_name = self.folder_path.name + " [sin marca]"
        self.output_folder = self.folder_path.parent / folder_name

        # Crear la carpeta si no existe
        self.output_folder.mkdir(exist_ok=True)

    def _load_image_list(self):
        """Carga la lista de archivos de imagen"""
        if not self.folder_path or not self.folder_path.exists():
            return

        # Si es un archivo, usar su directorio padre
        if self.folder_path.is_file():
            self.folder_path = self.folder_path.parent

        # Buscar todas las imágenes y ordenarlas
        for file in natsorted(self.folder_path.iterdir()):
            if file.is_file() and file.suffix.lower() in self.SUPPORTED_FORMATS:
                self.image_files.append(file)

        self._update_counter()

    def _load_watermark_folders(self):
        """Carga las carpetas disponibles en WatermarkRemove/marcas"""
        # Bloquear señales para evitar que se dispare _on_watermark_folder_changed durante la carga
        self.watermark_folder_combo.blockSignals(True)

        self.watermark_folder_combo.clear()

        wm_dir = os.path.dirname(current_dir)
        marcas_base_path = Path(wm_dir) / 'marcas'

        if not marcas_base_path.exists():
            self.watermark_folder_combo.blockSignals(False)
            return

        # Obtener subcarpetas ordenadas (más recientes primero)
        folders = [f for f in marcas_base_path.iterdir() if f.is_dir()]
        folders.sort(reverse=True)

        # Agregar al combo: label = nombre, data = ruta completa
        for folder in folders:
            self.watermark_folder_combo.addItem(folder.name, str(folder))

        # Usar la última carpeta guardada en settings
        folder_to_select = UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).get('last_watermark_folder', None)

        if folder_to_select:
            index = self.watermark_folder_combo.findText(folder_to_select)
            if index >= 0:
                self.watermark_folder_combo.setCurrentIndex(index)

        # Restaurar señales
        self.watermark_folder_combo.blockSignals(False)

        # Disparar manualmente para inicializar el estado
        self._on_watermark_folder_changed(self.watermark_folder_combo.currentIndex())

    def _on_watermark_folder_changed(self, index):
        """Callback cuando cambia la carpeta de marcas seleccionada"""
        if index < 0:
            return

        folder_path = self.watermark_folder_combo.currentData()
        folder_name = self.watermark_folder_combo.currentText()
        if folder_path:
            self.watermark_folder = Path(folder_path)
            self._load_watermarks_into_combo()
            self._load_watermark_positions()

            # Guardar como última carpeta usada
            UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).set('last_watermark_folder', folder_name)

            # Crear carpeta de salida si aún no existe
            if not self.output_folder and self.folder_path:
                self._create_output_folder()

            # Actualizar la visualización
            self._show_current_image()

    def _load_watermarks_into_combo(self):
        """Carga las marcas de agua PNG en el ComboBox desde la carpeta seleccionada"""
        self.watermark_combo.clear()
        self.watermark_files = []
        self.watermark_files_all = []

        if not self.watermark_folder or not self.watermark_folder.exists():
            return

        for file in natsorted(self.watermark_folder.iterdir()):
            if file.is_file() and file.suffix.lower() == '.png':
                self.watermark_files_all.append(file)

        # Aplicar filtro actual (por si había texto al cambiar de carpeta)
        self._filter_watermark_combo(self.watermark_filter.text())

    def _filter_watermark_combo(self, text: str):
        """Filtra el combo de marcas según el texto; actualiza self.watermark_files en paralelo."""
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
            self._show_current_image()

    def _on_watermark_changed(self, index):
        """Callback cuando cambia la marca individual seleccionada"""
        if index >= 0:
            # alpha_adjust puede no existir aún si se llama durante la construcción del panel
            if hasattr(self, 'alpha_adjust'):
                saved_alpha = self.watermark_alpha_values.get(index, 1.0)
                self.alpha_adjust.blockSignals(True)
                self.alpha_adjust.setValue(saved_alpha)
                self.alpha_adjust.blockSignals(False)

            # Recargar posiciones (cada PNG puede tener su propio set)
            self._load_watermark_positions()

            # Actualizar la visualización con los nuevos cuadrados
            self._show_current_image()

    def _load_watermark_positions(self):
        """Carga posiciones para la PNG actual; cae a folder-level si no existe."""
        self.watermark_positions = {}
        if not self.watermark_folder:
            return

        try:
            wm_dir = os.path.dirname(current_dir)
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

    def _show_current_image(self):
        """Muestra la imagen actual con el zoom aplicado"""
        if not self.image_files or self.current_index >= len(self.image_files):
            return

        current_file = self.image_files[self.current_index]

        # Cargar working_image SOLO si no existe (primera vez en esta imagen)
        if self.working_image is None:
            self.working_image = load_images_cv2(current_file)

        # Convertir working_image a QPixmap para mostrar
        if self.working_image is not None:
            height, width = self.working_image.shape[:2]
            bytes_per_line = 3 * width
            q_image = QImage(self.working_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            q_image = q_image.rgbSwapped()  # OpenCV usa BGR, Qt usa RGB
            self.current_pixmap = QPixmap.fromImage(q_image)
        else:
            # Fallback a cargar desde disco si working_image falla
            self.current_pixmap = QPixmap(str(current_file))

        if not self.current_pixmap.isNull():
            # Aplicar zoom
            self._apply_zoom()

            # Ajustar el tamaño de la ventana según la imagen
            width = self.current_pixmap.width()
            height = self.current_pixmap.height()
            self._adjust_window_size(width, height)
        else:
            self.image_label.setText("Error cargando imagen")

        # Actualizar nombre de archivo
        self.filename_label.setText(f"{current_file.name}")

        # Actualizar contador
        self._update_counter()

        # Actualizar estado de botones
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)

        # Si estamos en modo auto, redetectar para la nueva imagen
        if self.auto_mode_enabled:
            self._run_auto_detection()

    def _apply_zoom(self):
        """Aplica el nivel de zoom actual a la imagen y dibuja overlays de marcas"""
        # Prioridad: preview_image (sub-evento manual) > auto_preview_image (modo auto) > working_image
        if self.is_preview_active and self.preview_image is not None:
            # Mostrar preview del sub-evento
            height, width = self.preview_image.shape[:2]
            bytes_per_line = 3 * width
            q_image = QImage(self.preview_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            q_image = q_image.rgbSwapped()  # OpenCV usa BGR, Qt usa RGB
            pixmap_to_scale = QPixmap.fromImage(q_image)
        elif self.auto_mode_enabled and self.auto_preview_image is not None:
            # Mostrar preview de detección automática
            height, width = self.auto_preview_image.shape[:2]
            bytes_per_line = 3 * width
            q_image = QImage(self.auto_preview_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            q_image = q_image.rgbSwapped()
            pixmap_to_scale = QPixmap.fromImage(q_image)
        elif self.working_image is not None:
            # Mostrar imagen de trabajo (con sub-eventos previos aplicados)
            height, width = self.working_image.shape[:2]
            bytes_per_line = 3 * width
            q_image = QImage(self.working_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            q_image = q_image.rgbSwapped()  # OpenCV usa BGR, Qt usa RGB
            pixmap_to_scale = QPixmap.fromImage(q_image)
        else:
            # Fallback a pixmap original
            if self.current_pixmap is None or self.current_pixmap.isNull():
                return
            pixmap_to_scale = self.current_pixmap

        # Calcular nuevo tamaño basado en zoom
        scale_factor = self.zoom_level / 100.0
        new_size = pixmap_to_scale.size() * scale_factor

        # Escalar imagen
        scaled_pixmap = pixmap_to_scale.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Overlays: marcas de agua (desactivado en modo recorte, manual o auto) o recorte
        if (self.watermark_positions and self.watermark_files
                and not self.manual_mode_enabled and not self.crop_mode_enabled
                and not self.auto_mode_enabled):
            scaled_pixmap = self._draw_watermark_overlays(scaled_pixmap, scale_factor)

        if self.crop_mode_enabled:
            scaled_pixmap = self._draw_crop_overlay(scaled_pixmap, scale_factor)

        # Highlight de la marca seleccionada en modo auto
        if (self.auto_mode_enabled
                and 0 <= self.selected_mark_index < len(self.detected_marks)):
            mark = self.detected_marks[self.selected_mark_index]
            if mark['watermark_array'] is not None:
                h_wm, w_wm = mark['watermark_array'].shape[:2]
                sx = int(mark['x'] * scale_factor)
                sy = int(mark['y'] * scale_factor)
                sw = int(w_wm * scale_factor)
                sh = int(h_wm * scale_factor)
                painter = QPainter(scaled_pixmap)
                pen = QPen(QColor(255, 235, 59, 230))  # amarillo
                pen.setWidth(4)
                painter.setPen(pen)
                painter.setBrush(QColor(255, 235, 59, 40))
                painter.drawRect(sx, sy, sw, sh)
                painter.end()

        self.image_label.setPixmap(scaled_pixmap)
        # Ajustar el tamaño del label para que funcione el scroll
        self.image_label.resize(scaled_pixmap.size())

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

        self._apply_zoom()

    def _on_crop_pixels_changed(self, value):
        """Actualiza el overlay y persiste el valor en settings."""
        UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).set('last_crop_pixels', int(value))
        if self.crop_mode_enabled:
            self._apply_zoom()

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

        # Texto indicativo
        painter.setPen(QPen(QColor(255, 255, 255, 220)))
        painter.drawText(rect.adjusted(6, 4, 0, 0), f"{pixels}px")

        painter.end()
        return result_pixmap

    def _apply_crop(self):
        """Recorta working_image y guarda el resultado."""
        if not self.image_files or self.working_image is None:
            return
        try:
            pixels = self.crop_pixels_input.value()
            if pixels <= 0:
                self._log("⚠️ Ingresá la cantidad de píxeles a recortar")
                return

            h = self.working_image.shape[0]
            if pixels >= h:
                self._log("❌ El recorte supera la altura de la imagen")
                return

            if self.crop_invert_checkbox.isChecked():
                self.working_image = self.working_image[:h - pixels]
                direccion = "abajo"
            else:
                self.working_image = self.working_image[pixels:]
                direccion = "arriba"

            current_file = self.image_files[self.current_index]
            if not self.output_folder:
                self._create_output_folder()
            guardar(current_file, self.working_image, self.output_folder)
            self.processed_images.add(self.current_index)

            self._show_current_image()
            self._log(f"✂️ Recortados {pixels}px desde {direccion} → {current_file.name}")

        except Exception as e:
            self._log(f"❌ Error al recortar: {e}")

    def _draw_watermark_overlays(self, pixmap: QPixmap, scale_factor: float) -> QPixmap:
        """
        Dibuja cuadrados semi-transparentes sobre el pixmap indicando las posiciones de las marcas de agua.

        Args:
            pixmap: El pixmap escalado de la imagen
            scale_factor: Factor de escala actual (zoom_level / 100)

        Returns:
            QPixmap con los cuadrados dibujados
        """
        # Crear una copia del pixmap para dibujar encima
        result_pixmap = QPixmap(pixmap)
        painter = QPainter(result_pixmap)

        # Limpiar el diccionario de rectángulos para la nueva imagen
        self.watermark_rectangles = {}

        # Obtener posiciones ya procesadas para esta imagen
        processed_positions_set = self.processed_positions.get(self.current_index, set())

        try:
            # Obtener el índice de la marca actual en el combo
            current_watermark_index = self.watermark_combo.currentIndex()

            # Si no hay marca seleccionada o no hay archivos, no dibujar nada
            if current_watermark_index < 0 or not self.watermark_files:
                painter.end()
                return result_pixmap

            # Cargar la marca de agua actual para obtener sus dimensiones
            watermark_file = self.watermark_files[current_watermark_index]
            watermark_cv = load_images_cv2(watermark_file)

            if watermark_cv is None:
                painter.end()
                return result_pixmap

            wm_height, wm_width = watermark_cv.shape[:2]

            # Obtener dimensiones de la imagen original
            img_width = self.current_pixmap.width()
            img_height = self.current_pixmap.height()

            # Dibujar un cuadrado para cada posición guardada
            for pos_name, pos_data in self.watermark_positions.items():
                # Obtener parámetros de posición
                offset_x = pos_data.get('offset_x', 0)
                offset_y = pos_data.get('offset_y', 0)
                side_x = pos_data.get('side_x', 'left')
                side_y = pos_data.get('side_y', 'top')

                # Calcular coordenadas X según side_x
                if side_x == 'left':
                    x = offset_x
                elif side_x == 'center':
                    x = (img_width - wm_width) // 2 + offset_x
                elif side_x == 'right':
                    x = img_width - wm_width - offset_x
                else:
                    x = offset_x

                # Calcular coordenadas Y según side_y
                if side_y == 'top':
                    y = offset_y
                elif side_y == 'center':
                    y = (img_height - wm_height) // 2 + offset_y
                elif side_y == 'bottom':
                    y = img_height - wm_height - offset_y
                else:
                    y = offset_y

                # Aplicar el factor de escala para el zoom
                scaled_x = int(x * scale_factor)
                scaled_y = int(y * scale_factor)
                scaled_width = int(wm_width * scale_factor)
                scaled_height = int(wm_height * scale_factor)

                # Guardar el rectángulo para detección de clicks (sin escala, coordenadas originales)
                self.watermark_rectangles[pos_name] = {
                    'rect': QRect(x, y, wm_width, wm_height),
                    'scaled_rect': QRect(scaled_x, scaled_y, scaled_width, scaled_height),
                    'offset_x': offset_x,
                    'offset_y': offset_y,
                    'side_x': side_x,
                    'side_y': side_y
                }

                # Determinar color según si esta posición específica ya fue procesada
                if pos_name in processed_positions_set:
                    # Verde si ya fue procesada
                    pen_color = QColor(0, 255, 0, 200)
                    brush_color = QColor(0, 255, 0, 50)
                else:
                    # Rojo si aún no se procesó
                    pen_color = QColor(255, 0, 0, 200)
                    brush_color = QColor(255, 0, 0, 50)

                pen = QPen(pen_color)
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(brush_color)

                # Dibujar el rectángulo
                painter.drawRect(scaled_x, scaled_y, scaled_width, scaled_height)

                # Opcional: Dibujar el nombre de la posición
                painter.setPen(QPen(QColor(255, 255, 255, 255)))  # Texto blanco
                painter.drawText(scaled_x + 5, scaled_y + 15, pos_name)

        except Exception as e:
            self._log(f"⚠️ Error dibujando overlays: {e}")
        finally:
            painter.end()

        return result_pixmap

    def _set_zoom(self, new_zoom: int):
        """Establece el nivel de zoom y actualiza la visualización"""
        # Limitar el zoom entre 10% y 200%
        self.zoom_level = max(10, min(200, new_zoom))
        self._apply_zoom()
        self._show_zoom_overlay()

    def _show_zoom_overlay(self):
        """Muestra el label flotante con el zoom actual"""
        self.zoom_overlay_label.setText(f"🔍 {self.zoom_level}%")

        # Posicionar el label en la esquina superior derecha del scroll area
        scroll_width = self.scroll_area.width()
        label_width = 120
        label_height = 40
        x = scroll_width - label_width - 20
        y = 20

        self.zoom_overlay_label.setGeometry(x, y, label_width, label_height)
        self.zoom_overlay_label.show()
        self.zoom_overlay_label.raise_()  # Traer al frente

        # Reiniciar el timer para ocultar después de 2 segundos
        self.zoom_hide_timer.start(2000)

    def _hide_zoom_overlay(self):
        """Oculta el label flotante de zoom"""
        self.zoom_overlay_label.hide()

    def _adjust_window_size(self, image_width: int, image_height: int):
        """
        Ajusta el tamaño de la ventana según la imagen actual.
        - Ancho: Se ajusta al ancho de la imagen
        - Alto: Fijo basado en el panel de controles
        """
        # Calcular el ancho total de la ventana
        # Panel de controles + spacing + imagen + bordes/padding
        SPACING = 15  # spacing del main_layout
        MARGINS = 20  # 10px a cada lado (contentsMargins)
        SCROLL_BORDER = 4  # Border del scroll area (2px * 2)
        EXTRA_PADDING = 20  # Padding extra para barras de scroll y espacios

        new_window_width = (
            self.controls_panel_width +  # Panel de controles fijo
            SPACING +                     # Espacio entre paneles
            image_width +                 # Ancho de la imagen
            SCROLL_BORDER +               # Borde del scroll area
            MARGINS +                     # Márgenes laterales
            EXTRA_PADDING                 # Padding extra
        )

        # El alto se mantiene fijo (basado en el tamaño del panel de controles)
        # No se usa image_height porque solo queremos ajustar el ancho
        current_height = self.height()

        # Redimensionar solo el ancho, manteniendo el alto fijo
        self.resize(new_window_width, current_height)

    def _update_counter(self):
        """Actualiza el contador de imágenes"""
        if self.image_files:
            self.counter_label.setText(
                f"{self.current_index + 1} / {len(self.image_files)}"
            )
        else:
            self.counter_label.setText("0 / 0")

    def _clear_image_memory(self):
        """Limpia la imagen de memoria cuando se navega a otra imagen"""
        self.working_image = None  # Limpiar imagen de trabajo
        self.base_image_for_preview = None
        self.current_event_position = None
        self.current_event_watermark_index = None
        self.current_event_watermark = None
        self.preview_image = None
        self.is_preview_active = False

    def _next_image(self):
        """Avanza a la siguiente imagen, guardando la actual si no fue procesada"""
        # Limpiar memoria de eventos de la imagen actual
        self._clear_image_memory()

        # Guardar la imagen actual si no ha sido procesada (sin marcas removidas)
        if self.current_index not in self.processed_images:
            self._save_current_image_as_is()

        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._show_current_image()
        else:
            # Si ya estamos en la última imagen, finalizar automáticamente
            self._finish_review()

    def _previous_image(self):
        """Retrocede a la imagen anterior"""
        # Limpiar memoria de eventos de la imagen actual
        self._clear_image_memory()

        if self.current_index > 0:
            self.current_index -= 1
            self._show_current_image()

    def _save_current_image_as_is(self):
        """Guarda la imagen actual sin modificaciones (cuando no se removió ninguna marca)"""
        if not self.output_folder or not self.image_files:
            return

        try:
            current_file = self.image_files[self.current_index]

            # Cargar imagen original con OpenCV
            image = load_images_cv2(current_file)
            if image is None:
                self._log(f"⚠️ Error cargando imagen: {current_file.name}")
                return

            # Guardar la imagen sin modificaciones
            guardar(current_file, image, self.output_folder)

            # Marcar como procesada
            self.processed_images.add(self.current_index)

            self._log(f"💾 Imagen guardada sin cambios: {current_file.name}")

        except Exception as e:
            self._log(f"❌ Error guardando imagen: {e}")

    def _process_watermark_at_position(self, pos_name: str, rect_data: dict, is_cumulative: bool = False):
        """
        Procesa la marca de agua en la posición especificada.

        Args:
            pos_name: Nombre de la posición (ej: "pos_1")
            rect_data: Diccionario con información del rectángulo y posición
            is_cumulative: Si es True (click derecho), aplica acumulativamente.
                          Si es False (click izquierdo), reemplaza cualquier procesamiento anterior.
        """
        if not self.output_folder or not self.image_files:
            return

        try:
            # Obtener el archivo de imagen actual
            current_file = self.image_files[self.current_index]

            # Obtener el índice de la marca actual
            current_watermark_index = self.watermark_combo.currentIndex()
            if current_watermark_index < 0 or not self.watermark_files:
                return

            # Cargar la imagen con OpenCV (soporte Unicode)
            output_path = self.output_folder / current_file.name

            if is_cumulative and output_path.exists():
                # Click derecho: cargar imagen ya procesada para aplicar más marcas
                image = load_images_cv2(output_path)
            else:
                # Click izquierdo O primera vez: usar imagen original
                image = load_images_cv2(current_file)
                # Si es click izquierdo, limpiar posiciones procesadas anteriormente
                if not is_cumulative and self.current_index in self.processed_positions:
                    self.processed_positions[self.current_index].clear()

            if image is None:
                self._log(f"❌ Error cargando imagen: {current_file.name}")
                return

            # Cargar la marca de agua
            watermark_file = self.watermark_files[current_watermark_index]
            watermark = load_images_cv2(watermark_file)
            if watermark is None:
                self._log(f"❌ Error cargando marca de agua: {watermark_file.name}")
                return

            # Calcular coordenadas usando align_watermark
            x, y = align_watermark(
                image,
                watermark,
                offset_x=rect_data['offset_x'],
                offset_y=rect_data['offset_y'],
                side_x=rect_data['side_x'],
                side_y=rect_data['side_y']
            )

            # Aplicar remove_watermark
            result_image = remove_watermark(image, watermark, x, y, alpha_adjust=self.alpha_adjust.value())

            # Guardar la imagen procesada en la carpeta de salida (soporte Unicode)
            guardar(current_file, result_image, self.output_folder)

            # Marcar esta imagen como procesada
            self.processed_images.add(self.current_index)

            # Marcar esta posición específica como procesada para esta imagen
            if self.current_index not in self.processed_positions:
                self.processed_positions[self.current_index] = set()
            self.processed_positions[self.current_index].add(pos_name)

            # Actualizar la visualización para mostrar el cuadrado verde
            self._show_current_image()

            self._log(f"✅ Marca de agua removida: {pos_name} en {current_file.name}")

            # Solo avanzar automáticamente si es click izquierdo (no acumulativo)
            if not is_cumulative:
                self._next_image()

        except Exception as e:
            self._log(f"❌ Error procesando marca de agua: {e}")

    def eventFilter(self, watched, event):
        """Filtro de eventos para capturar mouse en image_label"""
        if watched == self.image_label and self.manual_mode_enabled:
            if event.type() == QEvent.Type.MouseMove:
                # Actualizar overlay siguiendo el cursor
                self._update_manual_overlay(event.pos())
                return False  # Propagar el evento

            elif event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    # SIEMPRE añade marca (primera o adicional)
                    # Usuario debe usar el botón "Aceptar" para confirmar
                    self._remove_watermark_preview()
                    return True  # Consumir evento

                elif event.button() == Qt.MouseButton.RightButton:
                    if self.is_preview_active:
                        # Revertir TODAS las marcas acumuladas
                        self._revert_preview()
                    return True  # Consumir evento

        return super().eventFilter(watched, event)

    def _toggle_manual_mode(self, state):
        """Activa o desactiva el modo de selección manual"""
        self.manual_mode_enabled = (state == Qt.CheckState.Checked.value)

        if self.manual_mode_enabled:
            # Activar modo manual
            self.image_label.setMouseTracking(True)
            self.manual_overlay_label.show()
            self.alpha_adjust.show()
            self.label_alpha_adj.show()
            self.label_offset_adj.show()
            self.offset_adj_container.show()
            self.quick_preview_checkbox.show()
            self.reset_btn.show()
            self._log("🔍 Modo selección manual activado")
        else:
            # Desactivar modo manual
            self.image_label.setMouseTracking(False)
            self.manual_overlay_label.hide()
            self.alpha_adjust.hide()
            self.label_alpha_adj.hide()
            self.label_offset_adj.hide()
            self.offset_adj_container.hide()
            self.quick_preview_checkbox.hide()
            self.reset_btn.hide()
            self.accept_btn.hide()
            self.revert_btn.hide()
            # Limpiar estado
            self.mouse_position = None
            self.preview_image = None
            self.is_preview_active = False
            self._log("✅ Modo selección manual desactivado")
            # Refrescar imagen
            self._apply_zoom()

    def _update_manual_overlay(self, pos):
        """Actualiza la posición del overlay manual siguiendo el cursor"""
        try:
            # Obtener marca actual
            current_watermark_index = self.watermark_combo.currentIndex()
            if current_watermark_index < 0 or not self.watermark_files:
                return

            # Cargar marca para obtener dimensiones
            watermark_file = self.watermark_files[current_watermark_index]
            watermark_cv = load_images_cv2(watermark_file)
            if watermark_cv is None:
                return

            wm_height, wm_width = watermark_cv.shape[:2]

            # Aplicar escala de zoom
            scale_factor = self.zoom_level / 100.0
            scaled_width = int(wm_width * scale_factor)
            scaled_height = int(wm_height * scale_factor)

            # Convertir posición a coordenadas del scroll area
            scroll_pos = self.scroll_area.mapFromGlobal(self.image_label.mapToGlobal(pos))

            # Centrar overlay en cursor
            overlay_x = scroll_pos.x() - scaled_width // 2
            overlay_y = scroll_pos.y() - scaled_height // 2

            # Posicionar overlay
            self.manual_overlay_label.setGeometry(overlay_x, overlay_y, scaled_width, scaled_height)
            self.manual_overlay_label.raise_()

            # Guardar coordenadas originales de la imagen (sin escala de zoom)
            # pos es relativo al image_label escalado, dividir por scale_factor para obtener coordenadas reales
            image_x = int(pos.x() / scale_factor)
            image_y = int(pos.y() / scale_factor)
            self.mouse_position = QPoint(image_x, image_y)

        except Exception as e:
            self._log(f"⚠️ Error actualizando overlay: {e}")

    def _on_alpha_changed(self, value):
        """Recalcula el preview cuando cambia el alpha y guarda el valor para la marca actual"""
        # Guardar el alpha para la marca actual
        current_index = self.watermark_combo.currentIndex()
        if current_index >= 0:
            self.watermark_alpha_values[current_index] = value

        # Solo recalcular si hay evento activo
        if not self.is_preview_active:
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
            self._apply_zoom()

        except Exception as e:
            self._log(f"❌ Error recalculando preview: {e}")

    def _on_offset_adj_changed(self):
        """Recalcula el preview cuando cambia el ajuste de posición."""
        if not self.is_preview_active:
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
            self._apply_zoom()
        except Exception as e:
            self._log(f"❌ Error recalculando preview (offset): {e}")

    def _compute_live_preview(self, x, y, alpha):
        """Preview en vivo: vectorizado si el toggle está activo, sino remove_watermark sin filtro."""
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
        """Crea un preview removiendo la marca de agua en la posición del cursor. Sistema de eventos atómicos."""
        # Si ya hay un evento activo, IGNORAR (un evento = un solo click)
        if self.is_preview_active:
            self._log("⚠️ Ya hay un evento activo. Acepta o revierte primero.")
            return

        if not self.mouse_position or not self.image_files:
            self._log("⚠️ Posicione el cursor sobre la marca de agua primero")
            return

        try:
            # Obtener marca actual
            current_watermark_index = self.watermark_combo.currentIndex()
            if current_watermark_index < 0 or not self.watermark_files:
                self._log("⚠️ Seleccione una marca de agua")
                return

            # Usar working_image como base (ya está en memoria)
            if self.working_image is None:
                self._log("❌ No hay imagen en memoria")
                return

            # Guardar base para este sub-evento
            self.base_image_for_preview = self.working_image

            # Guardar índice de marca actual
            self.current_event_watermark_index = current_watermark_index

            # Cargar marca de agua y cachear para sub-eventos (alpha/offset live)
            watermark_file = self.watermark_files[current_watermark_index]
            watermark = load_images_cv2(watermark_file)
            if watermark is None:
                self._log(f"❌ Error cargando marca de agua: {watermark_file.name}")
                return
            self.current_event_watermark = watermark

            # Obtener coordenadas del mouse
            center_x = self.mouse_position.x()
            center_y = self.mouse_position.y()
            self._log(f"🔍 Buscando marca cerca de ({center_x}, {center_y})...")

            # Encontrar mejor posición
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

            # Resetear ajuste de posición para cada nueva detección
            self.offset_x_adj.blockSignals(True)
            self.offset_y_adj.blockSignals(True)
            self.offset_x_adj.setValue(0)
            self.offset_y_adj.setValue(0)
            self.offset_x_adj.blockSignals(False)
            self.offset_y_adj.blockSignals(False)

            # Preview en vivo (vectorizado si el toggle está activo)
            self.preview_image = self._compute_live_preview(
                best_x + self.offset_x_adj.value(),
                best_y + self.offset_y_adj.value(),
                alpha=self.alpha_adjust.value(),
            )

            # Activar evento
            self.is_preview_active = True

            # Bloquear UI
            self.next_btn.setEnabled(False)
            self.prev_btn.setEnabled(False)
            self.watermark_combo.setEnabled(False)

            # Mostrar botones
            self.reset_btn.hide()
            self.accept_btn.show()
            self.revert_btn.show()

            # Actualizar display
            self._apply_zoom()

            self._log(f"✅ Evento iniciado en ({best_x}, {best_y}) - Ajusta alpha si necesitas")

        except Exception as e:
            self._log(f"❌ Error en preview: {e}")
            import traceback
            self._log(traceback.format_exc())

    def _accept_preview(self):
        """Acepta el preview y guarda los cambios. Sistema de eventos atómicos."""
        if not self.is_preview_active or self.preview_image is None:
            return

        try:
            current_file = self.image_files[self.current_index]
            if not self.output_folder:
                self._create_output_folder()

            # Pasada final con filtro JPEG (los previews en vivo lo saltean por velocidad)
            best_x, best_y = self.current_event_position
            self.working_image = remove_watermark(
                self.base_image_for_preview,
                self.current_event_watermark,
                best_x + self.offset_x_adj.value(),
                best_y + self.offset_y_adj.value(),
                alpha_adjust=self.alpha_adjust.value(),
                apply_jpeg_filter=True,
            )

            # Guardar a disco
            guardar(current_file, self.working_image, self.output_folder)

            # Marcar como procesada
            self.processed_images.add(self.current_index)

            # Recopilar dato de entrenamiento YOLO (no debe interrumpir la remoción si falla)
            try:
                from WatermarkRemove.training_collector import save_training_sample
                wm_file = self.watermark_files[self.current_event_watermark_index]
                training_json = Path(os.path.dirname(current_dir)) / 'training_data.json'
                save_training_sample(
                    image_path=current_file,
                    watermark_path=wm_file,
                    watermark_folder=self.watermark_folder.name,
                    x=best_x + self.offset_x_adj.value(),
                    y=best_y + self.offset_y_adj.value(),
                    watermark_array=self.current_event_watermark,
                    image_array=self.base_image_for_preview,
                    output_json=training_json,
                )
            except Exception as collect_err:
                self._log(f"⚠️ No se pudo guardar dato de entrenamiento: {collect_err}")

            # Limpiar state del sub-evento
            self.base_image_for_preview = None
            self.current_event_position = None
            self.current_event_watermark_index = None
            self.current_event_watermark = None
            self.preview_image = None
            self.is_preview_active = False

            # Restaurar controles UI
            self.next_btn.setEnabled(True)
            self.prev_btn.setEnabled(True)
            self.watermark_combo.setEnabled(True)  # Desbloquear combo

            # Restaurar botones
            self.accept_btn.hide()
            self.revert_btn.hide()
            self.reset_btn.show()

            # Refrescar display: ahora se muestra working_image (con filtro JPEG aplicado)
            self._apply_zoom()

            # Actualizar conteo de datos de entrenamiento
            self._update_counts_label()

            # Log
            self._log(f"✅ Evento guardado en {current_file.name}")

            # NO avanzar automáticamente - permitir al usuario seguir trabajando en la misma imagen

            # Devolver foco al widget principal para que Space active keyPressEvent en vez del botón
            self.setFocus()

        except Exception as e:
            self._log(f"❌ Error guardando: {e}")

    def _revert_preview(self):
        """Revierte el preview y vuelve al estado anterior. Sistema de eventos atómicos."""
        if not self.is_preview_active:
            return

        # Limpiar state del sub-evento (NO tocar working_image - mantener eventos previos)
        self.base_image_for_preview = None
        self.current_event_position = None
        self.current_event_watermark_index = None
        self.current_event_watermark = None
        self.preview_image = None
        self.is_preview_active = False

        # Restaurar controles UI
        self.next_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self.watermark_combo.setEnabled(True)  # Desbloquear combo

        # Restaurar botones
        self.accept_btn.hide()
        self.revert_btn.hide()
        self.reset_btn.show()

        # Mostrar working_image (con sub-eventos previos aplicados)
        self._apply_zoom()

        # Log
        self._log(f"↩️ Evento descartado")

    def _reset_current_image(self):
        """
        Deshace todas las remociones de la imagen actual:
        - Cancela preview activo si lo hay
        - Borra el archivo procesado en output_folder
        - Quita el índice de processed_images / processed_positions
        - Elimina entries del training_data.json para esta imagen
        - Recarga working_image desde el original y refresca display
        """
        if not self.image_files:
            return

        current_file = self.image_files[self.current_index]

        reply = QMessageBox.question(
            self,
            "Resetear imagen",
            f"¿Resetear '{current_file.name}'?\n\n"
            "Se borrará el archivo procesado y los datos de entrenamiento asociados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Cancelar preview activo (si lo hay)
        if self.is_preview_active:
            self._revert_preview()

        # Borrar el archivo procesado
        if self.output_folder:
            output_file = self.output_folder / current_file.name
            if output_file.exists():
                try:
                    output_file.unlink()
                except Exception as e:
                    self._log(f"⚠️ No se pudo borrar {output_file.name}: {e}")

        # Quitar marcadores de procesamiento
        self.processed_images.discard(self.current_index)
        self.processed_positions.pop(self.current_index, None)

        # Limpiar entradas de training_data.json para esta imagen
        from WatermarkRemove.training_collector import remove_training_sample
        remove_training_sample(current_dir, current_file, self._log)
        
        # Recargar imagen original
        self.working_image = load_images_cv2(current_file)
        self._show_current_image()
        self._update_counts_label()

        self._log(f"↺ Imagen reseteada: {current_file.name}")

    # ===== Modo detección automática YOLO =====

    def _toggle_auto_mode(self, state):
        """Activa/desactiva modo auto: oculta selección manual, muestra panel auto."""
        self.auto_mode_enabled = (state == Qt.CheckState.Checked.value)
        if self.auto_mode_enabled:
            self._toggle_manual_mode(False)
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
            self._apply_zoom()

    def _run_auto_detection(self):
        # TODO: Ventana emergente de "cargando modelo"
        """Corre YOLO sobre la imagen actual y arma la lista de detecciones."""
        if self.working_image is None:
            return
        try:
            detections = detect_watermarks(self.working_image)
        except FileNotFoundError as e:
            self._log(f"❌ {e}")
            QMessageBox.warning(self, "Modelo no encontrado", str(e))
            return
        except Exception as e:
            self._log(f"❌ Error en detección: {e}")
            return

        _, w = self.working_image.shape[:2]
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

            # Refinar posición con template matching centrado en el bbox de YOLO
            final_x, final_y = int(x1), int(y1)
            if wm_array is not None:
                try:
                    cx = int((x1 + x2) / 2)
                    cy = int((y1 + y2) / 2)
                    final_x, final_y = find_wm(
                        self.working_image,
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
            self._apply_zoom()
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
        """Actualiza la posición de la marca seleccionada y refresca preview."""
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
        if self.working_image is None:
            self.auto_preview_image = None
            self._apply_zoom()
            return

        if self.auto_quick_preview_checkbox.isChecked() and self.detected_marks:
            result = self.working_image.copy()
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
            self.auto_preview_image = self.working_image.copy()

        self._apply_zoom()

    def _accept_auto_detections(self):
        """Aplica remove_watermark a todas las marcas y guarda. También recopila datos."""
        if not self.detected_marks:
            self._log("⚠️ Sin detecciones para aplicar")
            return
        if self.working_image is None:
            return
        if not self.output_folder:
            self._create_output_folder()

        current_file = self.image_files[self.current_index]
        base = self.working_image  # imagen previa al accept (para training data)
        result = base.copy()
        applied = 0

        for mark in self.detected_marks:
            if mark['watermark_array'] is None:
                continue  # sin PNG, se omite
            result = remove_watermark(
                result,
                mark['watermark_array'],
                mark['x'],
                mark['y'],
                alpha_adjust=1.0,
                apply_jpeg_filter=True,
            )

            # Recopilar dato (el filtro de clases entrenables lo aplica save_training_sample)
            try:
                from WatermarkRemove.training_collector import save_training_sample
                training_json = Path(os.path.dirname(current_dir)) / 'training_data.json'
                save_training_sample(
                    image_path=current_file,
                    watermark_path=mark['watermark_path'],
                    watermark_folder=self.watermark_folder.name if self.watermark_folder else '',
                    x=mark['x'],
                    y=mark['y'],
                    watermark_array=mark['watermark_array'],
                    image_array=base,
                    output_json=training_json,
                )
            except Exception as collect_err:
                self._log(f"⚠️ No se pudo guardar dato de entrenamiento: {collect_err}")

            applied += 1

        if applied == 0:
            self._log("⚠️ Sin marcas removibles (todas sin PNG)")
            return

        self.working_image = result
        guardar(current_file, result, self.output_folder)
        self.processed_images.add(self.current_index)
        self._update_counts_label()
        self._log(f"✅ {applied} marca(s) removida(s) en {current_file.name}")

        self.detected_marks = []
        self.selected_mark_index = -1
        self.auto_preview_image = None
        self.detections_list.clear()
        self._apply_zoom()

    def _finish_review(self):
        """Finaliza la revisión y permite continuar con el proceso"""
        reply = QMessageBox.question(
            self, "Finalizar revisión",
            "¿Seguro que quieres finalizar y procesar las imágenes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.user_approved = True
        self.review_completed.emit(True)
        self.accept()

    def _cancel_review(self):
        """Cancela la revisión y el proceso"""
        reply = QMessageBox.question(
            self, "Cancelar revisión",
            "¿Seguro que quieres cancelar? Se perderán los cambios no guardados.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.user_approved = False
        self.review_completed.emit(False)
        self.reject()

    def mousePressEvent(self, event: QMouseEvent):
        """
        Maneja clicks en la imagen para procesar marcas de agua.

        Click Izquierdo: Reemplaza cualquier procesamiento anterior (solo un cuadro verde) y avanza automáticamente
        Click Derecho: Procesamiento acumulativo (múltiples cuadros verdes) sin avanzar
        """
        # Solo procesar clicks izquierdos o derechos
        if event.button() not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            super().mousePressEvent(event)
            return

        # Si no hay watermark folder, comportamiento normal
        if not self.watermark_folder or not self.watermark_rectangles:
            super().mousePressEvent(event)
            return

        # Obtener posición del click relativo al scroll area
        click_pos = event.pos()

        # Convertir a coordenadas de la imagen (considerando el scroll)
        scroll_pos = self.scroll_area.mapFrom(self, click_pos)
        viewport_pos = self.scroll_area.viewport().mapFrom(self.scroll_area, scroll_pos)

        # Ajustar por el scroll offset
        image_x = viewport_pos.x() + self.scroll_area.horizontalScrollBar().value()
        image_y = viewport_pos.y() + self.scroll_area.verticalScrollBar().value()

        # Verificar si el click está dentro de algún rectángulo
        for pos_name, rect_data in self.watermark_rectangles.items():
            scaled_rect = rect_data['scaled_rect']
            if scaled_rect.contains(image_x, image_y):
                # Determinar si es acumulativo según el botón
                is_cumulative = (event.button() == Qt.MouseButton.RightButton)

                # Click detectado en un cuadrado
                self._process_watermark_at_position(pos_name, rect_data, is_cumulative)
                event.accept()
                return

        super().mousePressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        """Maneja el zoom con Ctrl + rueda del mouse"""
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl está presionado - hacer zoom
            delta = event.angleDelta().y()
            zoom_change = 10 if delta > 0 else -10
            new_zoom = self.zoom_level + zoom_change
            self._set_zoom(new_zoom)
            event.accept()
        else:
            # Sin Ctrl - comportamiento normal de scroll
            super().wheelEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Maneja los eventos de teclado"""
        key = event.key()

        # Teclas de zoom
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            # Ctrl + Plus: Zoom in
            self._set_zoom(self.zoom_level + 10)
            event.accept()
            return
        elif key == Qt.Key.Key_Minus:
            # Ctrl + Minus: Zoom out
            self._set_zoom(self.zoom_level - 10)
            event.accept()
            return
        elif key == Qt.Key.Key_0:
            # Ctrl + 0: Reset zoom
            self._set_zoom(100)
            event.accept()
            return

        # Navegación normal
        check_opc_avanzadas = self.opciones_avanzadas.isChecked()
        if key == Qt.Key.Key_Space:
            if check_opc_avanzadas and self.is_preview_active:
                self._accept_preview()
            else:
                self._next_image()
        elif key == Qt.Key.Key_Backspace:
            if check_opc_avanzadas and self.is_preview_active:
                self._revert_preview()
            else:
                self._previous_image()
        # elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
        #     self._finish_review()
        # elif key == Qt.Key.Key_Escape:
        #     self._cancel_review()
        else:
            super().keyPressEvent(event)

    def get_approved(self) -> bool:
        """Retorna si el usuario aprobó continuar con el proceso"""
        return self.user_approved

    def get_output_folder(self) -> Path:
        """Retorna la carpeta de salida donde se guardaron las imágenes procesadas"""
        return self.output_folder

    def has_processed_images(self) -> bool:
        """Retorna True si se procesó al menos una imagen"""
        return len(self.processed_images) > 0


# Para pruebas independientes
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Carpeta de prueba
    test_folder = r"C:\Users\Felix\Downloads\Image Picka\32 urek"
    viewer = SlideshowViewer(test_folder)

    # Conectar señal
    viewer.review_completed.connect(
        lambda approved: print(f"Revisión {'aprobada' if approved else 'cancelada'}")
    )

    result = viewer.exec()
    print(f"Resultado: {'Aceptado' if result else 'Cancelado'}")
    print(f"Aprobado: {viewer.get_approved()}")

    sys.exit(app.exec())
