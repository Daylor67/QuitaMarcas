"""
Editor interactivo de posiciones de marcas de agua - Version reorganizada
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QGroupBox, QFileDialog, QWidget, QMessageBox,
    QScrollArea, QSlider, QSpinBox
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPixmap, QKeyEvent, QImage, QWheelEvent
import numpy as np
import cv2

# Agregar el directorio raíz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils import UtilJson
from WatermarkRemove import load_images_cv2, align_watermark, remove_watermark


class ZoomableImageLabel(QLabel):
    """Label que soporta zoom con scroll del mouse"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.zoom_level = 100
        self.original_pixmap = None
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #2b2b2b;")
        self.setSizePolicy(
            QWidget().sizePolicy().Policy.Expanding,
            QWidget().sizePolicy().Policy.Expanding
        )

    def set_image(self, pixmap: QPixmap):
        """Establece la imagen original"""
        self.original_pixmap = pixmap
        self.update_display()

    def update_display(self):
        """Actualiza la visualización con el zoom actual"""
        if self.original_pixmap is None:
            return

        # Calcular nuevo tamaño basado en zoom
        scale_factor = self.zoom_level / 100.0
        new_size = self.original_pixmap.size() * scale_factor

        # Escalar imagen
        scaled_pixmap = self.original_pixmap.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.setPixmap(scaled_pixmap)

        # Ajustar el tamaño del label al pixmap para que funcione el scroll
        self.resize(scaled_pixmap.size())

    def set_zoom(self, zoom: int):
        """Establece el nivel de zoom (10-200%)"""
        self.zoom_level = max(10, min(200, zoom))
        self.update_display()


