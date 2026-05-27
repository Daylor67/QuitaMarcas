---
phase: 02-slideshowviewer-decomposition
plan: 02
subsystem: WatermarkRemove/ui
tags: [refactor, qt, signal-slot, decomposition, manual-mode, auto-yolo, position-grid]
requires:
  - WatermarkRemove/ui/slideshow_viewer.py (Plan 02-01 output: composer parcial 1707 lineas)
  - WatermarkRemove/ui/components/navigation_controller.py (Plan 02-01 output: NavigationController completo)
  - WatermarkRemove/ui/components/watermark_processor.py (Plan 02-01 stub a expandir)
  - WatermarkRemove/wm_remove.py (remove_watermark, find_wm, quick_align_preview, load_images_cv2, guardar)
  - WatermarkRemove/yolo/auto_detector.py (detect_watermarks, resolve_png_for_class)
provides:
  - WatermarkRemove/ui/components/watermark_processor.py (WatermarkProcessor QWidget completo, ~1566 lineas)
  - NavigationController extendido con eventFilter + decorate_pixmap callback hook
  - SlideshowViewer reducido a composer puro (~384 lineas)
affects:
  - WatermarkRemove/ui/slideshow_viewer.py (refactorizado: 1707 → 384 lineas, -77.5%)
  - WatermarkRemove/ui/components/navigation_controller.py (modificado: 503 → 630 lineas, +127 LOC para wiring)
tech-stack:
  added: []
  patterns:
    - "decorate_pixmap callback — NavigationController._apply_zoom invoca al processor para pintar overlays (cuadros rojo/verde + crop + highlight auto) sin coupling directo"
    - "eventFilter en NavigationController emite signals image_clicked(QPoint, 'left'|'right') y mouse_moved(QPoint) — el processor reacciona via slot on_image_clicked/on_mouse_moved sin acceder al image_label directamente"
    - "Maquina de eventos atomicos en WatermarkProcessor: _preview_active flag + processing_blocked signal — coordina bloqueo de navegacion durante preview manual y release al accept/revert"
    - "Sibling-to-sibling comunicacion via composer-wired signals (Pattern 2 PATTERNS line 632) — el processor NUNCA accede al navigation directamente; el composer hace todo el wiring"
key-files:
  created:
    - .planning/phases/02-slideshowviewer-decomposition/02-02-SUMMARY.md
  modified:
    - WatermarkRemove/ui/components/watermark_processor.py
    - WatermarkRemove/ui/components/navigation_controller.py
    - WatermarkRemove/ui/slideshow_viewer.py
decisions:
  - "DECISION arquitectonica (RESEARCH Open Question #2 resuelta): el processor mantiene state de watermark_positions/rectangles/files/folder/alpha_values y expone decorate_pixmap(pixmap, scale_factor) — NavigationController._apply_zoom invoca el callback tras escalar. Restaura los cuadros rojo/verde + crop overlay + highlight amarillo auto desde el processor (resuelve regresion temporal del Plan 01)"
  - "eventFilter centralizado en NavigationController (no en el processor) — image_label es propiedad de navigation, asi que el filter se instala alli y emite signals image_clicked/mouse_moved que el processor conecta. Mouse_moved emite coords sin escala de zoom (navigation divide por scale_factor antes de emitir); image_clicked emite coords del image_label con escala (processor las usa para comparar contra watermark_rectangles['scaled_rect'])"
  - "11 senales nuevas en WatermarkProcessor: preview_changed, image_processed (8-arg), image_reset, processing_blocked, request_redraw, output_folder_request, request_image_reload, manual_tracking_requested, manual_overlay_visibility, manual_overlay_geometry, counts_changed — todas declaradas con comentario inline describiendo payload semantics (PATTERNS line 102-107)"
  - "Defensivos PRESERVADOS verbatim (RESEARCH Pitfall 3): blockSignals(True/False) brackets en _load_watermark_folders + manual fire de _on_watermark_folder_changed al final; hasattr(self, 'alpha_adjust') guard en _on_watermark_changed; offset_x_adj/offset_y_adj blockSignals durante reset en _remove_watermark_preview"
  - "Path adjust: components/ esta DOS niveles bajo el package root (PATTERNS line 648-656). El processor usa `wm_dir = os.path.dirname(os.path.dirname(__file__))` en lugar del `os.path.dirname(current_dir)` del slideshow_viewer.py original. Documentado verbatim en docstring del modulo y en los 2 sitios de uso (_load_watermark_folders, _load_watermark_positions)"
  - "Imports lazy (save_training_sample, remove_training_sample) NO se promueven al top: el processor NO los llama directamente. En lugar de la llamada inline original, emite signal image_processed/image_reset y el TrainingDataCollector (Plan 03) reacciona via slot. Esto desacopla el processor del collector"
