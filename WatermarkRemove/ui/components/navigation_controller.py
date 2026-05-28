"""
NavigationController - Componente extraido de SlideshowViewer (Plan 02-01 Task 2).

Responsabilidades:
- Lista de imagenes y current_index
- working_image / base_image_for_preview / output_folder / processed_images / processed_positions
- Zoom (zoom_level 10-200) y render del pixmap (panel derecho del visor)
- Botones prev/next + contador + filename label + zoom overlay

Signals publicas (ver `<signals_publicas>` en clase):
- image_changed(int, object, object): (index, Path, np.ndarray working_image)
- output_folder_ready(object): Path
- request_redraw(): el composer/processor debe re-renderizar (placeholder Plan 02)
- window_resize_requested(int, int): el composer (QDialog) ejecuta resize(width, height)
- finish_requested(): la navegacion llego al final; el composer abre dialogo
"""
import os
import sys
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QGroupBox, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QPoint
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QWheelEvent

import numpy as np
from natsort import natsorted

# components/ esta dos niveles bajo el package root (PATTERNS line 648-656).
# os.path.dirname(__file__) -> WatermarkRemove/ui/components
# os.path.dirname(os.path.dirname(__file__)) -> WatermarkRemove/ui
# os.path.dirname(os.path.dirname(os.path.dirname(__file__))) -> WatermarkRemove/
current_dir = os.path.abspath(os.path.dirname(__file__))
wm_dir_root = os.path.dirname(os.path.dirname(__file__))  # WatermarkRemove/ui — usar dirname extra para WatermarkRemove/
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from WatermarkRemove.wm_remove import load_images_cv2, guardar
from WatermarkRemove.services import wm_persistence  # noqa: F401  (Plan 02 lo usara desde el processor)


