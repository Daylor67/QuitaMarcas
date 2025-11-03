"""
Pestaña UI para Watermark Remover
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QTextEdit, QPushButton
)
from PySide6.QtCore import Qt

# Agregar el directorio raíz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils import UtilJson
from .image_viewer import ImageViewer
from .position_editor import PositionEditor


class WatermarkTab(QWidget):
    """
    Pestaña de Quita Marcas - Widget independiente para eliminar marcas de agua

    Esta pestaña replica la funcionalidad que agregaste manualmente al layout.ui,
    pero de forma programática y modular.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        """Configura la interfaz de usuario"""
        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(6, 6, 6, 6)

        # GroupBox de configuración
        settings_group = QGroupBox("Quita Marcas Settings")
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(4)
        settings_layout.setContentsMargins(6, 6, 6, 6)

        # CheckBox: Ejecutar Quita Marcas
        self.run_quita_marcas = QCheckBox("Ejecutar Quita Marcas")
        settings_layout.addWidget(self.run_quita_marcas)

        # Botón para abrir visor de imágenes
        self.view_images_btn = QPushButton("Ver Imágenes de Input")
        self.view_images_btn.setStyleSheet("padding: 8px; color: white;")
        self.view_images_btn.clicked.connect(self._open_image_viewer)
        settings_layout.addWidget(self.view_images_btn)

        # Botón para abrir editor de posiciones
        self.edit_positions_btn = QPushButton("⚙️ Editor de Posiciones de Marcas")
        self.edit_positions_btn.setStyleSheet("padding: 8px; color: white; font-weight: bold;")
        self.edit_positions_btn.clicked.connect(self._open_position_editor)
        settings_layout.addWidget(self.edit_positions_btn)

        # Layout horizontal (placeholder para futuros controles)
        post_process_layout = QHBoxLayout()
        settings_layout.addLayout(post_process_layout)

        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)

        # TextEdit: Consola de proceso
        self.process_console = QTextEdit()
        self.process_console.setEnabled(True)
        self.process_console.setReadOnly(True)
        main_layout.addWidget(self.process_console)

        # Conectar señales
        self._connect_signals()

    def _connect_signals(self):
        """Conecta las señales de los widgets"""
        pass

    def _open_image_viewer(self):
        # TODO: En lugar de mostrar todas las imagenes, activar 
        # unicamente cuando hay imagenes que puedan generar errores
        
        """Abre el visor de imágenes con la carpeta del inputField"""
        try:
            # Obtener el MainWindow desde el parent
            main_window = self._get_main_window()

            if main_window is None:
                self.log("Error: No se pudo acceder a la ventana principal")
                return

            # Obtener la ruta del inputField
            input_path = main_window.inputField.text()

            if not input_path:
                self.log("Error: No hay carpeta seleccionada en Input")
                return

            # Verificar que la ruta existe
            if not Path(input_path).exists():
                self.log(f"Error: La ruta no existe: {input_path}")
                return

            # Abrir el visor
            self.log(f"Abriendo visor para: {input_path}")
            viewer = ImageViewer(input_path, self)
            viewer.exec()

        except Exception as e:
            self.log(f"Error al abrir visor: {str(e)}")

    def _open_position_editor(self):
        """Abre el editor de posiciones de marcas de agua"""
        try:
            self.log("Abriendo editor de posiciones...")
            editor = PositionEditor(self)
            result = editor.exec()

            if result:
                self.log("Editor cerrado correctamente")
            else:
                self.log("Editor cancelado")

        except Exception as e:
            self.log(f"Error al abrir editor: {str(e)}")

    def _get_main_window(self):
        """Busca y retorna el MainWindow (ventana principal)"""
        widget = self.parent()
        while widget is not None:
            # Verificar si tiene el atributo inputField (característica del MainWindow)
            if hasattr(widget, 'inputField'):
                return widget
            widget = widget.parent()
        return None

    def log(self, message: str):
        """Agrega un mensaje a la consola de proceso"""
        self.process_console.append(message)

    def get_settings(self) -> dict:
        """
        Retorna la configuración actual de la pestaña

        Returns:
            dict: Configuración con las siguientes claves:
                - run_quita_marcas (bool)
        """
        return {
            'run_quita_marcas': self.run_quita_marcas.isChecked()
        }

    def set_settings(self, settings: dict):
        """
        Aplica configuración a la pestaña

        Args:
            settings (dict): Diccionario con la configuración
        """
        if 'run_quita_marcas' in settings:
            self.run_quita_marcas.setChecked(settings['run_quita_marcas'])


# Para pruebas independientes
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

    app = QApplication(sys.argv)

    # Crear ventana de prueba
    window = QMainWindow()
    window.setWindowTitle("Test - Watermark Tab")
    window.setMinimumSize(500, 400)

    # Crear TabWidget y agregar nuestra pestaña
    tab_widget = QTabWidget()
    watermark_tab = WatermarkTab()
    tab_widget.addTab(watermark_tab, "Quita Marcas")

    window.setCentralWidget(tab_widget)
    window.show()

    sys.exit(app.exec())