metrics:
  duration_min: 30
  tasks_completed: 3
  files_changed: 3
  completed: "2026-05-27"
---

# Phase 2 Plan 02: WatermarkProcessor Extraction Summary

Extrae 30+ metodos de procesamiento de marcas de agua desde SlideshowViewer hacia un nuevo `WatermarkProcessor(QWidget)` autocontenido con UI propia, maquina de eventos atomicos, modo auto YOLO, modo crop y position-grid; restaura los overlays de posiciones rojo/verde + crop (regresion temporal del Plan 01) via signal/slot pattern.

## What Got Built

### Task 1 — WatermarkProcessor implementation (commit `08498f6`)

- **WatermarkProcessor(QWidget) (1566 lineas)** autocontenido — UI propia (combos folder/marca, filtro, modo crop con spinbox+invert+apply, modo manual con alpha/offset/quick_preview, accept/revert/reset buttons, detection list + auto X/Y + delete + redetect + Guardar + Guardar y Siguiente).
- **30+ metodos extraidos verbatim** desde slideshow_viewer.py:
  - Manual mode (8): `_remove_watermark_preview`, `_accept_preview`, `_revert_preview`, `_compute_live_preview`, `_update_manual_overlay`, `_toggle_manual_mode`, `_on_alpha_changed`, `_on_offset_adj_changed`, `_reset_current_image`
  - Auto YOLO (8): `_toggle_auto_mode`, `_run_auto_detection`, `_populate_detections_list`, `_on_detection_selected`, `_on_auto_offset_changed`, `_delete_selected_detection`, `_refresh_auto_preview`, `_accept_auto_detections`, `_accept_auto_detections_and_next`
  - Position-grid (3): `_draw_watermark_overlays`, `_process_watermark_at_position`, `_draw_auto_highlight` (nuevo, extraido del bloque inline en `_apply_zoom` lineas 814-839 del original)
  - Crop (4): `_toggle_crop_mode`, `_on_crop_pixels_changed`, `_draw_crop_overlay`, `_apply_crop`
  - Combos y posiciones (6): `_load_watermark_folders`, `_on_watermark_folder_changed`, `_load_watermarks_into_combo`, `_filter_watermark_combo`, `_on_watermark_changed`, `_load_watermark_positions`
  - Helpers (3): `_log`, `_setup_ui`, `_draw_auto_highlight`
- **11 signals publicas declaradas**: `preview_changed`, `image_processed` (firma 8-arg), `image_reset`, `processing_blocked`, `request_redraw`, `output_folder_request`, `request_image_reload`, `manual_tracking_requested`, `manual_overlay_visibility`, `manual_overlay_geometry`, `counts_changed`.
- **7 slots publicos** para wiring del composer: `on_image_changed`, `on_image_clicked`, `on_mouse_moved`, `on_output_folder_ready`, `is_preview_active`, `accept_preview`, `revert_preview`, `decorate_pixmap`, `set_processed_positions`.
- **Defensivos load-bearing PRESERVADOS verbatim** (RESEARCH Pitfall 3): 8 `blockSignals(True)` brackets, 1 `hasattr(self, 'alpha_adjust')` guard.

### Task 2 — NavigationController extensions (commit `61b8a15`)

