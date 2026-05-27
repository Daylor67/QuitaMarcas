"""
Visor de imagenes tipo slideshow - Navega con Space y Backspace

Tras Phase 2 (Plan 02-01 + Plan 02-02), `SlideshowViewer` es un composer adelgazado:
solo instancia los componentes hijos (NavigationController + WatermarkProcessor +
TrainingDataCollector), wire sus signals, y conserva el contrato externo:

- Constructor `(folder_path: str, parent=None, watermark_tab=None)`
- Signal `review_completed = Signal(bool)`
- Metodos publicos `get_approved`, `get_output_folder`, `has_processed_images`

Toda la logica de procesamiento (manual mode, auto YOLO, position-grid, crop, alpha/offset
spinboxes) vive en `WatermarkProcessor`. Toda la navegacion + render + zoom + counter
viven en `NavigationController`. El conteo de training data (Plan 03) vivira en
`TrainingDataCollector` — todavia stub mientras se ejecuta esa fase.

Conservados aqui:
- `_update_counts_label` (todavia inline, migra en Plan 03)
- `_finish_review` / `_cancel_review` (acciones del QDialog)
- `keyPressEvent` con guard load-bearing: si processor tiene preview activo,
  Space/Backspace van a accept/revert; sino, delegan a navigation
- `_on_navigation_resize_requested` (slot que ejecuta el resize del QDialog)
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QWidget,
    QScrollArea, QGroupBox, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent

# Agregar el directorio raiz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from WatermarkRemove.ui.components import (
    NavigationController, WatermarkProcessor, TrainingDataCollector,
)


class SlideshowViewer(QDialog):
    """
    Visor de imagenes estilo slideshow con navegacion por teclado y procesamiento de marcas.

    Es un composer puro tras Phase 2: instancia componentes hijos, conecta sus signals,
    expone API publica estable (contrato con `gui/controller.py:321`).

    Controles de navegacion:
        - Space: Siguiente imagen (o Accept preview si manual mode activo)
        - Backspace: Imagen anterior (o Revert preview si manual mode activo)
        - Enter: Finalizar revision
        - Escape: Cancelar proceso

    Controles de zoom (delegados a NavigationController):
        - Ctrl + Rueda: Zoom in/out
        - Plus/Minus: Zoom in/out
        - 0: Reset zoom al 100%
    """

    # Senal preservada — consumida por gui/controller.py:321
    review_completed = Signal(bool)  # True = continuar, False = cancelar

    def __init__(self, folder_path: str, parent=None, watermark_tab=None):
        super().__init__(parent)

        # === Estado del composer ===
        self.user_approved = False
        self.watermark_tab = watermark_tab
        self.controls_panel_width = 280

        # === Instanciar componentes hijos ===
        self.navigation = NavigationController(folder_path, parent=self, watermark_tab=watermark_tab)
        self.processor = WatermarkProcessor(parent=self, watermark_tab=watermark_tab)
        self.collector = TrainingDataCollector(parent=self, watermark_tab=watermark_tab)

        # === Wire signals ANTES de _setup_ui (para que callbacks iniciales del processor
        # tengan al composer correctamente cableado).
        self._wire_signals()

        # === Construir UI propia ===
        self._setup_ui()

    # ===================================================================
    # Signal wiring entre componentes
    # ===================================================================
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

        # --- Wire decorate_pixmap callback (restaura overlays de posiciones y crop) ---
        self.navigation.set_processor_decorator(self.processor.decorate_pixmap)

        # --- Navigation -> composer ---
        self.navigation.window_resize_requested.connect(self._on_navigation_resize_requested)
        self.navigation.finish_requested.connect(self._finish_review)

        # --- Processor -> Collector (Plan 03 wire training data) ---
        # El collector existe como stub; cuando Plan 03 lo implemente, estos slots ya estan listos.
        if hasattr(self.collector, 'on_image_processed'):
            self.processor.image_processed.connect(self.collector.on_image_processed)
        if hasattr(self.collector, 'on_image_reset'):
            self.processor.image_reset.connect(self.collector.on_image_reset)
        if hasattr(self.collector, 'on_counts_changed'):
            self.processor.counts_changed.connect(self.collector.on_counts_changed)

        # --- Procesador "Guardar y Siguiente" debe gatillar request_next ---
        # Replica del patron original (lineas 428-429 del slideshow_viewer.py pre-refactor)
        # donde el boton tenia conectado dos slots: accept + next.
        self.processor.auto_accept_next_btn.clicked.connect(self.navigation.request_next)

    # ===================================================================
    # UI setup (panel izquierdo composer + processor + collector apilados)
    # ===================================================================
    def _setup_ui(self):
        """Configura la interfaz de usuario con layout horizontal."""
        self.setWindowTitle("Revisión de Imágenes")
        self.setModal(True)
        self.resize(900, 650)

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # === PANEL IZQUIERDO: Controles (fijo 280px) ===
        left_panel = self._create_controls_panel()
        main_layout.addWidget(left_panel)

        # === PANEL DERECHO: NavigationController ===
        main_layout.addWidget(self.navigation, 1)

    def _on_navigation_resize_requested(self, width: int, height: int):
        """Slot: NavigationController solicita resize. Mantiene altura actual y ajusta ancho."""
        self.resize(width, self.height())

    def _create_controls_panel(self) -> QWidget:
        """Crea el panel de controles (izquierda) con scroll vertical.

        El panel contiene (top-down):
            1. WatermarkProcessor (con sus GroupBoxes propios: Seleccion + Auto)
            2. Grupo "Navegacion" (finish + cancel buttons — sin prev/next que viven en navigation)
            3. Grupo "Datos recopilados" (conteo — todavia inline hasta Plan 03)
        """
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

        # === 3. Conteo de datos de entrenamiento (todavia inline — migra Plan 03) ===
        conteo_group = QGroupBox("📊 Datos recopilados")
        conteo_layout = QVBoxLayout(conteo_group)
        conteo_layout.setSpacing(4)
        conteo_layout.setContentsMargins(8, 6, 8, 6)

        self.training_counts_label = QLabel("Sin datos aún")
        self.training_counts_label.setStyleSheet(
            "color: #aaaaaa; font-size: 10px; font-family: monospace;"
        )
        self.training_counts_label.setWordWrap(True)
        conteo_layout.addWidget(self.training_counts_label)

        layout.addWidget(conteo_group)
        self._update_counts_label()

        # Refrescar conteos cada vez que el processor emita counts_changed
        self.processor.counts_changed.connect(self._update_counts_label)

        layout.addStretch(1)

        return panel

    def _update_counts_label(self):
        """Lee training_data.json y actualiza el conteo de muestras por clase.

        TODO Plan 03: este metodo migra al TrainingDataCollector.
        """
        import json as _json

        training_json = Path(os.path.dirname(current_dir)) / 'WatermarkRemove' / 'training_data.json'
        # current_dir = WatermarkRemove/ui/ ; queremos WatermarkRemove/training_data.json
        # os.path.dirname(current_dir) = WatermarkRemove/  ya correctamente
        training_json = Path(os.path.dirname(current_dir)) / 'training_data.json'
        try:
            if not training_json.exists():
                self.training_counts_label.setText("Sin datos aún")
                return
            data = _json.loads(training_json.read_text(encoding='utf-8'))
            if not data:
                self.training_counts_label.setText("Sin datos aún")
                return

            counts: dict = {}
            for entry in data:
                cls = entry.get('class_type', '?')
                counts[cls] = counts.get(cls, 0) + 1

            lines = [f"{cls}: {n}" for cls, n in sorted(counts.items())]
            total = sum(counts.values())
            lines.append(f"─────────\nTotal: {total}")
            self.training_counts_label.setText("\n".join(lines))
        except Exception:
            self.training_counts_label.setText("Sin datos aún")

    def _log(self, message: str):
        """Logger del composer — todavia usado por _finish_review/_cancel_review en logs futuros."""
        if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
            self.watermark_tab.log(message)
        else:
            print(message)

    # ===================================================================
    # Acciones del dialogo (finalizar / cancelar)
    # ===================================================================
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

    # ===================================================================
    # keyPressEvent — guard load-bearing: processor preview > navigation
    # ===================================================================
    def keyPressEvent(self, event: QKeyEvent):
        """Maneja eventos de teclado — delega zoom y navegacion a NavigationController.

        Guard load-bearing (RESEARCH Pitfall 2): si hay preview activo en el processor,
        Space/Backspace van a accept/revert. El check `processor.is_preview_active()`
        DEBE ir ANTES de la delegacion a navigation.
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

    # ===================================================================
    # API publica (contrato con gui/controller.py:321 — PRESERVAR)
    # ===================================================================
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
