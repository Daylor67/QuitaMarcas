"""
Pestaña UI para Watermark Remover
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QCheckBox, QLabel, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt

# Agregar el directorio raíz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utils import UtilJson


class WatermarkTab(QWidget):
    """
    Pestaña de Quita Marcas - Widget independiente para eliminar marcas de agua

    Esta pestaña replica la funcionalidad que agregaste manualmente al layout.ui,
    pero de forma programática y modular.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._load_newtoki_numbers()

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

        # CheckBox: Omitir
        self.omitir_checkbox = QCheckBox("[V1] Omitir primera imagen | [V2] sin marca color")
        settings_layout.addWidget(self.omitir_checkbox)

        # Label: Número de Newtoki
        newtoki_label = QLabel("Numero de Newtoki")
        settings_layout.addWidget(newtoki_label)

        # ComboBox: Selector de número
        self.newtoki_number = QComboBox()
        settings_layout.addWidget(self.newtoki_number)

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
        self.run_quita_marcas.stateChanged.connect(self._on_run_changed)
        self.newtoki_number.currentTextChanged.connect(self._on_newtoki_changed)

    def _load_newtoki_numbers(self):
        """Carga los números de Newtoki disponibles desde el JSON"""
        try:
            # Obtener la ruta del JSON de posiciones
            wm_dir = os.path.dirname(current_dir)
            positions_path = Path(wm_dir) / 'wm_poscition.json'

            if not positions_path.exists():
                self.log("Archivo de posiciones no encontrado")
                return

            # Cargar sitios disponibles
            positions_file = UtilJson(positions_path)
            sites = positions_file.keys()

            # Agregar al combobox
            self.newtoki_number.clear()
            self.newtoki_number.addItems(sites)

            self.log(f"Cargados {len(sites)} sitios: {', '.join(sites)}")

        except Exception as e:
            self.log(f"Error cargando números de Newtoki: {e}")

    def _on_run_changed(self, state):
        """Callback cuando cambia el estado de 'Ejecutar Quita Marcas'"""
        if state == Qt.CheckState.Checked.value:
            self.log("Quita Marcas activado")
        else:
            self.log("Quita Marcas desactivado")

    def _on_newtoki_changed(self, text):
        """Callback cuando cambia el número de Newtoki seleccionado"""
        if text:
            self.log(f"Sitio seleccionado: {text}")

    def log(self, message: str):
        """Agrega un mensaje a la consola de proceso"""
        self.process_console.append(message)

    def get_settings(self) -> dict:
        """
        Retorna la configuración actual de la pestaña

        Returns:
            dict: Configuración con las siguientes claves:
                - run_quita_marcas (bool)
                - omitir (bool)
                - newtoki_number (str)
        """
        return {
            'run_quita_marcas': self.run_quita_marcas.isChecked(),
            'omitir': self.omitir_checkbox.isChecked(),
            'newtoki_number': self.newtoki_number.currentText()
        }

    def set_settings(self, settings: dict):
        """
        Aplica configuración a la pestaña

        Args:
            settings (dict): Diccionario con la configuración
        """
        if 'run_quita_marcas' in settings:
            self.run_quita_marcas.setChecked(settings['run_quita_marcas'])

        if 'omitir' in settings:
            self.omitir_checkbox.setChecked(settings['omitir'])

        if 'newtoki_number' in settings:
            index = self.newtoki_number.findText(settings['newtoki_number'])
            if index >= 0:
                self.newtoki_number.setCurrentIndex(index)


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