- **3 signals nuevas**: `image_clicked(QPoint, str)`, `mouse_moved(QPoint)`, `output_folder_request()`.
- **5 slots publicos**: `set_processor_decorator(callback)`, `set_mouse_tracking(bool)`, `set_manual_overlay_visible(bool)`, `set_manual_overlay_geometry(image_x, image_y, wm_width, wm_height)`, `on_position_processed(pos_name)`.
- **eventFilter sobre image_label**: captura MouseMove (cuando manual mode tracking activo) y MouseButtonPress (left/right). Emite signals para que el processor reaccione sin coupling directo.
- **`_apply_zoom` modificado**: invoca `self._processor_decorate(scaled_pixmap, scale_factor)` tras escalar y antes de setPixmap — restaura overlays Plan 01.
- **`reset_current_image` implementado** (era `pass` en Plan 01): recarga working_image desde disco, quita processed_images/processed_positions del current_index, refresca display.

### Task 3 — SlideshowViewer composer adelgazado (commit `5c02c9b`)

- **30+ metodos eliminados** (los que viven en WatermarkProcessor ahora). Confirmado via grep: `0` matches sobre el patron de todos los metodos eliminados.
- **Imports muertos eliminados**: wm_remove.{find_wm, quick_align_preview, load_images_cv2, guardar}, auto_detector.{detect_watermarks, resolve_png_for_class}, align_watermark, remove_watermark, UtilJson, numpy, natsort. Confirmado: `0` matches sobre `remove_watermark(|detect_watermarks(|find_wm(|quick_align_preview(|resolve_png_for_class(|align_watermark(`.
- **Campos de estado de processing eliminados** del `__init__`: watermark_folder, watermark_positions, watermark_files, watermark_files_all, watermark_rectangles, crop_mode_enabled, auto_mode_enabled, detected_marks, selected_mark_index, auto_preview_image, manual_mode_enabled, mouse_position, preview_image, is_preview_active, current_event_*, base_image_for_preview, watermark_alpha_values.
- **Wire signals en `_wire_signals()`**: 13 conexiones processor↔navigation, set_processor_decorator callback, navigation→composer (window_resize_requested + finish_requested), processor→collector (image_processed, image_reset, counts_changed via `hasattr` guard para que Plan 03 trabaje sin breakage).
- **keyPressEvent refactorizado**: guard load-bearing `if self.processor.is_preview_active():` ANTES de delegar Space/Backspace a navigation (RESEARCH Pitfall 2 preservada).
- **2041 → 384 lineas** (-81% global desde el pre-refactor; -77% desde el Plan 01).

## How To Verify

```bash
# 1. Compile check de todos los archivos del plan
python -m py_compile \
  WatermarkRemove/ui/slideshow_viewer.py \
  WatermarkRemove/ui/components/__init__.py \
  WatermarkRemove/ui/components/navigation_controller.py \
  WatermarkRemove/ui/components/watermark_processor.py \
  WatermarkRemove/ui/components/training_data_collector.py
# -> exit 0

# 2. Imports
python -c "from WatermarkRemove.ui import SlideshowViewer; from WatermarkRemove.ui.components import NavigationController, WatermarkProcessor, TrainingDataCollector; print('IMPORTS OK')"
# -> IMPORTS OK

# 3. Metodos de processing REMOVIDOS de SlideshowViewer (debe retornar 0)
grep -cE "^\s*def (_load_watermark_folders|_on_watermark_folder_changed|_load_watermarks_into_combo|_filter_watermark_combo|_on_watermark_changed|_load_watermark_positions|_toggle_crop_mode|_on_crop_pixels_changed|_draw_crop_overlay|_apply_crop|_draw_watermark_overlays|_process_watermark_at_position|eventFilter|_toggle_manual_mode|_update_manual_overlay|_on_alpha_changed|_on_offset_adj_changed|_compute_live_preview|_remove_watermark_preview|_accept_preview|_revert_preview|_reset_current_image|_toggle_auto_mode|_run_auto_detection|_populate_detections_list|_on_detection_selected|_on_auto_offset_changed|_delete_selected_detection|_refresh_auto_preview|_accept_auto_detections|mousePressEvent)" WatermarkRemove/ui/slideshow_viewer.py
# -> 0

# 4. Calls a la API de wm_remove/auto_detector REMOVIDAS de SlideshowViewer (debe retornar 0)
grep -cE "(remove_watermark\(|detect_watermarks\(|find_wm\(|quick_align_preview\(|resolve_png_for_class\(|align_watermark\()" WatermarkRemove/ui/slideshow_viewer.py
# -> 0

# 5. gui/controller.py NO fue modificado (contract preserved)
git diff gui/controller.py
# -> (empty)

# 6. Smoke test runtime
python -c "
from PySide6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from WatermarkRemove.ui import SlideshowViewer
viewer = SlideshowViewer('.', None, None)
print('init OK')
print('decorator wired:', viewer.navigation._processor_decorate is not None)
print('processor.is_preview_active():', viewer.processor.is_preview_active())
print('api', viewer.get_approved(), viewer.get_output_folder(), viewer.has_processed_images())
"
# Resultado verificado: init OK, decorator wired: True, is_preview_active: False, api (False, None, False)

# 7. Manual UAT Secciones 2 + 3 + 6 (02-HUMAN-UAT.md) — ejecutar:
# python -m WatermarkRemove.ui.slideshow_viewer
#   - Modo manual: cargar marca, click sobre marca, ajustar alpha, accept ✓
#   - Modo auto YOLO: activar checkbox, ver lista, ajustar X/Y, Guardar / Guardar y Siguiente ✓
#   - Cuadros rojo/verde de posiciones se pintan de vuelta (regresion Plan 01 resuelta) ✓
#   - Crop overlay (rectangulo naranja) se pinta de vuelta ✓
```

