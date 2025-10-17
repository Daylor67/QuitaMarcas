"""
Visor de imágenes tipo slideshow - Navega con Space y Backspace
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QScrollArea, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation
from PySide6.QtGui import QPixmap, QKeyEvent, QWheelEvent

# Agregar el directorio raíz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)


class SlideshowViewer(QDialog):
    """
    Visor de imágenes estilo slideshow con navegación por teclado

    Controles:
        - Space: Siguiente imagen
        - Backspace: Imagen anterior
        - Enter: Finalizar revisión
        - Escape: Cancelar proceso
    """

    # Señal que se emite cuando el usuario finaliza la revisión
    review_completed = Signal(bool)  # True = continuar, False = cancelar

    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tga', '.psd', '.psb', '.jfif')

    def __init__(self, folder_path: str, parent=None):
        super().__init__(parent)
        self.folder_path = Path(folder_path) if folder_path else None
        self.image_files = []
        self.current_index = 0
        self.user_approved = False
        self.current_pixmap = None  # Pixmap original sin zoom
        self.zoom_level = 100  # Nivel de zoom actual
        self.controls_panel_width = 280  # Ancho del panel de controles para cálculos

        self._setup_ui()
        self._load_image_list()

        if self.image_files:
            self._show_current_image()

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

        # Información de carpeta
        info_group = QWidget()
        info_layout = QVBoxLayout(info_group)
        info_layout.setSpacing(5)

        info_layout.addWidget(QLabel("📁 Carpeta:"))
        self.folder_label = QLabel()
        self.folder_label.setStyleSheet("color: #666; font-size: 10px; padding-left: 10px;")
        self.folder_label.setWordWrap(True)
        info_layout.addWidget(self.folder_label)

        if self.folder_path:
            self.folder_label.setText(str(self.folder_path))

        layout.addWidget(info_group)

        # Contador de imágenes
        self.counter_label = QLabel("0 / 0")
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3; padding: 15px;")
        layout.addWidget(self.counter_label)

        # Nombre del archivo actual
        self.filename_label = QLabel("Sin archivo")
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setStyleSheet("font-size: 12px; color: #888; padding: 10px; background-color: #1e1e1e; border-radius: 5px;")
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)

        # Espaciador
        layout.addStretch()

        # Botones de navegación
        nav_layout = QVBoxLayout()
        nav_layout.setSpacing(8)

        self.prev_btn = QPushButton("Anterior")
        self.prev_btn.clicked.connect(self._previous_image)
        self.prev_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #555; color: white;")
        nav_layout.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Siguiente")
        self.next_btn.clicked.connect(self._next_image)
        self.next_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #4CAF50; color: white; font-weight: bold;")
        nav_layout.addWidget(self.next_btn)

        layout.addLayout(nav_layout)

        # Botones de acción
        action_layout = QVBoxLayout()
        action_layout.setSpacing(8)

        self.finish_btn = QPushButton("Finalizar y Procesar")
        self.finish_btn.clicked.connect(self._finish_review)
        self.finish_btn.setStyleSheet("padding: 12px; font-size: 12px; background-color: #2196F3; color: white; font-weight: bold;")
        action_layout.addWidget(self.finish_btn)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel_review)
        self.cancel_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #f44336; color: white;")
        action_layout.addWidget(self.cancel_btn)

        layout.addLayout(action_layout)

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

        layout.addWidget(scroll, 1)

        self.scroll_area = scroll  # Guardar referencia para uso posterior
        return panel

    def _load_image_list(self):
        """Carga la lista de archivos de imagen"""
        if not self.folder_path or not self.folder_path.exists():
            return

        # Si es un archivo, usar su directorio padre
        if self.folder_path.is_file():
            self.folder_path = self.folder_path.parent

        # Buscar todas las imágenes y ordenarlas
        for file in sorted(self.folder_path.iterdir()):
            if file.is_file() and file.suffix.lower() in self.SUPPORTED_FORMATS:
                self.image_files.append(file)

        self._update_counter()

    def _show_current_image(self):
        """Muestra la imagen actual con el zoom aplicado"""
        if not self.image_files or self.current_index >= len(self.image_files):
            return

        current_file = self.image_files[self.current_index]

        # Cargar imagen original
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
        """Aplica el nivel de zoom actual a la imagen"""
        if self.current_pixmap is None or self.current_pixmap.isNull():
            return

        # Calcular nuevo tamaño basado en zoom
        scale_factor = self.zoom_level / 100.0
        new_size = self.current_pixmap.size() * scale_factor

        # Escalar imagen
        scaled_pixmap = self.current_pixmap.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.image_label.setPixmap(scaled_pixmap)
        # Ajustar el tamaño del label para que funcione el scroll
        self.image_label.resize(scaled_pixmap.size())

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

    def _next_image(self):
        """Avanza a la siguiente imagen"""
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._show_current_image()
        else:
            # Si ya estamos en la última imagen, finalizar automáticamente
            self._finish_review()

    def _previous_image(self):
        """Retrocede a la imagen anterior"""
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current_image()

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
        if key == Qt.Key.Key_Space:
            self._next_image()
        elif key == Qt.Key.Key_Backspace:
            self._previous_image()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._finish_review()
        elif key == Qt.Key.Key_Escape:
            self._cancel_review()
        else:
            super().keyPressEvent(event)

    def get_approved(self) -> bool:
        """Retorna si el usuario aprobó continuar con el proceso"""
        return self.user_approved


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
