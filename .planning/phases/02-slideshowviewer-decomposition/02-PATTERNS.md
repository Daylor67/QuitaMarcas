# Phase 2: SlideshowViewer Decomposition - Pattern Map

**Mapped:** 2026-05-26
**Files analyzed:** 5 (1 package init + 3 new components + 1 modified composer)
**Analogs found:** 5 / 5

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `WatermarkRemove/ui/components/__init__.py` | package-init | barrel-export | `WatermarkRemove/services/__init__.py` | exact (singleton/barrel export pattern) |
| `WatermarkRemove/ui/components/navigation_controller.py` | component (QWidget) | state-source + event-driven | `WatermarkRemove/ui/image_viewer.py` + original `SlideshowViewer` (extraction) | role-match (QWidget+folder+navigation) |
| `WatermarkRemove/ui/components/watermark_processor.py` | component (QWidget) | request-response (signal-mediated) | original `SlideshowViewer` manual/auto methods (extraction) + `WatermarkRemove/ui/watermark_tab.py` | partial (signal contract is new; logic is copy-extract) |
| `WatermarkRemove/ui/components/training_data_collector.py` | component (QWidget) wrapping service | event-driven (slot reactor) | `WatermarkRemove/services/wm_persistence.py` (wrap pattern) + original `_update_counts_label` | role-match (thin UI wrap over module functions) |
| `WatermarkRemove/ui/slideshow_viewer.py` (modified) | composer (QDialog) | signal-router | itself (original) + `WatermarkRemove/ui/image_viewer.py` (QDialog skeleton) | exact (preserves public API, becomes thin composer) |

## Pattern Assignments

### `WatermarkRemove/ui/components/__init__.py` (package-init, barrel-export)

**Analog:** `WatermarkRemove/services/__init__.py`

**Imports/exports pattern** (full file, lines 1-5):
```python
from .wm_persistence import WmPersistenceService

wm_persistence = WmPersistenceService()

__all__ = ['wm_persistence', 'WmPersistenceService']
```

**Apply to new file:** Mirror exactly the barrel-export style — one `from .module import Class` per line, then `__all__` with explicit names. NO singleton instance creation (these are widgets that the composer instantiates per-dialog, not module-level singletons like `wm_persistence`).

**Recommended content for new file:**
```python
"""WatermarkRemove.ui.components - Componentes extraidos del SlideshowViewer.

Cada componente es un QWidget con responsabilidad unica, que se comunica con
el composer (SlideshowViewer) y sus hermanos via Signal/Slot.
"""
from .navigation_controller import NavigationController
from .watermark_processor import WatermarkProcessor
from .training_data_collector import TrainingDataCollector

__all__ = ['NavigationController', 'WatermarkProcessor', 'TrainingDataCollector']
```

---

### `WatermarkRemove/ui/components/navigation_controller.py` (QWidget, state-source + event-driven)

**Primary analog (structure):** `WatermarkRemove/ui/image_viewer.py`
**Secondary analog (extracted logic):** `WatermarkRemove/ui/slideshow_viewer.py` (methods being moved)

**Module header + imports pattern** (from `image_viewer.py` lines 1-20):
```python
"""
Visor de imágenes para mostrar todas las imágenes de una carpeta
"""
import os
import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QWidget, QGridLayout, QApplication
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from natsort import natsorted
# Agregar el directorio raíz al path
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
```

**Note for new component:** `current_dir` here must be adjusted — `WatermarkRemove/ui/components/` is two levels deep under the package root; the original `slideshow_viewer.py` uses `current_dir = os.path.dirname(__file__)` and then `wm_dir = os.path.dirname(current_dir)` to reach `WatermarkRemove/`. From `components/` the equivalent is `wm_dir = os.path.dirname(os.path.dirname(__file__))`. **Document this difference verbatim in the new file** (RESEARCH.md Pitfall 3 — defensive guards must be copied with their reason).

**SUPPORTED_FORMATS constant pattern** (from `image_viewer.py` line 26, also identical in `slideshow_viewer.py` line 53):
```python
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tga', '.psd', '.psb', '.jfif')
```
Copy verbatim — already a project-wide convention.

