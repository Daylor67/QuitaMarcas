---
phase: 02-slideshowviewer-decomposition
plan: 01
subsystem: WatermarkRemove/ui
tags: [refactor, qt, signal-slot, decomposition, navigation]
requires:
  - WatermarkRemove/ui/slideshow_viewer.py (existente, monolítico ~2041 líneas)
  - WatermarkRemove/wm_remove.py (load_images_cv2, guardar — sin cambios)
  - WatermarkRemove/services/__init__.py (wm_persistence singleton — sin cambios)
provides:
  - WatermarkRemove/ui/components/ (paquete nuevo)
  - WatermarkRemove/ui/components/__init__.py (barrel export)
  - WatermarkRemove/ui/components/navigation_controller.py (NavigationController QWidget completo)
  - WatermarkRemove/ui/components/watermark_processor.py (stub para Plan 02-02)
  - WatermarkRemove/ui/components/training_data_collector.py (stub para Plan 02-03)
affects:
  - WatermarkRemove/ui/slideshow_viewer.py (refactorizado a composer parcial: 2041 → 1707 líneas)
tech-stack:
  added: []
  patterns:
    - "Composer + componentes (Signal/Slot) — el composer (SlideshowViewer/QDialog) instancia NavigationController y conecta sus señales (window_resize_requested → resize, finish_requested → _finish_review)"
    - "Barrel export en paquete `WatermarkRemove/ui/components/__init__.py` (análogo a `WatermarkRemove/services/__init__.py`)"
    - "Public-slot rename: `_next_image`/`_previous_image` → `request_next`/`request_previous` (slots públicos de NavigationController)"
    - "Window-resize via signal: NavigationController emite `window_resize_requested(int, int)` que el composer (QDialog) consume — un QWidget no puede llamar `self.resize()` directamente"
key-files:
  created:
    - WatermarkRemove/ui/components/__init__.py
    - WatermarkRemove/ui/components/navigation_controller.py
    - WatermarkRemove/ui/components/watermark_processor.py
    - WatermarkRemove/ui/components/training_data_collector.py
    - .planning/phases/02-slideshowviewer-decomposition/02-01-SUMMARY.md
  modified:
    - WatermarkRemove/ui/slideshow_viewer.py
    - .planning/phases/02-slideshowviewer-decomposition/02-VALIDATION.md
decisions:
  - "NavigationController = QWidget (no QDialog) — `window_resize_requested` signal delega resize al composer; permite que NavigationController sea instalable como hijo de cualquier layout, no solo un dialogo"
  - "`base_image_for_preview` queda en SlideshowViewer durante Plan 01 (es parte de la maquina de estados manual que migra en Plan 02-02 con `WatermarkProcessor`) — NavigationController lo declara como placeholder pero no lo modifica"
  - "REGRESION TEMPORAL ACEPTADA: overlays de posicion rojo/verde (`_draw_watermark_overlays`) y crop overlay (`_draw_crop_overlay`) NO se pintan durante Plan 01; se restauran en Plan 02-02 cuando WatermarkProcessor decore el pixmap via signal `request_redraw`. Documentado en `NavigationController._apply_zoom` TODO + en comentario del composer linea ~634"
  - "Stubs `WatermarkProcessor` y `TrainingDataCollector` instanciados pero NO wired — placeholders explicitos para Plans 02-02 y 02-03"
metrics:
  duration_min: 10
  tasks_completed: 3
  files_changed: 6
  completed: "2026-05-27"
---

# Phase 2 Plan 01: SlideshowViewer Decomposition — Navigation Extraction Summary

Extrae 13 métodos de navegación + render desde el God Class `SlideshowViewer` hacia un nuevo `NavigationController(QWidget)` con Signal/Slot, estableciendo el patrón composer+componentes que usarán los Plans 02-02 y 02-03.

## What Got Built

