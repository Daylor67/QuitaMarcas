"""
Diálogo de actualización para notificar al usuario sobre nuevas versiones
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QTextEdit)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from core.services.update_checker import UpdateChecker
from core.services import SettingsHandler


class DownloadThread(QThread):
    """Thread para descargar la actualización sin bloquear la GUI"""
    progress = Signal(int, int)  # downloaded, total
    finished = Signal(str)  # path del archivo descargado
    error = Signal(str)  # mensaje de error

    def __init__(self, download_url):
        super().__init__()
        self.download_url = download_url
        self.updater = UpdateChecker()

    def run(self):
        try:
            zip_path = self.updater.download_update(
                self.download_url,
                lambda downloaded, total: self.progress.emit(downloaded, total)
            )

            if zip_path:
                self.finished.emit(zip_path)
            else:
                self.error.emit("Error al descargar la actualización")

        except Exception as e:
            self.error.emit(str(e))


class UpdateDialog(QDialog):
    """Diálogo que muestra información de actualización y permite descargar"""

    def __init__(self, parent, current_version, latest_version, download_url, release_notes):
        super().__init__(parent)
        self.current_version = current_version
        self.latest_version = latest_version
        self.download_url = download_url
        self.release_notes = release_notes
        self.updater = UpdateChecker()
        self.download_thread = None
        self.settings = SettingsHandler()

        self.init_ui()

    def init_ui(self):
        """Inicializa la interfaz del diálogo"""
        self.setWindowTitle("Actualización Disponible")
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()

        # Título
        title = QLabel(f"Nueva versión disponible: v{self.latest_version}")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        # Versión actual
        current = QLabel(f"Versión actual: v{self.current_version}")
        layout.addWidget(current)

        layout.addSpacing(10)

        # Notas de la versión
        notes_label = QLabel("Notas de la versión:")
        notes_label.setFont(QFont("", 10, QFont.Bold))
        layout.addWidget(notes_label)

        self.notes_text = QTextEdit()
        self.notes_text.setReadOnly(True)
        self.notes_text.setMarkdown(self.release_notes)
        self.notes_text.setMaximumHeight(200)
        layout.addWidget(self.notes_text)

        layout.addSpacing(10)

        # Barra de progreso (oculta inicialmente)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Label de estado
        self.status_label = QLabel("")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Botones
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.later_button = QPushButton("Más tarde")
        self.later_button.clicked.connect(self.on_later_clicked)
        button_layout.addWidget(self.later_button)

        self.update_button = QPushButton("Actualizar ahora")
        self.update_button.setDefault(True)
        self.update_button.clicked.connect(self.start_update)
        button_layout.addWidget(self.update_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def on_later_clicked(self):
        """Guarda la versión rechazada y cierra el diálogo"""
        self.settings.save("skipped_update_version", self.latest_version)
        self.reject()

    def start_update(self):
        """Inicia la descarga de la actualización"""
        self.update_button.setEnabled(False)
        self.later_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.status_label.setText("Descargando actualización...")

        # Crear y conectar thread de descarga
        self.download_thread = DownloadThread(self.download_url)
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.finished.connect(self.download_finished)
        self.download_thread.error.connect(self.download_error)
        self.download_thread.start()

    def update_progress(self, downloaded, total):
        """Actualiza la barra de progreso"""
        if total > 0:
            progress = int((downloaded / total) * 100)
            self.progress_bar.setValue(progress)

            # Mostrar tamaño en MB
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            self.status_label.setText(
                f"Descargando: {downloaded_mb:.1f} MB / {total_mb:.1f} MB ({progress}%)"
            )

    def download_finished(self, zip_path):
        """Llamado cuando la descarga termina"""
        self.status_label.setText("Descarga completada. Aplicando actualización...")
        self.progress_bar.setVisible(False)

        # Limpiar la versión rechazada ya que el usuario decidió actualizar
        self.settings.save("skipped_update_version", "")

        # Aplicar actualización
        if self.updater.apply_update(zip_path):
            self.status_label.setText(
                "Actualización aplicada. La aplicación se reiniciará..."
            )
            # Cerrar la aplicación (el script se encargará de reiniciarla)
            import sys
            sys.exit(0)
        else:
            self.download_error("No se pudo aplicar la actualización")

    def download_error(self, error_msg):
        """Llamado cuando hay un error"""
        self.status_label.setText(f"Error: {error_msg}")
        self.progress_bar.setVisible(False)
        self.update_button.setEnabled(True)
        self.later_button.setEnabled(True)


class UpdateNotificationDialog(QDialog):
    """Diálogo simple para notificar sobre actualizaciones"""

    def __init__(self, parent, current_version, latest_version):
        super().__init__(parent)
        self.setWindowTitle("Actualización Disponible")
        self.init_ui(current_version, latest_version)

    def init_ui(self, current_version, latest_version):
        layout = QVBoxLayout()

        # Mensaje
        message = QLabel(
            f"Hay una nueva versión disponible de SmartStitch WR.\n\n"
            f"Versión actual: v{current_version}\n"
            f"Nueva versión: v{latest_version}\n\n"
            f"¿Deseas actualizar ahora?"
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        # Botones
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        no_button = QPushButton("No")
        no_button.clicked.connect(self.reject)
        button_layout.addWidget(no_button)

        yes_button = QPushButton("Sí")
        yes_button.setDefault(True)
        yes_button.clicked.connect(self.accept)
        button_layout.addWidget(yes_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
