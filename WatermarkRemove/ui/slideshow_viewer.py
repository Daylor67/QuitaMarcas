"""Visor de imagenes tipo slideshow — composer puro tras Phase 2.

`SlideshowViewer` solo instancia los componentes hijos (NavigationController +
WatermarkProcessor + TrainingDataCollector), cablea sus signals en `_wire_signals`,
arma el layout, y conserva el contrato externo con `gui/controller.py`:

- Constructor (folder_path, parent, watermark_tab)
- Senal review_completed (bool)
- Metodos publicos get_approved / get_output_folder / has_processed_images

Procesamiento (manual, auto YOLO, position-grid, crop) vive en WatermarkProcessor;
navegacion + render + zoom + counter en NavigationController; conteo de training
data en TrainingDataCollector. `keyPressEvent` mantiene el guard load-bearing:
si el processor tiene preview activo, Space/Backspace van a accept/revert.
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QWidget,
    QScrollArea, QGroupBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

# Agregar el directorio raiz al path (bootstrap para importar el package).
_parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from WatermarkRemove.ui.components import (
    NavigationController, WatermarkProcessor, TrainingDataCollector,
)


class SlideshowViewer(QDialog):
    """Composer puro tras Phase 2: instancia componentes hijos, conecta sus
    signals y expone API publica estable (contrato con `gui/controller.py:321`).

    Controles: Space=siguiente/accept, Backspace=anterior/revert, Enter=finalizar,
    Escape=cancelar; zoom (Ctrl+rueda / Plus-Minus / 0) delegado a NavigationController.
    """

    # Senal preservada — consumida por gui/controller.py:321
    review_completed = Signal(bool)  # True = continuar, False = cancelar

    def __init__(self, folder_path: str, parent=None, watermark_tab=None):
        super().__init__(parent)

        # Estado del composer
        self.user_approved = False
        self.watermark_tab = watermark_tab
        self.controls_panel_width = 280

        # Instanciar componentes hijos
        self.navigation = NavigationController(folder_path, parent=self, watermark_tab=watermark_tab)
        self.processor = WatermarkProcessor(parent=self, watermark_tab=watermark_tab)
        self.collector = TrainingDataCollector(parent=self, watermark_tab=watermark_tab)

        # Wire signals ANTES de _setup_ui (callbacks iniciales necesitan el cableado), luego UI.
        self._wire_signals()
        self._setup_ui()

    def _wire_signals(self):
        """Conecta signals processor↔navigation y composer↔components."""

        # --- Navegacion -> Processor (notificar cambio de imagen/folder/clicks/moves) ---
        self.navigation.image_changed.connect(self.processor.on_image_changed)
        self.navigation.output_folder_ready.connect(self.processor.on_output_folder_ready)
        self.navigation.image_clicked.connect(self.processor.on_image_clicked)
        self.navigation.mouse_moved.connect(self.processor.on_mouse_moved)

        # --- Processor -> Navegacion (preview / final / bloqueo UI / reset / output folder) ---
        self.processor.preview_changed.connect(self.navigation.on_preview_changed)
        self.processor.image_processed.connect(self.navigation.on_image_processed)
        self.processor.processing_blocked.connect(
            lambda blocked: self.navigation.set_navigation_enabled(not blocked)
        )
        self.processor.image_reset.connect(self.navigation.reset_current_image)
        self.processor.request_image_reload.connect(self.navigation.reset_current_image)
        self.processor.request_redraw.connect(self.navigation._apply_zoom)
        self.processor.output_folder_request.connect(self.navigation._create_output_folder)
        self.processor.manual_tracking_requested.connect(self.navigation.set_mouse_tracking)
        self.processor.manual_overlay_visibility.connect(self.navigation.set_manual_overlay_visible)
        self.processor.manual_overlay_geometry.connect(self.navigation.set_manual_overlay_geometry)
        # decorate_pixmap callback restaura overlays de posiciones y crop
        self.navigation.set_processor_decorator(self.processor.decorate_pixmap)

        # --- Navigation -> composer ---
        self.navigation.window_resize_requested.connect(self._on_navigation_resize_requested)
        self.navigation.finish_requested.connect(self._finish_review)

        # --- Processor -> Collector (Plan 03 — cada accept/reset alimenta el collector) ---
        self.processor.image_processed.connect(self.collector.on_image_processed)
        self.processor.image_reset.connect(self.collector.on_image_reset)
        self.processor.counts_changed.connect(self.collector.on_counts_changed)

        # --- "Guardar y Siguiente" gatilla request_next (replica patron original) ---
        self.processor.auto_accept_next_btn.clicked.connect(self.navigation.request_next)

    def _setup_ui(self):
        """Layout horizontal: panel de controles (izq, 280px) + navigation (der)."""
        self.setWindowTitle("Revisión de Imágenes")
        self.setModal(True)
        self.resize(900, 650)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        main_layout.addWidget(self._create_controls_panel())
        main_layout.addWidget(self.navigation, 1)

    def _on_navigation_resize_requested(self, width: int, height: int):
        """Slot: NavigationController solicita resize. Mantiene altura actual y ajusta ancho."""
        self.resize(width, self.height())

    def _create_controls_panel(self) -> QWidget:
        """Panel de controles (izquierda, scroll vertical): WatermarkProcessor +
        grupo Navegacion (finish/cancel) + TrainingDataCollector (conteo)."""
        panel = QWidget()
        panel.setFixedWidth(self.controls_panel_width)

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

        # === 1. WatermarkProcessor (sus GroupBoxes "Seleccion" + "Auto") ===
        layout.addWidget(self.processor)

        # === 2. Grupo Navegacion (solo finish + cancel) ===
        nav_group = QGroupBox("✳️ Navegación")
        nav_action_layout = QHBoxLayout(nav_group)
        nav_action_layout.setSpacing(5)

        self.finish_btn = QPushButton("Finalizar y Procesar")
        self.finish_btn.clicked.connect(self._finish_review)
        self.finish_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #2196F3; color: white; font-weight: bold;")
        self.finish_btn.setMaximumHeight(40)
        nav_action_layout.addWidget(self.finish_btn)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel_review)
        self.cancel_btn.setStyleSheet("padding: 10px; font-size: 12px; background-color: #f44336; color: white;")
        self.cancel_btn.setMaximumHeight(40)
        nav_action_layout.addWidget(self.cancel_btn)

        layout.addWidget(nav_group)

        # === 3. TrainingDataCollector (su propio GroupBox "Datos recopilados") ===
        layout.addWidget(self.collector)
        layout.addStretch(1)
        return panel

    def _log(self, message: str):
        """Logger del composer (fallback a print)."""
        if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
            self.watermark_tab.log(message)
        else:
            print(message)

    def _finish_review(self):
        """Finaliza la revision y permite continuar con el proceso."""
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
        """Cancela la revision y el proceso."""
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

    def keyPressEvent(self, event: QKeyEvent):
        """Delega zoom y navegacion a NavigationController.

        Guard load-bearing (RESEARCH Pitfall 2): si el processor tiene preview activo,
        Space/Backspace van a accept/revert ANTES de delegar a navigation.
        """
        key = event.key()

        # Teclas de zoom (delegadas al NavigationController)
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.navigation.adjust_zoom(10)
            event.accept()
            return
        elif key == Qt.Key.Key_Minus:
            self.navigation.adjust_zoom(-10)
            event.accept()
            return
        elif key == Qt.Key.Key_0:
            self.navigation.set_zoom_level(100)
            event.accept()
            return

        # Guard load-bearing: si processor tiene preview activo, Space/Backspace van a accept/revert.
        if self.processor.is_preview_active():
            if key == Qt.Key.Key_Space:
                self.processor.accept_preview()
                event.accept()
                return
            if key == Qt.Key.Key_Backspace:
                self.processor.revert_preview()
                event.accept()
                return

        # Caso normal: delega a navigation
        if key == Qt.Key.Key_Space:
            self.navigation.request_next()
            event.accept()
            return
        if key == Qt.Key.Key_Backspace:
            self.navigation.request_previous()
            event.accept()
            return

        super().keyPressEvent(event)

    # API publica (contrato con gui/controller.py:321 — PRESERVAR)
    def get_approved(self) -> bool:
        """Retorna si el usuario aprobo continuar con el proceso."""
        return self.user_approved

    def get_output_folder(self) -> Path:
        """Retorna la carpeta de salida donde se guardaron las imagenes procesadas."""
        return self.navigation.output_folder

    def has_processed_images(self) -> bool:
        """Retorna True si se proceso al menos una imagen."""
        return len(self.navigation.processed_images) > 0


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