- **Paquete `WatermarkRemove/ui/components/`** con barrel export en `__init__.py` que expone `NavigationController`, `WatermarkProcessor`, `TrainingDataCollector` (los dos últimos son stubs explícitos para los siguientes Plans).
- **`NavigationController(QWidget)` (503 líneas)** que asume la responsabilidad completa de:
  - Lista de imágenes (`image_files`, `current_index`), `working_image`, `output_folder`, `processed_images`, `processed_positions`, `current_pixmap`, `zoom_level`.
  - UI propia: contador (`counter_label`), filename label, botones prev/next, scroll_area + image_label + zoom_overlay_label + manual_overlay_label (este último placeholder para Plan 02-02).
  - 13 métodos extraídos verbatim desde `SlideshowViewer`: `_log`, `_setup_ui`, `_create_output_folder`, `_load_image_list`, `_show_current_image`, `_apply_zoom`, `_set_zoom`, `_show_zoom_overlay`, `_hide_zoom_overlay`, `_request_window_resize` (antes `_adjust_window_size`), `_update_counter`, `_clear_image_memory`, `_save_current_image_as_is`.
  - Métodos renombrados a slots públicos: `request_next` (antes `_next_image`), `request_previous` (antes `_previous_image`).
  - Slots Plan 02 wiring (stubs): `set_navigation_enabled`, `on_preview_changed`, `on_image_processed`, `reset_current_image`, `adjust_zoom`, `set_zoom_level`.
  - 5 signals públicas: `image_changed(int, object, object)`, `output_folder_ready(object)`, `request_redraw()`, `window_resize_requested(int, int)`, `finish_requested()`.
  - `wheelEvent` propio (Ctrl + rueda → zoom; sin Ctrl → scroll normal).
- **`SlideshowViewer` refactorizado a composer parcial** (2041 → 1707 líneas, -334 LOC, -16%):
  - Instancia `self.navigation = NavigationController(folder_path, parent=self, watermark_tab=watermark_tab)` y la coloca como panel derecho (con `stretch=1`).
  - Conecta `navigation.window_resize_requested` → `_on_navigation_resize_requested` (preserva ancho con altura actual) y `navigation.finish_requested` → `_finish_review`.
  - Conserva inline (migra en Plans 02/03): toda la lógica manual mode (`_remove_watermark_preview`, `_accept_preview`, `_revert_preview`, `_compute_live_preview`, `_update_manual_overlay`, `_toggle_manual_mode`), auto mode YOLO (`_run_auto_detection`, `_accept_auto_detections`, `_populate_detections_list`, etc.), training counts (`_update_counts_label`), crop mode (`_apply_crop`, `_toggle_crop_mode`, `_draw_crop_overlay`), position grid (`_process_watermark_at_position`, `_draw_watermark_overlays`, `mousePressEvent`, `eventFilter`), watermark folder/file management (`_load_watermark_folders`, `_on_watermark_folder_changed`, `_load_watermark_positions`, etc.).
  - `keyPressEvent` refactorizado: zoom keys (+/-/0) delegan a `self.navigation.adjust_zoom` / `set_zoom_level`; Space/Backspace delegan a `self.navigation.request_next` / `request_previous` (preservando el guard `check_opc_avanzadas and self.is_preview_active` antes de delegar — RESEARCH Pitfall 2 load-bearing).
  - Stubs adicionales instanciados pero inactivos: `self.processor = WatermarkProcessor(...)`, `self.collector = TrainingDataCollector(...)` (placeholders Plans 02-02 / 02-03).
  - Todas las referencias internas a `self.image_files/current_index/working_image/output_folder/processed_images/processed_positions/image_label/scroll_area/current_pixmap/zoom_level` reescritas a `self.navigation.<x>`.
- **`02-VALIDATION.md`** marcado `wave_0_complete: true` y `nyquist_compliant: true` (los 4 archivos de Wave 0 — barrel export + 3 stubs — están creados inline en Task 1).

## How To Verify