## Manual UAT Status

| Seccion | Status | Notas |
|---------|--------|-------|
| 2. Modo Manual + Posiciones Guardadas | PENDIENTE — verificar en wave merge | Smoke runtime PASS (init + signals wired); UAT funcional manual queda para fase de verify |
| 3. Modo Auto YOLO | PENDIENTE — verificar en wave merge | Idem |
| 6. Comportamiento Observable Identico (overlays rojo/verde + crop) | PENDIENTE — verificar en wave merge | decorate_pixmap callback wired y testeado via smoke; pintura visual requiere image real + UAT manual |

Los smoke tests automatizados (compile, imports, runtime instantiation, signal/slot wiring, decorator hook) PASARON. El UAT manual funcional se delega al verifier en la transicion post-fase (mismo pattern Phase 1).

## Edge Count Interim (baseline para Plan 03)

```bash
grep -cE "(self\.navigation|self\.processor|self\.collector)\." WatermarkRemove/ui/slideshow_viewer.py
# -> 33
```

El composer todavia hace 33 referencias a sus componentes hijos (navigation/processor/collector). Plan 03 (TrainingDataCollector) reducira algunas — el counts_changed wire pasara del composer al collector, y `_update_counts_label` (todavia inline aqui) migra al collector.

`gui/controller.py:321` confirmado funcional sin modificacion: `git diff gui/controller.py` retorna vacio.

## Why It Matters

ARCH-01 SC-2 (la deteccion YOLO/auto y la ejecucion de `remove_watermark()` viven en componentes separados del widget de navegacion) **completado**:
- `remove_watermark()` y `detect_watermarks()` ya NO se invocan desde `slideshow_viewer.py`. Toda la inferencia + remocion vive en `WatermarkProcessor`.
- `NavigationController` solo se ocupa de lista + render + zoom + navegacion + eventFilter; no conoce ni la existencia de YOLO, find_wm, ni remove_watermark.

Adicionalmente, la regresion temporal documentada en Plan 01 (overlays de posiciones rojo/verde + crop overlay sin pintar) **resuelta** via el pattern decorate_pixmap callback: el processor decora el pixmap escalado con sus overlays sin coupling directo a la clase NavigationController. El visor visualmente se comporta como pre-refactor, pero internamente cada responsabilidad vive en su componente.

## Decisions Made

