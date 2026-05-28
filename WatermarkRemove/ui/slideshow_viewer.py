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
    QGroupBox, QMessageBox, QSplitter,
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
from WatermarkRemove.services import wm_persistence


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
        # Re-emitir estado inicial: NavigationController emitio image_changed en su __init__
        # ANTES de que _wire_signals() conectara el slot del processor, asi que el processor
        # nunca recibio la imagen inicial — _working_image quedaria None para siempre.
        self._sync_initial_state()
        self._setup_ui()

    def _sync_initial_state(self):
        """Re-emite el estado inicial de navigation hacia processor/collector.

        NavigationController emite image_changed en su __init__ (via _show_current_image),
        pero en ese momento _wire_signals() aun no corrio — ningun slot estaba conectado.
        Esto deja processor._working_image = None, rompiendo overlays, modo manual y auto YOLO.
        """
        if not self.navigation.image_files:
            return
        current_file = self.navigation.image_files[self.navigation.current_index]
        self.navigation.image_changed.emit(
            self.navigation.current_index,
            current_file,
            self.navigation.working_image,
        )
        if self.navigation.output_folder is not None:
            self.navigation.output_folder_ready.emit(self.navigation.output_folder)

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
        """Layout principal: QSplitter horizontal (65% visor / 35% controles).

        Reemplaza el QHBoxLayout con ancho fijo de 280 px (Phase 4 — D-01, D-02).
        La proporcion inicial es [315, 585] (35%/65% de 900 px iniciales).
        """
        self.setWindowTitle("Revisión de Imágenes")
        self.setModal(True)
        self.resize(900, 650)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.addWidget(self._create_controls_panel())
        self._splitter.addWidget(self.navigation)
        self._splitter.setSizes(wm_persistence.get_splitter_sizes([315, 585]))
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        outer.addWidget(self._splitter)

    def _on_navigation_resize_requested(self, width: int, height: int):
        """Slot: NavigationController solicita resize. Mantiene altura actual y ajusta ancho."""
        self.resize(width, self.height())

    def _create_controls_panel(self) -> QWidget:
        """Panel de controles (izquierda del splitter): WatermarkProcessor +
        grupo Navegacion (finish/cancel) + TrainingDataCollector.

        Sin scroll wrapper (D-03) y sin ancho fijo (D-01 — el splitter lo controla).
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 6, 0)

        # === 1. WatermarkProcessor (sus GroupBoxes "Seleccion" + "Auto") ===
        layout.addWidget(self.processor)

        # === 2. Grupo Navegacion (finish + cancel) ===
        nav_group = QGroupBox("Navegación")
        nav_action_layout = QHBoxLayout(nav_group)
        nav_action_layout.setSpacing(5)

        self.finish_btn = QPushButton("Finalizar y Procesar")
        self.finish_btn.clicked.connect(self._finish_review)
        self.finish_btn.setMaximumHeight(40)
        nav_action_layout.addWidget(self.finish_btn)

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.clicked.connect(self._cancel_review)
        self.cancel_btn.setMaximumHeight(40)
        nav_action_layout.addWidget(self.cancel_btn)

        layout.addWidget(nav_group)

        # === 3. TrainingDataCollector (su propio GroupBox "Datos recopilados") ===
        layout.addWidget(self.collector)
        layout.addStretch(1)
        return panel

    def _on_splitter_moved(self, pos: int, index: int):
        """Slot: persiste los sizes del splitter al moverlo (D-02)."""
        wm_persistence.set_splitter_sizes(list(self._splitter.sizes()))

    def closeEvent(self, event):
        """Persiste el tamaño del splitter al cerrar el diálogo (D-02)."""
        wm_persistence.set_splitter_sizes(list(self._splitter.sizes()))
        super().closeEvent(event)

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