```bash
# 1. Compile check todos los archivos del plan
python -m py_compile \
  WatermarkRemove/ui/components/__init__.py \
  WatermarkRemove/ui/components/navigation_controller.py \
  WatermarkRemove/ui/components/watermark_processor.py \
  WatermarkRemove/ui/components/training_data_collector.py \
  WatermarkRemove/ui/slideshow_viewer.py

# 2. Imports
python -c "from WatermarkRemove.ui import SlideshowViewer; from WatermarkRemove.ui.components import NavigationController, WatermarkProcessor, TrainingDataCollector"

# 3. Métodos de navegación REMOVIDOS de SlideshowViewer (debe retornar 0)
grep -cE "^\s*def (_load_image_list|_show_current_image|_create_output_folder|_next_image|_previous_image|_save_current_image_as_is|_apply_zoom|_set_zoom|_show_zoom_overlay|_hide_zoom_overlay|_adjust_window_size|_update_counter|_clear_image_memory)" WatermarkRemove/ui/slideshow_viewer.py
# -> 0

# 4. gui/controller.py NO fue modificado (contract preserved)
git diff gui/controller.py
# -> (empty)

# 5. Smoke test runtime instantiation
python -c "
from PySide6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
from WatermarkRemove.ui import SlideshowViewer
viewer = SlideshowViewer('.', None, None)
print('init OK', viewer.navigation, viewer.processor, viewer.collector)
print('api', viewer.get_approved(), viewer.get_output_folder(), viewer.has_processed_images())
"
# Resultado verificado: init OK, navigation/processor/collector instanciados, api (False, None, False)

# 6. Manual UAT Sección 1 (Navegación) — ejecutar SmartStitchGUI.py o
# python -m WatermarkRemove.ui.slideshow_viewer con carpeta de imágenes
#   - Abre el visor con prev/next + counter + filename en panel derecho ✓
#   - Space avanza, Backspace retrocede ✓
#   - Ctrl+rueda hace zoom; +/-/0 también ✓
#   - Al llegar a la última imagen y presionar Space, aparece dialogo finalizar ✓
```

## Why It Matters

ARCH-01 SC-1 (descomponer SlideshowViewer en componentes de responsabilidad única) avanza un paso clave: el primer componente extraído (`NavigationController`) demuestra que el patrón composer + Signal/Slot funciona sin romper el contrato externo (`gui/controller.py:321` sin modificar, API pública preservada: `get_approved` / `get_output_folder` / `has_processed_images` / `review_completed`). Los Plans 02-02 y 02-03 ahora tienen un molde claro (signals declaradas, slots públicos, stubs instanciables) para extraer manual mode y training data collector con el mismo patrón. Reducción de 334 líneas en el God Class es solo el principio — Plans siguientes lo reducirán a un composer fino.

## Decisions Made