**Constructor + folder-path normalization pattern** (from `image_viewer.py` lines 29-37):
```python
def __init__(self, folder_path: str, parent=None):
    super().__init__(parent)
    self.folder_path = Path(folder_path) if folder_path else None
    self.image_labels = []

    self._setup_ui()
    if self.folder_path and self.folder_path.exists():
        self._load_images()
```
**Apply to NavigationController:** Same pattern (defensive `Path(...)` cast on possibly-None argument; `_setup_ui` then `_load_images`).

**Signal declaration pattern** (from `slideshow_viewer.py` line 51 — already lives in the composer, must be re-applied per-component):
```python
review_completed = Signal(bool)  # True = continuar, False = cancelar
```
**Apply to NavigationController:** Declare class-level signals with inline comment describing payload semantics:
```python
image_changed = Signal(int, object, object)   # (index, Path, np.ndarray)
output_folder_ready = Signal(object)           # Path
processing_blocked_request = Signal(bool)      # opcional - relayed from processor
```

**Image-list loading pattern** (from `slideshow_viewer.py` lines 566-580 — copy verbatim into NavigationController):
```python
def _load_image_list(self):
    """Carga la lista de archivos de imagen"""
    if not self.folder_path or not self.folder_path.exists():
        return

    # Si es un archivo, usar su directorio padre
    if self.folder_path.is_file():
        self.folder_path = self.folder_path.parent

    # Buscar todas las imágenes y ordenarlas
    for file in natsorted(self.folder_path.iterdir()):
        if file.is_file() and file.suffix.lower() in self.SUPPORTED_FORMATS:
            self.image_files.append(file)

    self._update_counter()
```

**working_image load + QPixmap conversion pattern** (from `slideshow_viewer.py` lines 726-746 — copy into NavigationController):
```python
def _show_current_image(self):
    if not self.image_files or self.current_index >= len(self.image_files):
        return

    current_file = self.image_files[self.current_index]

    # Cargar working_image SOLO si no existe (primera vez en esta imagen)
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
```
**Note:** The "load_images_cv2 only if None" guard is load-bearing (preserves state during preview sub-events). Do not "simplify" it (RESEARCH.md Pitfall 3).

**Output-folder creation pattern** (from `slideshow_viewer.py` lines 554-564 — copy verbatim):
```python
def _create_output_folder(self):
    """Crea la carpeta de salida para las imágenes procesadas"""
    if not self.folder_path:
        return

    # Nombre de la carpeta: "{nombre_original} [sin marca]"
    folder_name = self.folder_path.name + " [sin marca]"
    self.output_folder = self.folder_path.parent / folder_name

    # Crear la carpeta si no existe
    self.output_folder.mkdir(exist_ok=True)
```

**Save-as-is pattern** (from `slideshow_viewer.py` lines 1153-1176 — preserve verbatim including the `_log` calls. RESEARCH Assumption A5 confirms this is **intentional behavior**, not a bug):
```python
def _save_current_image_as_is(self):
    """Guarda la imagen actual sin modificaciones (cuando no se removió ninguna marca)"""
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
```

**Error-handling pattern (consistent throughout codebase):**
```python
try:
    # operation
    self._log(f"✅ Success message")
except Exception as e:
    self._log(f"❌ Error message: {e}")
```
Use `self._log()` (mirror of `slideshow_viewer.py` line 141-149) which falls back to `print` when `watermark_tab` is None — pattern proven in original.

**`_log` helper pattern** (from `slideshow_viewer.py` lines 141-149):
```python
def _log(self, message: str):
    """
    Registra un mensaje en la consola de proceso del watermark_tab.
    Si no hay watermark_tab disponible, usa print como fallback.
    """
    if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
        self.watermark_tab.log(message)
    else:
        print(message)
```
**Apply to each component:** Each extracted QWidget receives `watermark_tab` in `__init__` (or via slot) and exposes its own `_log()` with the same fallback.

---

