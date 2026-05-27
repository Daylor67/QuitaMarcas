"""TrainingDataCollector — UI de conteo + wrappers de save/remove training samples.

Componente que encapsula la recopilacion de datos de entrenamiento YOLO,
extraido verbatim de `SlideshowViewer` (Plan 02-03). Responsabilidades:

- UI propia: GroupBox "📊 Datos recopilados" con un QLabel que muestra el conteo
  de muestras por clase leyendo `training_data.json`.
- Slots para reaccionar a las senales del WatermarkProcessor:
    * `on_image_processed(...)` → invoca `save_training_sample`
    * `on_image_reset(file_path)` → invoca `remove_training_sample`
- Refresca el label tras cada operacion (defensive try/except preservado del
  original — fallback "Sin datos aún" — RESEARCH Pitfall 3).

El modulo externo `WatermarkRemove.yolo.training_collector` NO se modifica
(out-of-scope per RESEARCH line 228); aqui solo se wrappean sus funciones.

NOTA DE PATH (Pitfall 4 + PATTERNS line 648-656):
- En el `slideshow_viewer.py` original `current_dir` era `WatermarkRemove/ui/`
  (un nivel por encima de `WatermarkRemove/`). Aqui `__file__` vive en
  `WatermarkRemove/ui/components/` — un nivel mas profundo. Por eso el path a
  `training_data.json` se calcula como
  `Path(os.path.dirname(os.path.dirname(__file__))) / 'training_data.json'`
  → `WatermarkRemove/training_data.json`, identico al destino original.
- Los imports `save_training_sample` / `remove_training_sample` estaban lazy en
  el original (slideshow_viewer.py lines 1540/1662/1854). Aqui se promueven a
  top-level por consistencia con el resto de componentes.
"""
import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QLabel
from PySide6.QtCore import Signal, Qt

from WatermarkRemove.yolo.training_collector import save_training_sample, remove_training_sample


class TrainingDataCollector(QWidget):
    """Recopila datos de entrenamiento y muestra el conteo de muestras.

    Construido por-dialogo desde `SlideshowViewer.__init__` (sin singletons).
    Reacciona a las senales `image_processed` / `image_reset` del processor.
    """

    # Senal opcional emitida tras refrescar el label (para depuracion/tests).
    counts_updated = Signal()

    def __init__(self, parent=None, watermark_tab=None):
        super().__init__(parent)

        # === Estado ===
        self.watermark_tab = watermark_tab  # para _log fallback
        # WatermarkRemove/ (un nivel arriba de components/, dos arriba de __file__)
        wm_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._training_json: Path = Path(wm_dir) / 'training_data.json'

        # === UI propia ===
        self._setup_ui()

    # ===================================================================
    # UI
    # ===================================================================
    def _setup_ui(self):
        """Construye el GroupBox de conteo (verbatim del original lines 480-493)."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

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

        main_layout.addWidget(conteo_group)

        # Refresco inicial (replica linea 493 del original)
        self._update_counts_label()

    # ===================================================================
    # Logging (replica patron 141-149 del slideshow_viewer.py original)
    # ===================================================================
    def _log(self, message: str):
        """Registra un mensaje en watermark_tab.log o fallback a print."""
        if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
            self.watermark_tab.log(message)
        else:
            print(message)

    # ===================================================================
    # Refresh del conteo (extraido verbatim del original lines 115-139)
    # ===================================================================
    def _update_counts_label(self):
        """Lee training_data.json y actualiza el conteo de muestras por clase.

        Defensive try/except preservado verbatim del original; ante cualquier
        problema (archivo ausente, corrupto, no-lista) cae a "Sin datos aún".
        """
        import json as _json

        training_json = self._training_json
        try:
            if not training_json.exists():
                self.training_counts_label.setText("Sin datos aún")
                self.counts_updated.emit()
                return
            data = _json.loads(training_json.read_text(encoding='utf-8'))
            if not data:
                self.training_counts_label.setText("Sin datos aún")
                self.counts_updated.emit()
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
        finally:
            self.counts_updated.emit()

    # ===================================================================
    # Slots — wiring desde el processor (Plan 03)
    # ===================================================================
    def on_image_processed(
        self,
        file_path,
        working_image,
        x: int,
        y: int,
        watermark_array,
        watermark_path,
        watermark_folder_name: str,
        base_image,
    ):
        """Slot: el processor acepto una remocion → guarda dato de entrenamiento.

        Replica el bloque try/except del original (slideshow_viewer.py 1538-1554).
        Si `watermark_path` es None (caso crop o auto-detect sin PNG, original
        line 1842) NO se guarda nada — el collector ignora la muestra.
        """
        try:
            if watermark_path is None:
                return
            save_training_sample(
                image_path=file_path,
                watermark_path=watermark_path,
                watermark_folder=watermark_folder_name,
                x=x,
                y=y,
                watermark_array=watermark_array,
                image_array=base_image,
                output_json=self._training_json,
            )
        except Exception as collect_err:
            self._log(f"⚠️ No se pudo guardar dato de entrenamiento: {collect_err}")
        finally:
            self._update_counts_label()

    def on_image_reset(self, file_path):
        """Slot: el processor reseteo una imagen → limpia sus training samples.

        Replica la logica del original (slideshow_viewer.py lines 1661-1668).

        NOTA CRITICA: `remove_training_sample(current_dir, current_file, log)`
        construye internamente `Path(os.path.dirname(current_dir)) / 'training_data.json'`.
        En el original `current_dir` era `WatermarkRemove/ui/`, por lo que
        `dirname()` apuntaba a `WatermarkRemove/`. Para preservar el comportamiento
        sin modificar `yolo/training_collector.py` (out-of-scope), construimos
        `fake_current_dir = <WatermarkRemove>/ui` para que `dirname()` retorne
        `WatermarkRemove/` — el mismo destino que `self._training_json`.
        """
        try:
            wm_dir_str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # WatermarkRemove/
            fake_current_dir = os.path.join(wm_dir_str, 'ui')
            remove_training_sample(fake_current_dir, Path(file_path), self._log)
        except Exception as e:
            self._log(f"⚠️ Error en remove_training_sample: {e}")
        finally:
            self._update_counts_label()

    def on_counts_changed(self):
        """Slot: el processor pidio refrescar conteos (signal counts_changed)."""
        self._update_counts_label()