- **NavigationController = QWidget no QDialog**: permite que sea hijo en cualquier layout. La consecuencia (no puede llamar `self.resize()` sobre la ventana padre) se resuelve con la signal `window_resize_requested(int, int)`. Esto es más limpio que pasarle una referencia al QDialog y evita coupling inverso.
- **`base_image_for_preview` queda en SlideshowViewer durante Plan 01**: aunque conceptualmente es estado de la imagen base para preview, su uso intensivo está en `_remove_watermark_preview` / `_compute_live_preview` que son del modo manual — todo eso migra junto al `WatermarkProcessor` en Plan 02-02. Mover una sola variable hacia `NavigationController` ahora produciría una `temporal field` (Plan 02-02 la sacaría). NavigationController declara el atributo como placeholder pero no lo modifica.
- **Regresión temporal aceptada (overlays de posición + crop)**: los painters de cuadros rojo/verde y el rectángulo naranja de crop dependen de `watermark_positions` + `watermark_files` + `crop_pixels_input` que viven en SlideshowViewer. Pintarlos desde `NavigationController._apply_zoom` requeriría exponer esa data via getters / signal o moverla — ambos creating temporal coupling. Decisión: pintar via signal `request_redraw` desde el processor en Plan 02-02 (RESEARCH Open Question #2). El visor sigue siendo funcional durante Plan 01 — solo los overlays de posición/crop están temporalmente invisibles.
- **Stubs vacíos para WatermarkProcessor / TrainingDataCollector**: Plan 02-02 y 02-03 los expanden. Las firmas mínimas (`__init__(parent=None, watermark_tab=None)`) son suficientes para que el composer los instancie sin error y para que los Plans siguientes tengan archivos sobre los que iterar (criterio Wave 0 satisfecho).
- **Public-slot rename `_next_image` → `request_next` / `_previous_image` → `request_previous`**: convierte métodos internos en API pública del componente, alineado al patrón Signal/Slot donde slots públicos no llevan underscore.

## Deviations from Plan

Ninguna. El plan se ejecutó tal como fue diseñado en `02-01-PLAN.md`. Las "decisiones" arriba son explicitaciones de instrucciones del plan, no desviaciones.

### Auto-fixed Issues

Ninguno.

## Threat Flags

Ninguno. Esta fase es redistribución estructural pura — sin nuevas superficies de ataque, sin nuevos endpoints, sin nuevos paths de filesystem. Las mitigaciones existentes (`load_images_cv2` con `np.fromfile(str(path))`, `guardar` con `Path` objects, `wm_persistence` JSON defensivo) se heredan al ser NavigationController quien las llama ahora.

## Commits

| Task | Hash | Message |
|------|------|---------|
| 1 | `008d711` | feat(02-01): create components/ package with QWidget stubs |
| 2 | `590fa4a` | feat(02-01): implement NavigationController extracting nav+render from SlideshowViewer |
| 3 | `aeff2a3` | refactor(02-01): delegate navigation to NavigationController in SlideshowViewer |

## Known Stubs

| File | Line | Stub | Reason | Resolved In |
|------|------|------|--------|-------------|
| `WatermarkRemove/ui/components/watermark_processor.py` | 16-18 | `class WatermarkProcessor(QWidget)` con `__init__` mínimo (super + parent) | Placeholder explícito declarado por `02-01-PLAN.md` Task 1 artifact spec — Plan 02-02 lo implementa | Plan 02-02 |
| `WatermarkRemove/ui/components/training_data_collector.py` | 15-17 | `class TrainingDataCollector(QWidget)` con `__init__` mínimo | Placeholder explícito declarado por `02-01-PLAN.md` Task 1 artifact spec — Plan 02-03 lo implementa | Plan 02-03 |
| `WatermarkRemove/ui/components/navigation_controller.py` | 287-292 | `_apply_zoom` no pinta overlays de posición/crop (regresion temporal documentada) | Decoradores via `request_redraw` signal — el processor los aplicará desde Plan 02-02 | Plan 02-02 |
| `WatermarkRemove/ui/components/navigation_controller.py` | 393-397 | `_clear_image_memory` solo limpia state de navigation; `current_event_*` quedan en SlideshowViewer | Manual mode state migra junto con WatermarkProcessor | Plan 02-02 |
| `WatermarkRemove/ui/components/navigation_controller.py` | 489-491 | `reset_current_image()` es `pass` | El reset también implica borrar entries de `training_data.json` y archivo de output, eso se orquesta desde el processor | Plan 02-02 / 02-03 |
| `WatermarkRemove/ui/slideshow_viewer.py` | 107-108 | `self.processor` y `self.collector` instanciados pero sin wiring de signals | Plan 02-02 y 02-03 conectan los componentes con sus slots de manual/auto/training | Plans 02-02, 02-03 |

Todos los stubs son explícitos, planeados y resueltos en Plans posteriores documentados.

## TDD Gate Compliance

Plan no usa `type: tdd` (TDD mode desactivado para esta fase por decisión inicial — refactor estructural sin tests automatizados todavía; ARCH-05 deferred). Sampling rate por commit usa `python -m py_compile` + grep semánticos; UAT manual cubre comportamiento observable.

## Self-Check: PASSED

- FOUND: `WatermarkRemove/ui/components/__init__.py` (barrel export)
- FOUND: `WatermarkRemove/ui/components/navigation_controller.py` (NavigationController completo, 503 líneas)
- FOUND: `WatermarkRemove/ui/components/watermark_processor.py` (stub)
- FOUND: `WatermarkRemove/ui/components/training_data_collector.py` (stub)
- FOUND: `WatermarkRemove/ui/slideshow_viewer.py` (refactorizado, 1707 líneas)
- FOUND commit: `008d711` (Task 1)
- FOUND commit: `590fa4a` (Task 2)
- FOUND commit: `aeff2a3` (Task 3)
- VERIFIED: `gui/controller.py` sin cambios (git diff vacío)
- VERIFIED: `python -m py_compile` sobre los 5 archivos sale 0
- VERIFIED: `python -c "from WatermarkRemove.ui import SlideshowViewer"` sale 0
- VERIFIED: instanciación runtime con QApplication exitosa (navigation/processor/collector presentes; get_approved/get_output_folder/has_processed_images responden con defaults)
- VERIFIED: 13 métodos de navegación REMOVIDOS de SlideshowViewer (grep retorna 0)