### `WatermarkRemove/ui/components/watermark_processor.py` (QWidget, request-response via signals)

**Primary analog (extracted logic):** `WatermarkRemove/ui/slideshow_viewer.py` lines 1178-1886 (manual + auto YOLO + position-grid handlers)
**Secondary analog (QWidget shape):** `WatermarkRemove/ui/watermark_tab.py` (clean small QWidget with `_setup_ui`)

**Imports pattern (FOR THE NEW FILE — extracted from `slideshow_viewer.py` lines 22-28):**
```python
from utils import UtilJson
from WatermarkRemove.services import wm_persistence
import numpy as np
from natsort import natsorted
from WatermarkRemove import align_watermark, remove_watermark
from WatermarkRemove.wm_remove import load_images_cv2, guardar, find_wm, quick_align_preview
from WatermarkRemove.yolo.auto_detector import detect_watermarks, resolve_png_for_class
```

**Manual mode accept (atomic event) pattern** (from `slideshow_viewer.py` lines 1511-1589 — copy core logic, replace direct UI mutation with signal emission):
```python
def _accept_preview(self):
    """Acepta el preview y guarda los cambios. Sistema de eventos atómicos."""
    if not self.is_preview_active or self.preview_image is None:
        return
    try:
        current_file = self.image_files[self.current_index]
        if not self.output_folder:
            self._create_output_folder()

        # Pasada final con filtro JPEG (los previews en vivo lo saltean por velocidad)
        best_x, best_y = self.current_event_position
        self.working_image = remove_watermark(
            self.base_image_for_preview,
            self.current_event_watermark,
            best_x + self.offset_x_adj.value(),
            best_y + self.offset_y_adj.value(),
            alpha_adjust=self.alpha_adjust.value(),
            apply_jpeg_filter=True,
        )
        guardar(current_file, self.working_image, self.output_folder)
        self.processed_images.add(self.current_index)

        # Recopilar dato de entrenamiento YOLO (no debe interrumpir la remoción si falla)
        try:
            from WatermarkRemove.yolo.training_collector import save_training_sample
            # ...
        except Exception as collect_err:
            self._log(f"⚠️ No se pudo guardar dato de entrenamiento: {collect_err}")
```
**After extraction:** Replace the direct `save_training_sample` call with `self.image_processed.emit(current_file, self.working_image, best_x, best_y, watermark, wm_path, wm_folder_name, base_image)` so `TrainingDataCollector` reacts via slot (decouples).

