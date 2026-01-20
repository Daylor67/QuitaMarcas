"""
Visor de imágenes tipo slideshow - Navega con Space y Backspace
"""
import os
import sys
from pathlib import Path
from typing import Tuple, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget, QGridLayout,
    QScrollArea, QComboBox, QGroupBox, QCheckBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QRect, QEvent, QPoint
from PySide6.QtGui import QPixmap, QKeyEvent, QWheelEvent, QPainter, QPen, QColor, QMouseEvent, QImage

# Agregar el directorio raíz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils import UtilJson
import numpy as np
from natsort import natsorted
from WatermarkRemove import align_watermark, remove_watermark
from WatermarkRemove.wm_remove import load_images_cv2, guardar, find_wm

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

    def __init__(self, folder_path: str, parent=None, watermark_folder: str = None, watermark_name: str = None, watermark_tab=None):
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

        # Información de marca de agua
        self.watermark_folder = Path(watermark_folder) if watermark_folder else None
        self.watermark_name = watermark_name
        self.watermark_positions = {}  # Posiciones cargadas desde JSON
        self.watermark_files = []  # Archivos PNG de marcas de agua

        # Procesamiento de marcas de agua
        self.output_folder = None  # Carpeta donde se guardarán las imágenes procesadas
        self.processed_images = set()  # Set de índices de imágenes ya procesadas
        self.processed_positions = {}  # Diccionario: {image_index: set(pos_names)} - posiciones procesadas por imagen
        self.watermark_rectangles = {}  # Diccionario: pos_name -> QRect (para detección de clicks)

        # Modo selección manual
        self.manual_mode_enabled = False  # Si está activado el modo manual
        self.manual_overlay_label = None  # Label flotante para el overlay
        self.mouse_position = None  # Posición actual del cursor (QPoint)
        self.preview_image = None  # Imagen con marca removida (temporal, numpy array)
        self.is_preview_active = False  # Si hay un preview activo esperando confirmación

        # Sistema de eventos atómicos para remoción de marcas
        self.current_event_position: Optional[Tuple[int, int]] = None  # Coordenadas del click del evento actual (best_x, best_y)
        self.current_event_watermark_index: Optional[int] = None  # Índice de la marca de agua usada en el evento actual
        self.base_image_for_preview: Optional[np.ndarray] = None  # Imagen base para el sub-evento actual

        # Imagen de trabajo en memoria (fuente de verdad para edición)
        self.working_image: Optional[np.ndarray] = None

        # Alpha por marca de agua (índice -> valor alpha)
        self.watermark_alpha_values: dict = {}  # {0: 1.0, 1: 1.5, ...}

        self._setup_ui()
        self._load_image_list()

        # Crear carpeta de salida si se proporcionó watermark
        if self.watermark_folder and self.folder_path:
            self._create_output_folder()

        # Cargar marcas de agua y posiciones si se proporcionó la carpeta
        if self.watermark_folder:
            self._load_watermark_files()
            self._load_watermark_positions()

        if self.image_files:
            self._show_current_image()

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
        """Crea el panel de controles (izquierda)"""
        panel = QWidget()
        panel.setFixedWidth(self.controls_panel_width)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Información de carpeta  ////////////////////////////////////////
        info_group = QGroupBox("ℹ️ Info")
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(5)

        info_layout.addWidget(QLabel("Carpeta:"))
        self.folder_label = QLabel()
        self.folder_label.setStyleSheet("color: #999999; font-size: 10px; padding-left: 10px;")
        self.folder_label.setWordWrap(True)
        self.folder_label.setMaximumHeight(60)  # Limitar altura
        info_layout.addWidget(self.folder_label)

        if self.folder_path:
            self.folder_label.setText(str(self.folder_path))

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

        # Selección  ////////////////////////////////////////
        seleccion_group = QGroupBox("📁 Selección")
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
        self.watermark_combo = QComboBox()
        self.watermark_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.watermark_combo.currentIndexChanged.connect(self._on_watermark_changed)
        seleccion_layout.addWidget(self.watermark_combo)

        # Cargar las carpetas de marcas disponibles
        self._load_watermark_folders()

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
        self.alpha_adjust.setSingleStep(0.01)  # Incremento de 0.01 (centésimas)
        self.alpha_adjust.setDecimals(2)  # Mostrar 2 decimales
        self.alpha_adjust.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.alpha_adjust.valueChanged.connect(self._on_alpha_changed)  # Conectar para recalcular preview en tiempo real
        self.alpha_adjust.hide()
        seleccion_layout.addWidget(self.alpha_adjust)

        # Botones de modo manual (ocultos por defecto)
        self.remove_btn = QPushButton("Remover marca")
        self.remove_btn.clicked.connect(self._remove_watermark_preview)
        self.remove_btn.setStyleSheet("padding: 8px; font-size: 11px; background-color: #FF9800; color: white; font-weight: bold;")
        self.remove_btn.hide()
        seleccion_layout.addWidget(self.remove_btn)

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

        # Determinar qué carpeta seleccionar
        if self.watermark_folder:
            # Si se proporcionó una carpeta inicial, usarla
            folder_to_select = self.watermark_name
        else:
            # Usar la última carpeta guardada en settings
            folder_to_select = UtilJson('__settings__/settings.json').get('last_watermark_folder', None)

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
            self.watermark_name = folder_name  # Actualizar el nombre
            self._load_watermarks_into_combo()
            self._load_watermark_positions()

            # Guardar como última carpeta usada
            UtilJson('__settings__/settings.json').set('last_watermark_folder', folder_name)

            # Crear carpeta de salida si aún no existe
            if not self.output_folder and self.folder_path:
                self._create_output_folder()

            # Actualizar la visualización
            self._show_current_image()

    def _load_watermarks_into_combo(self):
        """Carga las marcas de agua PNG en el ComboBox desde la carpeta seleccionada"""
        self.watermark_combo.clear()
        self.watermark_files = []

        if not self.watermark_folder or not self.watermark_folder.exists():
            return

        # Cargar todos los archivos PNG de la carpeta
        for file in natsorted(self.watermark_folder.iterdir()):
            if file.is_file() and file.suffix.lower() == '.png':
                self.watermark_files.append(file)
                # Agregar al ComboBox: nombre del archivo como label, ruta como data
                self.watermark_combo.addItem(file.name, str(file))

    def _on_watermark_changed(self, index):
        """Callback cuando cambia la marca individual seleccionada"""
        if index >= 0:
            # Cargar el alpha guardado para esta marca (o 1.0 por defecto)
            saved_alpha = self.watermark_alpha_values.get(index, 1.0)
            self.alpha_adjust.blockSignals(True)  # Evitar trigger de _on_alpha_changed
            self.alpha_adjust.setValue(saved_alpha)
            self.alpha_adjust.blockSignals(False)

            # Actualizar la visualización con los nuevos cuadrados
            self._show_current_image()

    def _load_watermark_files(self):
        """Carga los archivos PNG de marcas de agua desde la carpeta"""
        if not self.watermark_folder or not self.watermark_folder.exists():
            return

        self.watermark_files = []
        for file in natsorted(self.watermark_folder.iterdir()):
            if file.is_file() and file.suffix.lower() == '.png':
                self.watermark_files.append(file)

    def _load_watermark_positions(self):
        """Carga las posiciones de marcas de agua desde wm_positions.json"""
        if not self.watermark_name:
            return

        try:
            wm_dir = os.path.dirname(current_dir)
            positions_path = Path(wm_dir) / 'wm_positions.json'

            if not positions_path.exists():
                self.watermark_positions = {}
                return

            # Cargar posiciones desde JSON
            positions_file = UtilJson(positions_path)
            data = positions_file.read()

            # Obtener las posiciones para la marca actual
            if self.watermark_name in data:
                self.watermark_positions = data[self.watermark_name]
            else:
                self.watermark_positions = {}

        except Exception as e:
            self._log(f"⚠️ Error cargando posiciones de marca de agua: {e}")
            self.watermark_positions = {}

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

    def _apply_zoom(self):
        """Aplica el nivel de zoom actual a la imagen y dibuja overlays de marcas"""
        # Prioridad: preview_image (sub-evento activo) > working_image (imagen editada) > current_pixmap
        if self.is_preview_active and self.preview_image is not None:
            # Mostrar preview del sub-evento
            height, width = self.preview_image.shape[:2]
            bytes_per_line = 3 * width
            q_image = QImage(self.preview_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            q_image = q_image.rgbSwapped()  # OpenCV usa BGR, Qt usa RGB
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

        # Si hay posiciones de marcas de agua y NO estamos en modo manual, dibujar overlays
        if self.watermark_positions and self.watermark_files and not self.manual_mode_enabled:
            scaled_pixmap = self._draw_watermark_overlays(scaled_pixmap, scale_factor)

        self.image_label.setPixmap(scaled_pixmap)
        # Ajustar el tamaño del label para que funcione el scroll
        self.image_label.resize(scaled_pixmap.size())

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
            self.remove_btn.show()
            self._log("🔍 Modo selección manual activado")
        else:
            # Desactivar modo manual
            self.image_label.setMouseTracking(False)
            self.manual_overlay_label.hide()
            self.alpha_adjust.hide()
            self.label_alpha_adj.hide()
            self.remove_btn.hide()
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

        if self.current_event_position is None or self.current_event_watermark_index is None:
            return

        try:
            # Recargar marca de agua
            watermark_file = self.watermark_files[self.current_event_watermark_index]
            watermark = load_images_cv2(watermark_file)

            # Recalcular preview desde la base con nuevo alpha
            best_x, best_y = self.current_event_position
            self.preview_image = remove_watermark(
                self.base_image_for_preview,  # Siempre desde la base
                watermark,
                best_x,
                best_y,
                alpha_adjust=value  # Nuevo valor de alpha
            )

            # Actualizar display
            self._apply_zoom()

            self._log(f"🔄 Alpha ajustado a {value:.2f}")

        except Exception as e:
            self._log(f"❌ Error recalculando preview: {e}")

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

            # Cargar marca de agua
            watermark_file = self.watermark_files[current_watermark_index]
            watermark = load_images_cv2(watermark_file)
            if watermark is None:
                self._log(f"❌ Error cargando marca de agua: {watermark_file.name}")
                return

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

            # Crear preview con alpha actual
            self.preview_image = remove_watermark(
                self.base_image_for_preview,
                watermark,
                best_x,
                best_y,
                alpha_adjust=self.alpha_adjust.value()
            )

            # Activar evento
            self.is_preview_active = True

            # Bloquear UI
            self.next_btn.setEnabled(False)
            self.prev_btn.setEnabled(False)
            self.watermark_combo.setEnabled(False)

            # Mostrar botones
            self.remove_btn.hide()
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
            # Guardar imagen procesada
            current_file = self.image_files[self.current_index]
            if not self.output_folder:
                self._create_output_folder()

            # CRÍTICO: Actualizar working_image con el preview aceptado
            self.working_image = self.preview_image.copy()

            # Guardar a disco
            guardar(current_file, self.working_image, self.output_folder)

            # Marcar como procesada
            self.processed_images.add(self.current_index)

            # Limpiar state del sub-evento
            self.base_image_for_preview = None
            self.current_event_position = None
            self.current_event_watermark_index = None
            self.preview_image = None
            self.is_preview_active = False

            # Restaurar controles UI
            self.next_btn.setEnabled(True)
            self.prev_btn.setEnabled(True)
            self.watermark_combo.setEnabled(True)  # Desbloquear combo

            # Restaurar botones
            self.accept_btn.hide()
            self.revert_btn.hide()
            self.remove_btn.show()

            # Log
            self._log(f"✅ Evento guardado en {current_file.name}")

            # NO avanzar automáticamente - permitir al usuario seguir trabajando en la misma imagen

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
        self.preview_image = None
        self.is_preview_active = False

        # Restaurar controles UI
        self.next_btn.setEnabled(True)
        self.prev_btn.setEnabled(True)
        self.watermark_combo.setEnabled(True)  # Desbloquear combo

        # Restaurar botones
        self.accept_btn.hide()
        self.revert_btn.hide()
        self.remove_btn.show()

        # Mostrar working_image (con sub-eventos previos aplicados)
        self._apply_zoom()

        # Log
        self._log(f"↩️ Evento descartado")

    def _finish_review(self):
        """Finaliza la revisión y permite continuar con el proceso"""
        self.user_approved = True
        self.review_completed.emit(True)
        self.accept()

    def _cancel_review(self):
        """Cancela la revisión y el proceso"""
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
            if check_opc_avanzadas:
                self._accept_preview()
            else:
                self._next_image()
        elif key == Qt.Key.Key_Backspace:
            if check_opc_avanzadas:
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