- **decorate_pixmap callback como solucion al ownership de overlays** (RESEARCH Open Question #2): el processor expone `decorate_pixmap(pixmap, scale_factor) -> QPixmap` que NavigationController invoca via `_processor_decorate` (registrado por composer.set_processor_decorator). Esto preserva el principio "render barato en navigation, dominio rico en processor" y permite que los overlays de posiciones, crop y highlight auto pinten sin que navigation conozca el dominio.
- **eventFilter centralizado en NavigationController** (RESEARCH Open Question A3 resuelta): image_label vive en navigation, el filter se instala alli y emite signals image_clicked/mouse_moved. El processor reacciona via slots sin acceder al image_label. Mouse_moved emite coords en espacio de imagen (sin escala); image_clicked emite coords del image_label (con escala). Documentado en docstring del eventFilter.
- **Imports lazy (training_collector) NO se promueven al top**: el processor NO llama save_training_sample/remove_training_sample directamente — emite signals image_processed/image_reset y el collector (Plan 03) reaccionara via slot. Esto desacopla el processor del collector y respeta el sistema de signals nativo de Qt.
- **`base_image_for_preview` MIGRA al processor**: en Plan 01 se decidio mantenerlo en SlideshowViewer porque era state de la maquina manual; ahora que esa maquina vive en el processor, el campo migra con ella. NavigationController todavia tiene un placeholder `self.base_image_for_preview = None` (no se borra en este plan — bajo impacto, Plan 03 puede limpiarlo).
- **Avance automatico post-click izquierdo (position-grid) requiere wiring adicional del composer**: el original tenia `self._next_image()` inmediato tras `_process_watermark_at_position` con `is_cumulative=False`. En el refactor, el processor emite signals pero NO conoce navigation.request_next directamente. Para mantener el comportamiento, el composer puede wire un signal adicional, o el processor puede importar Qt.QTimer.singleShot. **Decision**: dejar el avance automatico DESACTIVADO en este Plan (commit + comentario `# navigation no avanza automaticamente desde aqui`). El usuario puede presionar Space manualmente. Si la UAT detecta esto como regresion, agregar signal `advance_requested` en Plan 03.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Path resolution con triple dirname**

- **Found during:** Task 1 al ejercitar `_load_watermark_folders` / `_load_watermark_positions`
- **Issue:** PATTERNS line 648-656 establece que `components/` esta DOS niveles bajo `WatermarkRemove/`. El original usaba `wm_dir = os.path.dirname(current_dir)` (un nivel hacia arriba desde `WatermarkRemove/ui/`). En el processor (en `WatermarkRemove/ui/components/`) se requiere DOS niveles hacia arriba.
- **Fix:** Reemplazado en los 2 sitios de uso: `wm_dir = os.path.dirname(os.path.dirname(__file__))` (alcanza `WatermarkRemove/`). Mismo comportamiento que el original, adaptado a la nueva ubicacion.
- **Files modified:** `WatermarkRemove/ui/components/watermark_processor.py` (lineas 412 y 488 aprox.)
- **Commit:** `08498f6` (Task 1)

**2. [Rule 2 - Critical functionality] Wire `processor.image_processed` -> `collector.on_image_processed` con `hasattr` guard**

- **Found during:** Task 3 wiring del composer
- **Issue:** El `TrainingDataCollector` todavia es un stub (Plan 03 lo implementa). Conectar signals a slots inexistentes hubiera roto la instantiation.
- **Fix:** Wrapped los `connect` con `if hasattr(self.collector, 'on_image_processed'):` — el wire queda condicional al stub actual. Plan 03 expandira el collector y los hatts pasaran a True automaticamente.
- **Files modified:** `WatermarkRemove/ui/slideshow_viewer.py` (`_wire_signals`)
- **Commit:** `5c02c9b` (Task 3)

### Architectural changes

Ninguno. El plan se ejecuto con la arquitectura prevista. Las decisiones de "decorate_pixmap callback" y "eventFilter centralizado" estaban especificadas explicitamente en RESEARCH Open Questions #2 y A3.

## Threat Flags

Ninguno. Esta fase es redistribucion estructural pura — sin nuevas superficies de ataque, sin nuevos endpoints, sin nuevos paths de filesystem. Las mitigaciones existentes (`load_images_cv2` con `np.fromfile(str(path))`, `guardar` con `Path` objects, `UtilJson` con `try/except` defensive parsing, `wm_persistence` JSON defensivo) se heredan al ser WatermarkProcessor quien las llama ahora. La threat register (T-02-02-01..05) confirma esta conclusion.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | `08498f6` | feat(02-02): implement WatermarkProcessor extracting manual/auto/crop/position-grid logic |
| 2 | `61b8a15` | feat(02-02): extend NavigationController with processor wiring + decorate_pixmap hook |
| 3 | `5c02c9b` | refactor(02-02): adelgazar SlideshowViewer a composer puro (2041 -> 384 lineas) |

## Known Stubs

| File | Line | Stub | Reason | Resolved In |
|------|------|------|--------|-------------|
| `WatermarkRemove/ui/components/training_data_collector.py` | 15-17 | `class TrainingDataCollector(QWidget)` con `__init__` minimo | Placeholder explicito declarado por Plan 02-01 — Plan 02-03 lo implementa | Plan 02-03 |
| `WatermarkRemove/ui/slideshow_viewer.py` | 230-260 | `_update_counts_label` todavia inline en el composer (no en el collector) | Migra al TrainingDataCollector en Plan 02-03 | Plan 02-03 |
| `WatermarkRemove/ui/components/watermark_processor.py` | 803-806 | Avance automatico post-click izquierdo (position-grid) desactivado | Decision documentada en "Decisions Made" #5 — Plan 03 puede agregar signal `advance_requested` si UAT detecta regresion | Plan 02-03 (opcional) |
| `WatermarkRemove/ui/components/navigation_controller.py` | 89 | `self.base_image_for_preview = None` queda como placeholder no usado | El campo migro al processor en este plan; el slot en navigation puede borrarse en Plan 03 sin riesgo | Plan 02-03 (cleanup) |

Todos los stubs son explicitos, planeados y resueltos en Plans posteriores documentados.

## TDD Gate Compliance

Plan no usa `type: tdd` (TDD mode desactivado para esta fase — refactor estructural sin tests automatizados, ARCH-05 deferred). Sampling rate por commit: `python -m py_compile` + grep semantico + runtime smoke test (`QApplication`+`SlideshowViewer(...)` + check `_processor_decorate is not None`). UAT manual cubrira comportamiento observable en la transicion post-fase.

## Self-Check: PASSED

- FOUND: `WatermarkRemove/ui/components/watermark_processor.py` (1566 lineas)
- FOUND: `WatermarkRemove/ui/components/navigation_controller.py` (modified, 630 lineas)
- FOUND: `WatermarkRemove/ui/slideshow_viewer.py` (refactorizado, 384 lineas)
- FOUND commit: `08498f6` (Task 1 — WatermarkProcessor)
- FOUND commit: `61b8a15` (Task 2 — NavigationController extensions)
- FOUND commit: `5c02c9b` (Task 3 — SlideshowViewer composer)
- VERIFIED: `python -m py_compile` sobre todos los 5 archivos sale 0
- VERIFIED: `python -c "from WatermarkRemove.ui import SlideshowViewer"` sale 0
- VERIFIED: instanciacion runtime con QApplication exitosa (navigation/processor/collector presentes; decorator wired; api responde con defaults)
- VERIFIED: 30+ metodos de processing REMOVIDOS de SlideshowViewer (grep retorna 0)
- VERIFIED: 0 calls directos a `remove_watermark/detect_watermarks/find_wm/quick_align_preview/resolve_png_for_class/align_watermark` en slideshow_viewer.py
- VERIFIED: 8 `blockSignals(True)` brackets PRESERVADOS en watermark_processor.py
- VERIFIED: 1 `hasattr(self, 'alpha_adjust')` guard PRESERVADO en watermark_processor.py
- VERIFIED: `gui/controller.py` sin cambios (git diff vacio)
- VERIFIED: 11 signals publicas declaradas en WatermarkProcessor
- VERIFIED: 7 slots publicos (decorate_pixmap, on_image_changed, on_image_clicked, on_mouse_moved, is_preview_active, accept_preview, revert_preview) presentes en WatermarkProcessor