**Atomic-event state-machine pattern** (from `slideshow_viewer.py` lines 1419-1509 — pertinent excerpts):
```python
def _remove_watermark_preview(self):
    """Crea un preview removiendo la marca de agua en la posición del cursor. Sistema de eventos atómicos."""
    # Si ya hay un evento activo, IGNORAR (un evento = un solo click)
    if self.is_preview_active:
        self._log("⚠️ Ya hay un evento activo. Acepta o revierte primero.")
        return
    # ...
    # Bloquear UI
    self.next_btn.setEnabled(False)
    self.prev_btn.setEnabled(False)
    self.watermark_combo.setEnabled(False)
```
**After extraction:** UI bloqueo via `self.processing_blocked.emit(True)` (NavigationController's slot disables prev/next/combo). The `self.watermark_combo.setEnabled(False)` stays internal to the processor since the combo is owned by the processor (per RESEARCH Component Responsibilities table).

**Live preview computation pattern** (from `slideshow_viewer.py` lines 1402-1417 — copy verbatim):
```python
def _compute_live_preview(self, x, y, alpha):
    """Preview en vivo: vectorizado si el toggle está activo, sino remove_watermark sin filtro."""
    if self.quick_preview_checkbox.isChecked():
        return quick_align_preview(
            self.base_image_for_preview,
            self.current_event_watermark,
            x, y,
            alpha_adjust=alpha,
        )
    return remove_watermark(
        self.base_image_for_preview,
        self.current_event_watermark,
        x, y,
        alpha_adjust=alpha,
        apply_jpeg_filter=False,
    )
```

**YOLO auto-detection pattern** (from `slideshow_viewer.py` lines 1691-1752 — copy verbatim):
```python
def _run_auto_detection(self):
    """Corre YOLO sobre la imagen actual y arma la lista de detecciones."""
    if self.working_image is None:
        return
    try:
        detections = detect_watermarks(self.working_image)
    except FileNotFoundError as e:
        self._log(f"❌ {e}")
        QMessageBox.warning(self, "Modelo no encontrado", str(e))
        return
    # ... see lines 1706-1752 for refinement loop with find_wm
```

**Watermark folder combo + `blockSignals` defensive pattern** (from `slideshow_viewer.py` lines 582-616):
```python
def _load_watermark_folders(self):
    """Carga las carpetas disponibles en WatermarkRemove/marcas"""
    # Bloquear señales para evitar que se dispare _on_watermark_folder_changed durante la carga
    self.watermark_folder_combo.blockSignals(True)
    self.watermark_folder_combo.clear()
    # ... (load folders)
    # Restaurar señales
    self.watermark_folder_combo.blockSignals(False)
    # Disparar manualmente para inicializar el estado
    self._on_watermark_folder_changed(self.watermark_folder_combo.currentIndex())
```
**Critical:** Preserve the `blockSignals(True)` / `blockSignals(False)` bracket and the manual fire at the end. RESEARCH Pitfall 3 (line 293-298) flags this as load-bearing.

**`hasattr` defensive guard pattern** (from `slideshow_viewer.py` lines 681-686):
```python
def _on_watermark_changed(self, index):
    if index >= 0:
        # alpha_adjust puede no existir aún si se llama durante la construcción del panel
        if hasattr(self, 'alpha_adjust'):
            saved_alpha = self.watermark_alpha_values.get(index, 1.0)
            self.alpha_adjust.blockSignals(True)
            self.alpha_adjust.setValue(saved_alpha)
            self.alpha_adjust.blockSignals(False)
```
**Preserve verbatim.** RESEARCH Pitfall 3 explicitly calls this out (line 294).

**`wm_persistence` usage pattern** (from `slideshow_viewer.py` lines 262-264 and 605-631):
```python
# Leer
saved_crop = wm_persistence.get_last_crop_pixels()
folder_to_select = wm_persistence.get_last_watermark_folder()

# Escribir
wm_persistence.set_last_crop_pixels(value)
wm_persistence.set_last_watermark_folder(folder_name)
```
Singleton — import once, use anywhere. No instance to manage.

---

### `WatermarkRemove/ui/components/training_data_collector.py` (QWidget wrap, event-driven)

**Primary analog (wrap pattern):** `WatermarkRemove/services/wm_persistence.py` (service wrap with domain methods)
**Secondary analog (extracted UI):** `WatermarkRemove/ui/slideshow_viewer.py` lines 115-139 (`_update_counts_label`) + lines 479-493 (`conteo_group` UI block)

**Service-wrap pattern** (from `wm_persistence.py` lines 11-39):
```python
class WmPersistenceService:
    """Servicio de persistencia de estado UI del módulo WatermarkRemove.

    Wrappea UtilJson con nombres de dominio para desacoplar slideshow_viewer
    de la implementación concreta de persistencia JSON.

    El servicio NO cachea datos en memoria — cada llamada crea una instancia
    de UtilJson y lee/escribe el archivo, consistente con el patrón original.
    """

    def __init__(self):
        self._path = os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')

    def get_last_crop_pixels(self) -> int:
        """Retorna el último valor de crop pixels. Default: 0."""
        return UtilJson(self._path).get('last_crop_pixels', 0) or 0
```
**Apply to `TrainingDataCollector`:** Mirror the docstring style and "domain-name wrapper" idea — public methods like `on_image_processed(...)` and `on_image_reset(...)` are domain slots wrapping `save_training_sample` and `remove_training_sample` from `yolo/training_collector.py`. The component does NOT modify the underlying module (`yolo/training_collector.py` is NO TOCAR per RESEARCH line 228).

**UI conteo group pattern** (from `slideshow_viewer.py` lines 479-493 — copy verbatim into `_setup_ui`):
```python
# Conteo de datos de entrenamiento recopilados
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
```

**Counts-label refresh pattern** (from `slideshow_viewer.py` lines 115-139 — copy verbatim):
```python
def _update_counts_label(self):
    """Lee training_data.json y actualiza el conteo de muestras por clase."""
    import json as _json

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
```
**Note:** `current_dir` needs adjustment when moved into `components/` (RESEARCH Pitfall 4, line 300-304). Document the change explicitly in the new file.

**save_training_sample call pattern** (from `slideshow_viewer.py` lines 1538-1554 — wrap inside slot, NOT inline):
```python
def on_image_processed(self, image_file, working_image, x, y, watermark_array,
                       watermark_path, watermark_folder_name, base_image):
    """Slot: el procesador terminó una remoción. Guardar sample y refrescar conteo."""
    try:
        # Import al top del archivo (per RESEARCH Pitfall 4 line 304 — documentar decisión)
        training_json = Path(os.path.dirname(os.path.dirname(__file__))) / 'training_data.json'
        save_training_sample(
            image_path=image_file,
            watermark_path=watermark_path,
            watermark_folder=watermark_folder_name,
            x=x, y=y,
            watermark_array=watermark_array,
            image_array=base_image,
            output_json=training_json,
        )
    except Exception as collect_err:
        self._log(f"⚠️ No se pudo guardar dato de entrenamiento: {collect_err}")
    finally:
        self._update_counts_label()
```

**remove_training_sample call pattern** (from `slideshow_viewer.py` lines 1661-1663):
```python
from WatermarkRemove.yolo.training_collector import remove_training_sample
remove_training_sample(current_dir, current_file, self._log)
```
**Note:** Original uses local import; new file can promote to top-level (documented decision per Pitfall 4).

---

### `WatermarkRemove/ui/slideshow_viewer.py` (modified — composer, signal-router)

**Analog:** itself (preserves public surface) + `WatermarkRemove/ui/image_viewer.py` (thin QDialog skeleton)

**QDialog skeleton pattern** (from `image_viewer.py` lines 21-46):
```python
class ImageViewer(QDialog):
    SUPPORTED_FORMATS = ('.png', '.jpg', ...)
    THUMBNAIL_SIZE = 200

    def __init__(self, folder_path: str, parent=None):
        super().__init__(parent)
        self.folder_path = Path(folder_path) if folder_path else None
        # ...
        self._setup_ui()
        if self.folder_path and self.folder_path.exists():
            self._load_images()

    def _setup_ui(self):
        self.setWindowTitle("Visor de Imágenes")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        main_layout = QVBoxLayout(self)
```
**Apply to refactored composer:** Replace the 2041-line monolith with a thin shell that instantiates the 3 components and wires their signals.

**Preserved public API (must NOT change — `gui/controller.py:321` contract)** — from `slideshow_viewer.py`:
- Line 30 — class declaration: `class SlideshowViewer(QDialog):`
- Line 51 — signal: `review_completed = Signal(bool)`
- Line 55 — constructor: `def __init__(self, folder_path: str, parent=None, watermark_tab=None):`
- Lines 2008-2018 — public methods:
  ```python
  def get_approved(self) -> bool:
      return self.user_approved

  def get_output_folder(self) -> Path:
      return self.output_folder  # NOTE: will become self.navigation.output_folder

  def has_processed_images(self) -> bool:
      return len(self.processed_images) > 0  # NOTE: will become len(self.navigation.processed_images) > 0
  ```

**External call site** (from `gui/controller.py` lines 320-335 — verify after refactor that this still works without modification):
```python
viewer = SlideshowViewer(input_path, MainWindow, watermark_tab=watermark_tab)
viewer.exec()
if not viewer.get_approved():
    return
if viewer.has_processed_images():
    output_folder = viewer.get_output_folder()
    if output_folder and output_folder.exists():
        MainWindow.inputField.setText(str(output_folder))
```
**Constraint:** All four entry points (constructor + `exec()` + `get_approved()` + `has_processed_images()` + `get_output_folder()`) must work without changes to `gui/controller.py`.

**keyPressEvent delegation pattern** (from `slideshow_viewer.py` lines 1968-2006 — preserve guard logic verbatim, delegate to child slots):
```python
def keyPressEvent(self, event: QKeyEvent):
    key = event.key()

    # Teclas de zoom
    if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
        self._set_zoom(self.zoom_level + 10); event.accept(); return
    # ...
    # Navegación normal
    check_opc_avanzadas = self.opciones_avanzadas.isChecked()
    if key == Qt.Key.Key_Space:
        if check_opc_avanzadas and self.is_preview_active:
            self._accept_preview()
        else:
            self._next_image()
    elif key == Qt.Key.Key_Backspace:
        if check_opc_avanzadas and self.is_preview_active:
            self._revert_preview()
        else:
            self._previous_image()
```
**Refactored equivalent (per RESEARCH Pitfall 1 + Example 2 lines 434-447):**
```python
def keyPressEvent(self, event: QKeyEvent):
    key = event.key()
    # Si hay preview activo en processor, Space/Backspace van a accept/revert
    if self.processor.is_preview_active():
        if key == Qt.Key.Key_Space:
            self.processor.accept_preview(); return
        if key == Qt.Key.Key_Backspace:
            self.processor.revert_preview(); return
    # Caso normal: navegación
    if key == Qt.Key.Key_Space:
        self.navigation.request_next(); return
    if key == Qt.Key.Key_Backspace:
        self.navigation.request_previous(); return
    super().keyPressEvent(event)
```
**Critical:** The guard `if self.processor.is_preview_active()` MUST be checked BEFORE navigation. Order matters — RESEARCH Pitfall 2 (lines 283-291).

**wheelEvent zoom pattern** (from `slideshow_viewer.py` lines 1955-1966 — composer keeps it, delegates to NavigationController):
```python
def wheelEvent(self, event: QWheelEvent):
    if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
        delta = event.angleDelta().y()
        zoom_change = 10 if delta > 0 else -10
        new_zoom = self.zoom_level + zoom_change
        self._set_zoom(new_zoom)
        event.accept()
    else:
        super().wheelEvent(event)
```
**Refactored:** delegate to `self.navigation.adjust_zoom(zoom_change)` since zoom state lives in NavigationController.

**Layout pattern (preserve outer structure)** (from `slideshow_viewer.py` lines 151-168):
```python
def _setup_ui(self):
    self.setWindowTitle("Revisión de Imágenes")
    self.setModal(True)
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
    main_layout.addWidget(right_panel, 1)
```
**Refactored composer:** replace `_create_controls_panel()` (currently builds 280px panel with 5+ groupboxes) by stacking the `processor` and `collector` widgets in a left QVBoxLayout, and `navigation` in the right. RESEARCH Assumption A4 (line 498) says **do NOT rebalance the layout** in Phase 2 — keep `controls_panel_width = 280` hardcoded.

---

## Shared Patterns

### Pattern: `_log` helper with watermark_tab fallback
**Source:** `WatermarkRemove/ui/slideshow_viewer.py` lines 141-149
**Apply to:** All three new components (each gets `watermark_tab` parameter via composer)
```python
def _log(self, message: str):
    if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
        self.watermark_tab.log(message)
    else:
        print(message)
```
**Constructor sig:** `def __init__(self, ..., parent=None, watermark_tab=None)` — composer passes `watermark_tab` down to each child.

### Pattern: Error handling with logged emoji prefix
**Source:** consistent throughout `WatermarkRemove/ui/slideshow_viewer.py` (lines 723, 932, 1045, 1175-1176, 1257-1258, 1382-1383, 1399-1400, 1506-1509, 1588-1589, 1666-1668, 1697-1704, 1717-1718, 1736-1737, 1865-1867)
**Apply to:** All extracted methods that contain external I/O or numpy/cv2 calls
```python
try:
    # operation
    self._log(f"✅ Success message")
except Exception as e:
    self._log(f"❌ Error: {e}")
```
**Emoji legend (proven across codebase):**
- `✅` success
- `❌` error
- `⚠️` warning / non-fatal
- `🔍` debug / search
- `💾` save
- `↩️` revert
- `↺` reset
- `✂️` crop
- `🤖` YOLO / automatic
- `🧹` cleanup

### Pattern: Signal vs direct slot call decision
**Source:** RESEARCH.md lines 198-207 + `slideshow_viewer.py` line 51
**Rule:**
- **Use Signal** for "something changed in me" notifications (`image_changed`, `preview_changed`, `image_processed`, `processing_blocked`)
- **Use direct slot call** when the composer (parent) invokes a public method on a child (`self.navigation.next_image()` from `keyPressEvent`)
- **NEVER** sibling-to-sibling direct calls — always through composer-wired signals

### Pattern: Singleton service usage
**Source:** `WatermarkRemove/services/__init__.py` line 3 + `slideshow_viewer.py` line 23
**Apply to:** Any component that needs `wm_persistence`
```python
from WatermarkRemove.services import wm_persistence  # module-level singleton

# Read
value = wm_persistence.get_last_crop_pixels()
# Write
wm_persistence.set_last_crop_pixels(new_value)
```
No instantiation, no DI, no caching layer — copy the pattern verbatim.

### Pattern: `current_dir` path resolution
**Source:** `slideshow_viewer.py` lines 17-20
```python
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
```
**Apply to new files in `components/`:** The depth changes — `components/` is one level deeper. The line `wm_dir = os.path.dirname(current_dir)` (used in original to reach `WatermarkRemove/`) becomes `wm_dir = os.path.dirname(os.path.dirname(__file__))`. **Verify each usage of `current_dir` when extracting** — particularly the `training_data.json` path resolution (slideshow_viewer.py lines 119, 1542, 1855) and `wm_positions.json` path (line 702) and `marcas` folder path (line 589).

### Pattern: Defensive `blockSignals` bracket
**Source:** `slideshow_viewer.py` lines 585-616, 659-669, 684-686, 1474-1479, 1756-1764, 1774-1779
**Apply to:** Any combo/spinbox population during state restoration or before manual trigger
```python
widget.blockSignals(True)
# ... populate ...
widget.blockSignals(False)
# Optionally fire the slot manually if needed
self._on_widget_changed(widget.currentIndex())
```
RESEARCH Pitfall 3 (lines 293-298) marks this as load-bearing — never strip during refactor.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All five target files have analogs in the codebase. The new files are either direct extractions from `slideshow_viewer.py` (logic moves verbatim) or follow established service/widget patterns from `wm_persistence`/`image_viewer`/`watermark_tab`. |

## Metadata

**Analog search scope:**
- `WatermarkRemove/ui/*.py` (4 files — `image_viewer.py`, `position_editor.py`, `slideshow_viewer.py`, `watermark_tab.py`)
- `WatermarkRemove/services/*.py` (2 files — `__init__.py`, `wm_persistence.py`)
- `WatermarkRemove/yolo/training_collector.py` (wrapped target)
- `gui/controller.py` lines 315-340 (caller contract verification)

**Files scanned:** 8 source files + 1 RESEARCH.md (649 lines)

**Lines of code reviewed in analogs:**
- `slideshow_viewer.py`: ~2040 lines (full file, the source of all extractions)
- `image_viewer.py`: 249 lines (full file)
- `wm_persistence.py`: 39 lines (full file)
- `services/__init__.py`: 5 lines (full file)
- `training_collector.py`: 141 lines (full file)
- `watermark_tab.py`: 264 lines (full file)
- `ui/__init__.py`: 13 lines (full file)
- `controller.py`: 25 lines (range 315-340)

**Pattern extraction date:** 2026-05-26

**Confidence:** HIGH — all five target files have one or more direct analogs in the codebase; the dominant pattern (extract code from monolith, wire via signals) is mechanical and well-documented in RESEARCH.md.
