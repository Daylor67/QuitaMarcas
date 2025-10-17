"""
Visor de imágenes tipo slideshow - Navega con Space y Backspace
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QKeyEvent

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

        self._setup_ui()
        self._load_image_list()

        if self.image_files:
            self._show_current_image()

    def _setup_ui(self):
        """Configura la interfaz de usuario"""
        self.setWindowTitle("Revisión de Imágenes - Presiona Space para continuar")
        self.setModal(True)  # Bloquea la ventana principal
        self.resize(1200, 800)
        self.setMinimumSize(800, 600)

        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header con información
        header_layout = QHBoxLayout()

        self.folder_label = QLabel()
        self.folder_label.setStyleSheet("font-weight: bold; font-size: 12px;")

        self.counter_label = QLabel()
        self.counter_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2196F3;")

        header_layout.addWidget(QLabel("Carpeta:"))
        header_layout.addWidget(self.folder_label, 1)
        header_layout.addWidget(self.counter_label)

        main_layout.addLayout(header_layout)

        # Área de imagen
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #2b2b2b; border: 2px solid #444;")
        self.image_label.setMinimumSize(600, 400)
        main_layout.addWidget(self.image_label, 1)

        # Nombre del archivo actual
        self.filename_label = QLabel()
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setStyleSheet("font-size: 14px; color: #666; padding: 5px;")
        main_layout.addLayout(QHBoxLayout())
        main_layout.addWidget(self.filename_label)

        # Botones
        button_layout = QHBoxLayout()

        self.prev_btn = QPushButton("⬅️ Anterior (Backspace)")
        self.prev_btn.clicked.connect(self._previous_image)
        self.prev_btn.setStyleSheet("padding: 10px; font-size: 12px;")

        self.next_btn = QPushButton("Siguiente (Space) ➡️")
        self.next_btn.clicked.connect(self._next_image)
        self.next_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #4CAF50; color: white;")

        self.finish_btn = QPushButton("✓ Finalizar y Procesar (Enter)")
        self.finish_btn.clicked.connect(self._finish_review)
        self.finish_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #2196F3; color: white;")

        self.cancel_btn = QPushButton("✗ Cancelar (Esc)")
        self.cancel_btn.clicked.connect(self._cancel_review)
        self.cancel_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #f44336; color: white;")

        button_layout.addWidget(self.prev_btn)
        button_layout.addWidget(self.next_btn)
        button_layout.addWidget(self.finish_btn)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)

        if self.folder_path:
            self.folder_label.setText(str(self.folder_path))

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
        """Muestra la imagen actual"""
        if not self.image_files or self.current_index >= len(self.image_files):
            return

        current_file = self.image_files[self.current_index]

        # Cargar y mostrar imagen
        pixmap = QPixmap(str(current_file))
        if not pixmap.isNull():
            # Escalar imagen para que quepa en el label manteniendo aspecto
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
        else:
            self.image_label.setText("Error cargando imagen")

        # Actualizar nombre de archivo
        self.filename_label.setText(f"📄 {current_file.name}")

        # Actualizar contador
        self._update_counter()

        # Actualizar estado de botones
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)

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

    def keyPressEvent(self, event: QKeyEvent):
        """Maneja los eventos de teclado"""
        key = event.key()

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

    def resizeEvent(self, event):
        """Actualiza la imagen cuando se redimensiona la ventana"""
        super().resizeEvent(event)
        if self.image_files:
            self._show_current_image()

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