class NavigationController(QWidget):
    """Controlador de navegacion: gestiona estado de lista de imagenes, working_image,
    output_folder, zoom y render del panel derecho.

    El composer (SlideshowViewer) lo instancia, lo coloca en su layout derecho,
    y conecta sus signals para reaccionar a image_changed, finish_requested, etc.
    """

    # === Senales publicas ===
    image_changed = Signal(int, object, object)   # (index, Path, np.ndarray working_image)
    output_folder_ready = Signal(object)           # Path
    request_redraw = Signal()                      # Plan 02: pintura de overlays via slot
    window_resize_requested = Signal(int, int)     # (width, height) — composer (QDialog) ejecuta resize
    finish_requested = Signal()                    # navegacion llego al final
    # === Plan 02-02 wiring: comunicacion con WatermarkProcessor ===
    # image_clicked: (QPoint pos_in_image_label_coords, "left"|"right") — emitida cuando user click sobre image_label
    image_clicked = Signal(object, str)
    # mouse_moved: (QPoint pos_in_image_coords sin escala) — emitida en mouse move cuando manual mode tracking activo
    mouse_moved = Signal(object)
    # output_folder_request: el processor pide a navigation que cree output_folder
    output_folder_request = Signal()

    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tga', '.psd', '.psb', '.jfif')

    def __init__(self, folder_path: str, parent=None, watermark_tab=None):
        super().__init__(parent)

        # Estado de carpeta
        self.folder_path = Path(folder_path) if folder_path else None

        # Estado de navegacion
        self.image_files: list = []
        self.current_index: int = 0

        # Estado de render
        self.current_pixmap: Optional[QPixmap] = None
        self.zoom_level: int = 100
        self.controls_panel_width = 280

        # Logging fallback
        self.watermark_tab = watermark_tab

        # Estado de procesamiento (compartido con composer via getters)
        self.output_folder: Optional[Path] = None
        self.processed_images: set = set()
        self.processed_positions: dict = {}

        # Imagen de trabajo en memoria (fuente de verdad para edicion)
        self.working_image: Optional[np.ndarray] = None
        # NOTA Plan 02: `base_image_for_preview` queda en SlideshowViewer (manual mode state)
        # durante Plan 01 — migra junto con WatermarkProcessor en Plan 02-02.
        self.base_image_for_preview: Optional[np.ndarray] = None  # placeholder; el processor lo poblara

        # Estado de preview (placeholder — el processor lo activa via slots en Plan 02)
        self._preview_image_from_processor: Optional[np.ndarray] = None

        # Plan 02-02 wiring: callback al `decorate_pixmap` del processor
        # Inicializado en None — el composer llama `set_processor_decorator(...)` tras instanciar
        # el processor. Permite que el render del navigation invoque al processor para pintar
        # overlays (cuadros rojo/verde + crop + highlight auto) sin coupling directo a la clase.
        self._processor_decorate = None

        self._setup_ui()
        self._load_image_list()

        # Instalar eventFilter sobre image_label para capturar clicks y mouse moves.
        # El filter emite signals image_clicked / mouse_moved que el processor conecta.
        self.image_label.installEventFilter(self)

        if self.image_files:
            self._show_current_image()

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
        """Construye el panel derecho: contador + filename + prev/next + scroll con image_label + overlays."""
        outer = QVBoxLayout(self)
        outer.setSpacing(6)
        outer.setContentsMargins(0, 0, 0, 0)

        # --- Info: contador y filename label ---
        info_group = QGroupBox("ℹ️ Info")
        self._nav_info_group = info_group   # Phase 4: para ocultarlo tras reparentar en create_nav_controls_widget
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(5)

        info_layout.addWidget(QLabel("Imagen:"))
        self.counter_label = QLabel("0 / 0")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.counter_label.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #2196F3; padding: 5px;"
        )
        info_layout.addWidget(self.counter_label)

        self.filename_label = QLabel("Sin archivo")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setStyleSheet(
            "font-size: 12px; color: #888; padding: 10px; "
            "background-color: #1e1e1e; border-radius: 5px;"
        )
        self.filename_label.setWordWrap(True)
        self.filename_label.setMaximumHeight(60)
        info_layout.addWidget(self.filename_label)
        outer.addWidget(info_group)

        # --- Botones de navegacion prev/next ---
        nav_buttons = QHBoxLayout()
        nav_buttons.setSpacing(5)

        self.prev_btn = QPushButton("Anterior")
        self.prev_btn.clicked.connect(self.request_previous)
        self.prev_btn.setStyleSheet(
            "padding: 10px; font-size: 12px; background-color: #555; color: white;"
        )
        self.prev_btn.setMaximumHeight(40)
        nav_buttons.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Siguiente")
        self.next_btn.clicked.connect(self.request_next)
        self.next_btn.setStyleSheet(
            "padding: 10px; font-size: 12px; background-color: #4CAF50; "
            "color: white; font-weight: bold;"
        )
        self.next_btn.setMaximumHeight(40)
        nav_buttons.addWidget(self.next_btn)
        outer.addLayout(nav_buttons)

        # --- Scroll area con image_label ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)  # Importante para que funcione el zoom
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("border: 2px solid #444; background-color: #2b2b2b;")

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2b2b2b;")
        scroll.setWidget(self.image_label)

        # Zoom overlay flotante
        self.zoom_overlay_label = QLabel(scroll)
        self.zoom_overlay_label.setStyleSheet(
            "background-color: rgba(0, 0, 0, 180); color: white; "
            "padding: 8px 16px; border-radius: 5px; font-size: 16px; font-weight: bold;"
        )
        self.zoom_overlay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_overlay_label.hide()

        self.zoom_hide_timer = QTimer(self)
        self.zoom_hide_timer.timeout.connect(self._hide_zoom_overlay)
        self.zoom_hide_timer.setSingleShot(True)

        # Manual overlay label (placeholder — el processor en Plan 02 lo activa via slot)
        self.manual_overlay_label = QLabel(scroll)
        self.manual_overlay_label.setStyleSheet(
            "background-color: rgba(33, 150, 243, 50); "
            "border: 3px solid rgba(33, 150, 243, 200);"
        )
        self.manual_overlay_label.hide()
        self.manual_overlay_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        outer.addWidget(scroll, 1)

        # Exponer scroll_area para que el composer (mousePressEvent inline) pueda mapear coords
        self.scroll_area = scroll

    # ===================================================================
    # Phase 4 (D-04): widget de controles de navegacion para el panel izquierdo
    # ===================================================================
    def create_nav_controls_widget(self) -> 'QGroupBox':
        """Retorna un QGroupBox 'Navegación' con los controles de navegación
        para el panel izquierdo del QSplitter (Phase 4, D-04).

        Reparenta self.counter_label, self.filename_label, self.prev_btn,
        self.next_btn al nuevo contenedor. Los slots y conexiones existentes
        siguen funcionando porque los objetos son los mismos.

        NOTA: Oculta self._nav_info_group (el QGroupBox 'ℹ️ Info' del layout
        de NavigationController) que queda vacío tras el reparentado, de modo
        que NavigationController muestre solo la scroll area (imagen).
        Solo debe llamarse una vez por instancia.
        """
        nav_widget = QGroupBox("Navegación")
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setSpacing(5)
        nav_layout.setContentsMargins(8, 6, 8, 6)

        # Reparentar widgets ya existentes (creados en _setup_ui)
        nav_layout.addWidget(self.counter_label)
        nav_layout.addWidget(self.filename_label)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(5)
        btn_row.addWidget(self.prev_btn)
        btn_row.addWidget(self.next_btn)
        nav_layout.addLayout(btn_row)

        # Ocultar el contenedor original (queda vacío tras reparentar sus widgets)
        if hasattr(self, '_nav_info_group'):
            self._nav_info_group.hide()

        return nav_widget

    # ===================================================================
    # Carga / output folder
    # ===================================================================
    def _create_output_folder(self):
        """Crea la carpeta de salida para las imagenes procesadas."""
        if not self.folder_path:
            return

        folder_name = self.folder_path.name + " [sin marca]"
        self.output_folder = self.folder_path.parent / folder_name
        self.output_folder.mkdir(exist_ok=True)
        self.output_folder_ready.emit(self.output_folder)

    def _load_image_list(self):
        """Carga la lista de archivos de imagen ordenada naturalmente."""
        if not self.folder_path or not self.folder_path.exists():
            return

        # Si es un archivo, usar su directorio padre
        if self.folder_path.is_file():
            self.folder_path = self.folder_path.parent

        for file in natsorted(self.folder_path.iterdir()):
            if file.is_file() and file.suffix.lower() in self.SUPPORTED_FORMATS:
                self.image_files.append(file)

        self._update_counter()

    # ===================================================================
    # Render principal
    # ===================================================================
    def _show_current_image(self):
        """Muestra la imagen actual con el zoom aplicado y emite image_changed."""
        if not self.image_files or self.current_index >= len(self.image_files):
            return

        current_file = self.image_files[self.current_index]

        # Cargar working_image SOLO si no existe (primera vez en esta imagen)
        # NOTA: el guard `is None` es load-bearing (RESEARCH Pitfall 3) — preserva
        # state durante sub-eventos de preview cuando el processor mutara working_image.
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
            self.current_pixmap = QPixmap(str(current_file))

        if not self.current_pixmap.isNull():
            self._apply_zoom()
            width = self.current_pixmap.width()
            height = self.current_pixmap.height()
            self._request_window_resize(width, height)
        else:
            self.image_label.setText("Error cargando imagen")

        # Filename + contador
        self.filename_label.setText(f"{current_file.name}")
        self._update_counter()

        # Estado de botones prev/next
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)

        # Notificar al composer/processor que cambio la imagen
        self.image_changed.emit(self.current_index, current_file, self.working_image)
        # Auto-detection se gatilla desde WatermarkProcessor via slot on_image_changed (Plan 02)

    def _apply_zoom(self):
        """Aplica el nivel de zoom actual a la imagen.

        TODO Plan 02: el processor decorara el pixmap via signal/slot
        (RESEARCH Open Question #2). Por ahora se prefiere preview_image si
        el processor lo envio via on_preview_changed; sino, working_image.

        # TODO Plan 02: el processor decorara el pixmap via signal/slot
        # — los cuadros rojo/verde de posiciones y el overlay de crop pintaran de
        # vuelta en Plan 02-02 cuando WatermarkProcessor reciba el pixmap escalado.
        """
        # Prioridad: preview del processor > working_image > current_pixmap original
        if self._preview_image_from_processor is not None:
            height, width = self._preview_image_from_processor.shape[:2]
            bytes_per_line = 3 * width
            q_image = QImage(
                self._preview_image_from_processor.data, width, height,
                bytes_per_line, QImage.Format.Format_RGB888
            )
            q_image = q_image.rgbSwapped()
            pixmap_to_scale = QPixmap.fromImage(q_image)
        elif self.working_image is not None:
            height, width = self.working_image.shape[:2]
            bytes_per_line = 3 * width
            q_image = QImage(self.working_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            q_image = q_image.rgbSwapped()
            pixmap_to_scale = QPixmap.fromImage(q_image)
        else:
            if self.current_pixmap is None or self.current_pixmap.isNull():
                return
            pixmap_to_scale = self.current_pixmap

        # Calcular nuevo tamano basado en zoom
        scale_factor = self.zoom_level / 100.0
        new_size = pixmap_to_scale.size() * scale_factor

        scaled_pixmap = pixmap_to_scale.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Plan 02-02 wiring: el processor decora el pixmap con overlays
        # (cuadros rojo/verde de posiciones, overlay de crop, highlight amarillo modo auto).
        # Esto restaura la regresion temporal del Plan 01.
        if self._processor_decorate is not None:
            scaled_pixmap = self._processor_decorate(scaled_pixmap, scale_factor)

        # Emit por si algun componente externo quiere reaccionar al re-render
        self.request_redraw.emit()

        self.image_label.setPixmap(scaled_pixmap)
        self.image_label.resize(scaled_pixmap.size())

    def _set_zoom(self, new_zoom: int):
        """Establece el nivel de zoom (clamp 10-200) y actualiza la visualizacion."""
        self.zoom_level = max(10, min(200, new_zoom))
        self._apply_zoom()
        self._show_zoom_overlay()

    def set_zoom_level(self, new_zoom: int):
        """Slot publico — alias semantico de `_set_zoom` para el composer."""
        self._set_zoom(new_zoom)

    def adjust_zoom(self, delta: int):
        """Slot publico: ajusta el zoom en `delta` unidades (positivo o negativo)."""
        self._set_zoom(self.zoom_level + delta)

    def _show_zoom_overlay(self):
        """Muestra el label flotante con el zoom actual."""
        self.zoom_overlay_label.setText(f"🔍 {self.zoom_level}%")

        scroll_width = self.scroll_area.width()
        label_width = 120
        label_height = 40
        x = scroll_width - label_width - 20
        y = 20

        self.zoom_overlay_label.setGeometry(x, y, label_width, label_height)
        self.zoom_overlay_label.show()
        self.zoom_overlay_label.raise_()

        self.zoom_hide_timer.start(2000)

    def _hide_zoom_overlay(self):
        """Oculta el label flotante de zoom."""
        self.zoom_overlay_label.hide()

    def _request_window_resize(self, image_width: int, image_height: int):
        """Calcula el ancho de ventana ideal y emite `window_resize_requested`.

        Adaptado del original `_adjust_window_size`: NavigationController es QWidget
        (no QDialog), por lo que no puede llamar `self.resize()` directamente; el composer
        (SlideshowViewer) recibe la senal y ejecuta su propio resize.
        """
        SPACING = 15
        MARGINS = 20
        SCROLL_BORDER = 4
        EXTRA_PADDING = 20

        new_window_width = (
            self.controls_panel_width +
            SPACING +
            image_width +
            SCROLL_BORDER +
            MARGINS +
            EXTRA_PADDING
        )
        # El alto lo mantiene el composer (no se modifica aqui)
        self.window_resize_requested.emit(new_window_width, image_height)

    def _update_counter(self):
        """Actualiza el contador de imagenes."""
        if self.image_files:
            self.counter_label.setText(
                f"{self.current_index + 1} / {len(self.image_files)}"
            )
        else:
            self.counter_label.setText("0 / 0")

    def _clear_image_memory(self):
        """Limpia la imagen de memoria al navegar a otra imagen.

        Solo limpia state propio de navigation (working_image, base_image_for_preview).
        # TODO Plan 02: el processor limpia su propio state via slot on_image_changed
        # (current_event_*, preview_image, is_preview_active viven en el processor).
        """
        self.working_image = None
        self.base_image_for_preview = None
        self._preview_image_from_processor = None

    # ===================================================================
    # Navegacion publica (slots)
    # ===================================================================
    def request_next(self):
        """Slot publico: avanza a la siguiente imagen.

        Si current_index == len-1, emite `finish_requested` para que el composer
        muestre el dialogo de fin (no llama _finish_review directamente).
        """
        # Limpiar memoria de eventos de la imagen actual
        self._clear_image_memory()

        # Guardar la imagen actual si no ha sido procesada
        if self.current_index not in self.processed_images:
            self._save_current_image_as_is()

        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._show_current_image()
        else:
            # Si ya estamos en la ultima imagen, delegar al composer
            self.finish_requested.emit()

    def request_previous(self):
        """Slot publico: retrocede a la imagen anterior."""
        self._clear_image_memory()

        if self.current_index > 0:
            self.current_index -= 1
            self._show_current_image()

    def _save_current_image_as_is(self):
        """Guarda la imagen actual sin modificaciones (no se removio ninguna marca).

        Preserva el comportamiento intencional (RESEARCH Assumption A5): si el usuario
        salta una imagen, igual se copia al output_folder.
        """
        if not self.output_folder or not self.image_files:
            return

        try:
            current_file = self.image_files[self.current_index]

            image = load_images_cv2(current_file)
            if image is None:
                self._log(f"⚠️ Error cargando imagen: {current_file.name}")
                return

            guardar(current_file, image, self.output_folder)
            self.processed_images.add(self.current_index)
            self._log(f"💾 Imagen guardada sin cambios: {current_file.name}")

        except Exception as e:
            self._log(f"❌ Error guardando imagen: {e}")

    # ===================================================================
    # Wiring con WatermarkProcessor (Plan 02 — stubs por ahora)
    # ===================================================================
    def set_navigation_enabled(self, enabled: bool):
        """Slot publico: el processor lo invoca para bloquear/desbloquear prev/next
        durante un preview activo (patron processing_blocked — PATTERNS line 632).
        """
        self.prev_btn.setEnabled(enabled and self.current_index > 0)
        self.next_btn.setEnabled(enabled and self.current_index < len(self.image_files) - 1)

    def on_preview_changed(self, preview_image):
        """Plan 02 wiring: el processor envia preview_image (np.ndarray) para mostrar.

        En esta fase: guardar el preview y refrescar via _apply_zoom.
        """
        self._preview_image_from_processor = preview_image
        self._apply_zoom()

    def on_image_processed(self, file, working_image, *args):
        """Plan 02 wiring: tras accept del processor, actualizar working_image."""
        self.working_image = working_image
        self.processed_images.add(self.current_index)
        self._preview_image_from_processor = None
        self._apply_zoom()

    def reset_current_image(self):
        """Slot: el processor emitio image_reset (o request_image_reload).

        Recarga working_image desde disco y refresca display. Tambien quita los
        marcadores de processed_images/processed_positions para esta imagen.
        """
        if not self.image_files:
            return
        current_file = self.image_files[self.current_index]
        self.working_image = load_images_cv2(current_file)
        self.processed_images.discard(self.current_index)
        self.processed_positions.pop(self.current_index, None)
        self._preview_image_from_processor = None
        self._show_current_image()

    # ===================================================================
    # Plan 02-02 wiring: slots publicos invocados por composer/processor
    # ===================================================================
    def set_processor_decorator(self, callback):
        """Registra el callback `decorate_pixmap(pixmap, scale_factor) -> QPixmap`
        del processor. El composer llama esto despues de instanciar el processor.

        Permite que `_apply_zoom` invoque al processor para pintar overlays
        sin coupling directo a la clase.
        """
        self._processor_decorate = callback

    def set_mouse_tracking(self, enabled: bool):
        """Slot: el processor activa/desactiva mouseTracking sobre image_label al
        toggle del modo manual.
        """
        self.image_label.setMouseTracking(enabled)

    def set_manual_overlay_visible(self, visible: bool):
        """Slot: muestra/oculta el manual_overlay_label."""
        if visible:
            self.manual_overlay_label.show()
        else:
            self.manual_overlay_label.hide()

    def set_manual_overlay_geometry(self, image_x: int, image_y: int, wm_width: int, wm_height: int):
        """Slot: el processor pide reposicionar el manual_overlay_label.

        El processor emite (image_x, image_y, wm_width, wm_height) en coords de imagen
        SIN escala. Aqui se aplica el zoom_level y la conversion al scroll_area.
        """
        try:
            scale_factor = self.zoom_level / 100.0
            scaled_width = int(wm_width * scale_factor)
            scaled_height = int(wm_height * scale_factor)
            # image_x/y vienen en coords de imagen original (sin escala). Convertir a
            # coords del image_label (con escala). El image_label esta dentro del scroll_area;
            # el manual_overlay_label es hijo del scroll_area (no del image_label) — entonces
            # debemos convertir las coords de imagen → coords del scroll_area.
            scaled_x_on_label = int(image_x * scale_factor)
            scaled_y_on_label = int(image_y * scale_factor)
            # Punto en image_label, convertir a scroll_area
            from PySide6.QtCore import QPoint as _QPoint
            global_pos = self.image_label.mapToGlobal(_QPoint(scaled_x_on_label, scaled_y_on_label))
            scroll_pos = self.scroll_area.mapFromGlobal(global_pos)
            overlay_x = scroll_pos.x() - scaled_width // 2
            overlay_y = scroll_pos.y() - scaled_height // 2
            self.manual_overlay_label.setGeometry(overlay_x, overlay_y, scaled_width, scaled_height)
            self.manual_overlay_label.raise_()
        except Exception:
            # No critico — un overlay desactualizado no rompe el flujo
            pass

    def on_position_processed(self, pos_name: str):
        """Slot (futuro): el processor notifica que una posicion fue procesada.

        Plan 02-02 mantiene processed_positions en navigation por compatibilidad
        con el API publica. El processor pasa `pos_name` para que navigation
        actualice el set local.
        """
        if pos_name:
            self.processed_positions.setdefault(self.current_index, set()).add(pos_name)
            self.processed_images.add(self.current_index)

    # ===================================================================
    # eventFilter — propaga clicks y mouse moves al processor via signals
    # ===================================================================
    def eventFilter(self, watched, event):
        """Captura mouse events sobre image_label y los emite via signals.

        - MouseMove (cuando mouseTracking esta activo, i.e. manual mode): emit
          mouse_moved con coords de imagen (sin escala de zoom).
        - MouseButtonPress (left/right): emit image_clicked con coords del image_label
          (con escala). El processor recibe y decide accion segun modo activo.
        """
        if watched is self.image_label:
            if event.type() == QEvent.Type.MouseMove:
                # Convertir pos a coords de imagen (sin escala de zoom) — el processor
                # las espera asi para alimentar mouse_position que despues compara con find_wm.
                scale_factor = self.zoom_level / 100.0 if self.zoom_level else 1.0
                if scale_factor == 0:
                    scale_factor = 1.0
                image_x = int(event.pos().x() / scale_factor)
                image_y = int(event.pos().y() / scale_factor)
                self.mouse_moved.emit(QPoint(image_x, image_y))
                return False  # propagar
            if event.type() == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self.image_clicked.emit(event.pos(), "left")
                    return True
                if event.button() == Qt.MouseButton.RightButton:
                    self.image_clicked.emit(event.pos(), "right")
                    return True
        return super().eventFilter(watched, event)

    # ===================================================================
    # wheelEvent — zoom con Ctrl+rueda
    # ===================================================================
    def wheelEvent(self, event: QWheelEvent):
        """Zoom con Ctrl+rueda. NavigationController owns image_label y scroll_area,
        asi que es el natural owner del wheel zoom.
        """
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            zoom_change = 10 if delta > 0 else -10
            new_zoom = self.zoom_level + zoom_change
            self._set_zoom(new_zoom)
            event.accept()
        else:
            super().wheelEvent(event)