class PositionEditor(QDialog):
    """
    Editor interactivo para ajustar posiciones de marcas de agua

    Layout: Controles a la izquierda | Imagen con zoom a la derecha
    """

    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tga', '.jfif')

    def __init__(self, parent=None):
        super().__init__(parent)

        # Datos
        self.images_folder = None
        self.watermarks_folder = None
        self.image_files = []
        self.watermark_files = []
        self.current_image_index = 0
        self.current_image = None
        self.current_watermark = None

        # Posición actual
        self.offset_x = 0
        self.offset_y = 0
        self.side_x = "left"
        self.side_y = "top"

        # Posiciones guardadas
        self.saved_positions = []

        self._setup_ui()

    def _setup_ui(self):
        """Configura la interfaz de usuario con layout horizontal"""
        self.setWindowTitle("Editor de Posiciones de Marca de Agua")
        self.setModal(True)
        self.resize(1300, 750)
        self.setMinimumSize(1100, 650)

        # Layout principal HORIZONTAL
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === PANEL IZQUIERDO: Controles (fijo 380px) ===
        left_panel = self._create_controls_panel()
        main_layout.addWidget(left_panel)

        # === PANEL DERECHO: Imagen con zoom ===
        right_panel = self._create_image_panel()
        main_layout.addWidget(right_panel, 1)  # stretch=1 para que use todo el espacio

    def _create_controls_panel(self) -> QWidget:
        """Crea el panel de controles (izquierda)"""
        panel = QWidget()
        panel.setFixedWidth(380)
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        # Carpetas
        folders_group = QGroupBox("📁 Selección")
        folders_layout = QVBoxLayout()
        folders_layout.setSpacing(6)

        # Botón carpeta imágenes
        btn_images = QPushButton("📂 Carpeta de Imágenes")
        btn_images.clicked.connect(self._select_images_folder)
        btn_images.setStyleSheet("padding: 6px;")
        folders_layout.addWidget(btn_images)

        self.images_label = QLabel("No seleccionada")
        self.images_label.setStyleSheet("color: #666; font-size: 10px; padding-left: 10px;")
        self.images_label.setWordWrap(True)
        folders_layout.addWidget(self.images_label)

        # Botón carpeta marcas
        btn_watermarks = QPushButton("📂 Carpeta de Marcas de Agua")
        btn_watermarks.clicked.connect(self._select_watermarks_folder)
        btn_watermarks.setStyleSheet("padding: 6px;")
        folders_layout.addWidget(btn_watermarks)

        self.watermarks_label = QLabel("No seleccionada")
        self.watermarks_label.setStyleSheet("color: #666; font-size: 10px; padding-left: 10px;")
        self.watermarks_label.setWordWrap(True)
        folders_layout.addWidget(self.watermarks_label)

        # Selector de marca
        folders_layout.addWidget(QLabel("Marca actual:"))
        self.watermark_combo = QComboBox()
        self.watermark_combo.currentIndexChanged.connect(self._on_watermark_changed)
        folders_layout.addWidget(self.watermark_combo)

        folders_group.setLayout(folders_layout)
        layout.addWidget(folders_group)

        # Controles de posición
        position_group = QGroupBox("🎮 Posición")
        position_layout = QVBoxLayout()
        position_layout.setSpacing(8)

        # Side X
        position_layout.addWidget(QLabel("Horizontal:"))
        self.side_x_combo = QComboBox()
        self.side_x_combo.addItem("Izquierda", "left")
        self.side_x_combo.addItem("Centro", "center")
        self.side_x_combo.addItem("Derecha", "right")
        self.side_x_combo.currentIndexChanged.connect(self._on_position_changed)
        position_layout.addWidget(self.side_x_combo)

        # Side Y
        position_layout.addWidget(QLabel("Vertical:"))
        self.side_y_combo = QComboBox()
        self.side_y_combo.addItem("Arriba", "top")
        self.side_y_combo.addItem("Centro", "center")
        self.side_y_combo.addItem("Abajo", "bottom")
        self.side_y_combo.currentIndexChanged.connect(self._on_position_changed)
        position_layout.addWidget(self.side_y_combo)

        # Offsets con botones y SpinBox editable
        position_layout.addWidget(QLabel("Ajuste Fino (pixel):"))

        # Control de Offset X
        offset_x_container = QWidget()
        offset_x_layout = QHBoxLayout(offset_x_container)
        offset_x_layout.setContentsMargins(0, 0, 0, 0)
        offset_x_layout.setSpacing(5)

        offset_x_layout.addWidget(QLabel("X:"))

        btn_x_minus = QPushButton("◀")
        btn_x_minus.setFixedSize(30, 30)
        btn_x_minus.setAutoRepeat(True)  # Incremento automático al mantener
        btn_x_minus.setAutoRepeatDelay(500)  # Espera antes de repetir
        btn_x_minus.setAutoRepeatInterval(50)  # Intervalo de repetición
        btn_x_minus.clicked.connect(lambda: self._adjust_offset('x', -1))
        offset_x_layout.addWidget(btn_x_minus)

        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-9999, 9999)
        self.offset_x_spin.setValue(0)
        self.offset_x_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offset_x_spin.valueChanged.connect(lambda v: self._on_offset_spin_changed('x', v))
        offset_x_layout.addWidget(self.offset_x_spin, 1)

        btn_x_plus = QPushButton("▶")
        btn_x_plus.setFixedSize(30, 30)
        btn_x_plus.setAutoRepeat(True)
        btn_x_plus.setAutoRepeatDelay(500)
        btn_x_plus.setAutoRepeatInterval(50)
        btn_x_plus.clicked.connect(lambda: self._adjust_offset('x', 1))
        offset_x_layout.addWidget(btn_x_plus)

        position_layout.addWidget(offset_x_container)

        # Control de Offset Y
        offset_y_container = QWidget()
        offset_y_layout = QHBoxLayout(offset_y_container)
        offset_y_layout.setContentsMargins(0, 0, 0, 0)
        offset_y_layout.setSpacing(5)

        offset_y_layout.addWidget(QLabel("Y:"))

        btn_y_minus = QPushButton("◀")
        btn_y_minus.setFixedSize(30, 30)
        btn_y_minus.setAutoRepeat(True)
        btn_y_minus.setAutoRepeatDelay(500)
        btn_y_minus.setAutoRepeatInterval(50)
        btn_y_minus.clicked.connect(lambda: self._adjust_offset('y', -1))
        offset_y_layout.addWidget(btn_y_minus)

        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-9999, 9999)
        self.offset_y_spin.setValue(0)
        self.offset_y_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.offset_y_spin.valueChanged.connect(lambda v: self._on_offset_spin_changed('y', v))
        offset_y_layout.addWidget(self.offset_y_spin, 1)

        btn_y_plus = QPushButton("▶")
        btn_y_plus.setFixedSize(30, 30)
        btn_y_plus.setAutoRepeat(True)
        btn_y_plus.setAutoRepeatDelay(500)
        btn_y_plus.setAutoRepeatInterval(50)
        btn_y_plus.clicked.connect(lambda: self._adjust_offset('y', 1))
        offset_y_layout.addWidget(btn_y_plus)

        position_layout.addWidget(offset_y_container)

        position_group.setLayout(position_layout)
        layout.addWidget(position_group)

        # Contador de imágenes
        self.counter_label = QLabel("0 / 0")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3; padding: 10px;")
        layout.addWidget(self.counter_label)

        # Instrucciones
        instructions = QLabel("⌨️ Enter: Guardar\nEsc: Cerrar")
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setStyleSheet(
            "background-color: #092D48; padding: 12px; "
            "border-radius: 5px; font-size: 11px; font-weight: bold;"
        )
        layout.addWidget(instructions)

        # Botones
        self.btn_save = QPushButton("💾 Guardar y Siguiente")
        self.btn_save.clicked.connect(self._save_and_next)
        self.btn_save.setStyleSheet("padding: 12px; background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_save.setEnabled(False)
        layout.addWidget(self.btn_save)

        btn_close = QPushButton("❌ Cerrar")
        btn_close.clicked.connect(self.close)
        btn_close.setStyleSheet("padding: 10px; background-color: #f44336; color: white;")
        layout.addWidget(btn_close)

        layout.addStretch()
        return panel

    def _create_image_panel(self) -> QWidget:
        """Crea el panel de imagen con zoom (derecha)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)

        # Controles de zoom
        zoom_container = QWidget()
        zoom_layout = QHBoxLayout(zoom_container)
        zoom_layout.setContentsMargins(0, 0, 0, 0)

        zoom_layout.addWidget(QLabel("Zoom:"))

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(10)
        self.zoom_slider.setMaximum(200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self._on_zoom_changed)
        zoom_layout.addWidget(self.zoom_slider, 1)

        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(50)
        self.zoom_label.setStyleSheet("font-weight: bold;")
        zoom_layout.addWidget(self.zoom_label)

        layout.addWidget(zoom_container)

        # Área de scroll con imagen
        scroll = QScrollArea()
        scroll.setWidgetResizable(False)  # Importante para que funcione el zoom
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("border: 2px solid #444;")

        self.image_label = ZoomableImageLabel()
        self.image_label.setMinimumSize(400, 300)
        scroll.setWidget(self.image_label)

        layout.addWidget(scroll, 1)

        return panel

    def _on_zoom_changed(self, value: int):
        """Callback cuando cambia el zoom"""
        self.zoom_label.setText(f"{value}%")
        self.image_label.set_zoom(value)

    def keyPressEvent(self, event: QKeyEvent):
        """Maneja los eventos de teclado (solo Enter y Esc)"""
        key = event.key()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if self.btn_save.isEnabled():
                self._save_and_next()
        elif key == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _adjust_offset(self, axis: str, delta: int):
        """Ajusta el offset en el eje dado usando los botones"""
        if axis == 'x':
            self.offset_x_spin.setValue(self.offset_x_spin.value() + delta)
        elif axis == 'y':
            self.offset_y_spin.setValue(self.offset_y_spin.value() + delta)

    def _on_offset_spin_changed(self, axis: str, value: int):
        """Callback cuando cambia el valor del SpinBox"""
        if axis == 'x':
            self.offset_x = value
        elif axis == 'y':
            self.offset_y = value

        self._update_preview()

    def _select_images_folder(self):
        """Abre diálogo para seleccionar carpeta de imágenes"""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Imágenes")
        if folder:
            self.images_folder = Path(folder)
            self.images_label.setText(self.images_folder.name)
            self._load_images()
            self._check_ready()

    def _select_watermarks_folder(self):
        """Abre diálogo para seleccionar carpeta de marcas de agua"""
        folder = QFileDialog.getExistingDirectory(self, "Seleccionar Carpeta de Marcas de Agua")
        if folder:
            self.watermarks_folder = Path(folder)
            self.watermarks_label.setText(self.watermarks_folder.name)
            self._load_watermarks()
            self._check_ready()

    def _load_images(self):
        """Carga la lista de imágenes"""
        if not self.images_folder or not self.images_folder.exists():
            return

        self.image_files = []
        for file in sorted(self.images_folder.iterdir()):
            if file.is_file() and file.suffix.lower() in self.SUPPORTED_FORMATS:
                self.image_files.append(file)

        self.current_image_index = 0
        self._update_counter()

    def _load_watermarks(self):
        """Carga la lista de marcas de agua"""
        if not self.watermarks_folder or not self.watermarks_folder.exists():
            return

        self.watermark_files = []
        self.watermark_combo.clear()

        for file in sorted(self.watermarks_folder.iterdir()):
            if file.is_file() and file.suffix.lower() == '.png':
                self.watermark_files.append(file)
                self.watermark_combo.addItem(file.name)

    def _check_ready(self):
        """Verifica si está listo para editar"""
        ready = (
            self.images_folder is not None and
            self.watermarks_folder is not None and
            len(self.image_files) > 0 and
            len(self.watermark_files) > 0
        )

        self.btn_save.setEnabled(ready)

        if ready:
            self._load_current_image()
            self._load_current_watermark()
            self._update_preview()

    def _load_current_image(self):
        """Carga la imagen actual"""
        if not self.image_files or self.current_image_index >= len(self.image_files):
            return

        image_path = self.image_files[self.current_image_index]
        self.current_image = load_images_cv2(str(image_path))

    def _load_current_watermark(self):
        """Carga la marca de agua actual"""
        if not self.watermark_files or self.watermark_combo.currentIndex() < 0:
            return

        watermark_path = self.watermark_files[self.watermark_combo.currentIndex()]
        self.current_watermark = load_images_cv2(str(watermark_path))

    def _on_watermark_changed(self, index):
        """Callback cuando cambia la marca"""
        if index >= 0:
            self._load_current_watermark()
            self._update_preview()

    def _on_position_changed(self):
        """Callback cuando cambian los controles de posición"""
        self.side_x = self.side_x_combo.currentData()
        self.side_y = self.side_y_combo.currentData()
        self._update_preview()

    def _update_preview(self):
        """Actualiza el preview con zoom"""
        if self.current_image is None or self.current_watermark is None:
            return

        try:
            # Hacer copia
            img_copy = self.current_image.copy()

            # Calcular coordenadas y aplicar remove_watermark
            x, y = align_watermark(
                img_copy, self.current_watermark,
                offset_x=self.offset_x, offset_y=self.offset_y,
                side_x=self.side_x, side_y=self.side_y
            )

            result_img = remove_watermark(img_copy, self.current_watermark, x, y)

            # Convertir a RGB y QPixmap
            result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
            height, width, channel = result_rgb.shape
            bytes_per_line = 3 * width
            q_image = QImage(result_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)

            # Establecer imagen (el label maneja el zoom)
            self.image_label.set_image(pixmap)

        except Exception as e:
            self.image_label.setText(f"❌ Error: {str(e)}")

    def _update_counter(self):
        """Actualiza el contador"""
        if self.image_files:
            self.counter_label.setText(f"{self.current_image_index + 1} / {len(self.image_files)}")
        else:
            self.counter_label.setText("0 / 0")

    def _save_and_next(self):
        """Guarda y pasa a la siguiente"""
        position_data = {
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
            'side_x': self.side_x,
            'side_y': self.side_y
        }
        self.saved_positions.append(position_data)

        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self._load_current_image()
            self._update_counter()
            self._update_preview()
            # Resetear zoom
            self.zoom_slider.setValue(100)
        else:
            self._save_to_json()
            QMessageBox.information(
                self, "Completado",
                f"Se guardaron {len(self.saved_positions)} posiciones correctamente"
            )
            self.accept()

    def _save_to_json(self):
        """Guarda en JSON"""
        if not self.watermarks_folder or not self.saved_positions:
            return

        try:
            watermark_folder_name = self.watermarks_folder.name
            wm_dir = os.path.dirname(current_dir)
            json_path = Path(wm_dir) / 'wm_positions.json'

            json_file = UtilJson(json_path)

            positions_dict = {}
            for i, pos_data in enumerate(self.saved_positions, start=1):
                positions_dict[f'pos_{i}'] = pos_data

            json_file.set(watermark_folder_name, positions_dict)
            print(f"✓ Guardadas {len(self.saved_positions)} posiciones en '{watermark_folder_name}'")

        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", f"No se pudieron guardar las posiciones:\n{str(e)}")


# Para pruebas
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    editor = PositionEditor()
    editor.show()
    sys.exit(app.exec())
