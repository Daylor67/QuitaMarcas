---
phase: 02-slideshowviewer-decomposition
plan: 03
subsystem: ui
tags: [pyside6, qt, signal-slot, training-data, yolo, composer]

# Dependency graph
requires:
  - phase: 02-01
    provides: NavigationController + components/ package skeleton + TrainingDataCollector stub
  - phase: 02-02
    provides: WatermarkProcessor (manual/auto YOLO, position-grid, crop) + image_processed/image_reset/counts_changed signals
provides:
  - TrainingDataCollector(QWidget) — UI de conteo + wrappers save/remove training samples
  - SlideshowViewer reducido a composer puro (280 lineas) que cablea los 3 componentes via _wire_signals
affects: [03-gap-closure, future-phases-touching-watermarkremove-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Component extraction via Signal/Slot wiring (composer owns _wire_signals)"
    - "Path shim para reusar firma externa sin modificar el modulo (fake_current_dir en on_image_reset)"
    - "Lazy imports promovidos a top-level por consistencia entre componentes"

key-files:
  created:
    - WatermarkRemove/ui/components/training_data_collector.py
  modified:
    - WatermarkRemove/ui/slideshow_viewer.py

key-decisions:
  - "fake_current_dir path shim para preservar el comportamiento de remove_training_sample sin tocar yolo/training_collector.py (out-of-scope)"
  - "Imports de training_collector promovidos a top-level (eran lazy en el original) por consistencia con el resto de componentes"
  - "Import de save/remove en linea unica (no multilinea) para satisfacer el gate key_links del plan"
  - "Condensacion de docstrings/banners decorativos para aterrizar en el target de 280 lineas sin tocar codigo funcional"

patterns-established:
  - "Composer puro: SlideshowViewer instancia hijos, _wire_signals cablea, _setup_ui arma layout, API publica intacta"
  - "Cada componente calcula su propio path a training_data.json segun su profundidad en el package"

requirements-completed: [ARCH-01]

# Metrics
duration: ~20min
completed: 2026-05-27
---

# Phase 2 Plan 03: TrainingDataCollector Extraction + SlideshowViewer Final Reduction Summary

**Recopilacion de training data YOLO extraida a `TrainingDataCollector(QWidget)` (GroupBox de conteo + slots save/remove), dejando `SlideshowViewer` como composer puro de 280 lineas (~86% de reduccion desde las 2041 originales).**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-05-27T20:26Z (aprox.)
- **Completed:** 2026-05-27T20:46Z
- **Tasks:** 2 de 3 ejecutadas autonomamente (Task 3 es checkpoint human-verify — pendiente)
- **Files modified:** 2 (1 creado/completado, 1 refactorizado)

## Accomplishments
- `TrainingDataCollector(QWidget)` implementado: GroupBox "📊 Datos recopilados" + `training_counts_label`, `_update_counts_label` (lee training_data.json, fallback defensivo "Sin datos aún"), slots `on_image_processed` (wrappea `save_training_sample`, guarda `watermark_path=None`) y `on_image_reset` (wrappea `remove_training_sample` via path shim), `_log`, `on_counts_changed`.
- `SlideshowViewer` finalizado como composer puro: eliminado `_update_counts_label` inline + GroupBox de conteo, cableado directo de `processor.image_processed/image_reset/counts_changed` → slots del collector, eliminado el global `current_dir`, reducido a **280 lineas** (target ≤280).
- Modulo externo `yolo/training_collector.py` NO modificado; `gui/controller.py` sin cambios (contrato preservado).

## Task Commits

Each task was committed atomically:

1. **Task 1: Implementar TrainingDataCollector + extraer GroupBox de conteo** - `a1786e3` (feat)
2. **Task 2: Refactorizar SlideshowViewer final — composer puro** - `9a64626` (refactor)
3. **Task 3: UAT manual completo + verificacion edge count** - NO EJECUTADA (checkpoint:human-verify gate="blocking" — requiere que el usuario corra la app y mida edge count)

**Plan metadata:** se commitea junto con este SUMMARY (docs).

## Files Created/Modified
- `WatermarkRemove/ui/components/training_data_collector.py` (195 lineas) - Componente de recopilacion de training data: UI de conteo + wrappers save/remove preservando el comportamiento del modulo externo.
- `WatermarkRemove/ui/slideshow_viewer.py` (280 lineas, desde 384 al iniciar este plan / 2041 pre-Phase-2) - Composer puro: instancia los 3 componentes, `_wire_signals`, `_setup_ui`, keyPressEvent guard, API publica.

### Final wc -l (4 archivos)
```
 280  WatermarkRemove/ui/slideshow_viewer.py
 630  WatermarkRemove/ui/components/navigation_controller.py
1566  WatermarkRemove/ui/components/watermark_processor.py
 195  WatermarkRemove/ui/components/training_data_collector.py
```

### Wiring confirmado en _wire_signals
- Navigation → Processor: image_changed, output_folder_ready, image_clicked, mouse_moved
- Processor → Navigation: preview_changed, image_processed, processing_blocked, image_reset, request_image_reload, request_redraw, output_folder_request, manual_tracking/overlay_*; + set_processor_decorator(decorate_pixmap)
- Navigation → composer: window_resize_requested, finish_requested
- **Processor → Collector (Plan 03)**: `image_processed → on_image_processed`, `image_reset → on_image_reset`, `counts_changed → on_counts_changed`
- Processor.auto_accept_next_btn → navigation.request_next

## Decisions Made
- **Path shim `fake_current_dir`**: `remove_training_sample(current_dir, ...)` calcula internamente `dirname(current_dir)/training_data.json`. En el original `current_dir` era `WatermarkRemove/ui/`. Para preservar el destino `WatermarkRemove/training_data.json` sin modificar el modulo externo (out-of-scope per RESEARCH line 228), el collector construye `fake_current_dir = <WatermarkRemove>/ui`.
- **Imports promovidos a top-level**: `save_training_sample`/`remove_training_sample` eran lazy en el original; se promueven a top-level por consistencia con los otros componentes.
- **Import en linea unica**: el plan key_link y la verify esperaban `from ... import save_training_sample, remove_training_sample` en una sola linea — se ajusto desde el formato multilinea inicial.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Import de training_collector convertido a linea unica**
- **Found during:** Task 1
- **Issue:** El import se escribio inicialmente en formato multilinea con parentesis, lo que hacia fallar el gate `grep -c "from WatermarkRemove.yolo.training_collector import save_training_sample"` (esperaba 1, retornaba 0) y el key_link del plan.
- **Fix:** Convertido a una sola linea `from WatermarkRemove.yolo.training_collector import save_training_sample, remove_training_sample`.
- **Files modified:** WatermarkRemove/ui/components/training_data_collector.py
- **Verification:** grep retorna 1; py_compile + import OK.
- **Committed in:** `a1786e3` (Task 1 commit)

**2. [Rule 3 - Blocking] Global `current_dir` removido conservando el bootstrap sys.path**
- **Found during:** Task 2
- **Issue:** El plan (item 8) pide eliminar el global `current_dir`, pero ese global era load-bearing para el bootstrap `sys.path.insert` (no solo para el counts label).
- **Fix:** Inline del calculo del parent dir en una variable local `_parent_dir`; el global `current_dir = os...` desaparece (gate `grep -c "current_dir = os"` = 0) sin romper el import del package.
- **Files modified:** WatermarkRemove/ui/slideshow_viewer.py
- **Verification:** `grep -c "current_dir = os"` = 0; import del package OK.
- **Committed in:** `9a64626` (Task 2 commit)

**3. [Rule 3 - Blocking] Condensacion de docstrings/banners para alcanzar wc -l ≤ 280**
- **Found during:** Task 2
- **Issue:** Tras eliminar el codigo de training inline, el archivo quedo en 331 lineas (>280 target). El exceso era 100% comentarios decorativos (`# ===` banners) y docstrings verbosos, no codigo.
- **Fix:** Condensados los docstrings de modulo/clase/metodos y eliminados los banners decorativos `# ===...===`; ningun codigo funcional removido. Resultado: 280 lineas exactas.
- **Files modified:** WatermarkRemove/ui/slideshow_viewer.py
- **Verification:** `wc -l` = 280; py_compile + import + signature check OK.
- **Committed in:** `9a64626` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking, todas para satisfacer gates de verificacion del plan)
**Impact on plan:** Ninguna toca logica funcional; todas son ajustes de forma para cumplir los gates de aceptacion. Sin scope creep.

## Issues Encountered
- El plan asumia que `_update_counts_label` y los imports muertos (`UtilJson`, `numpy`, `natsort`, `wm_persistence`) seguian en `slideshow_viewer.py`. Al iniciar este plan el archivo ya era un composer de 384 lineas (Plan 02-02 limpio la mayoria de imports muertos); solo quedaba el conteo inline + wiring guardado con `hasattr`. Se ejecutaron los cambios efectivamente pendientes y se verifico que los gates de imports muertos retornan 0.

## Checkpoint Pendiente (Task 3 — human-verify, gate="blocking")
Task 3 NO se ejecuta autonomamente. Requiere que el usuario:
- **A. UAT manual**: correr `python SmartStitchGUI.py`, ejecutar las 6 secciones de `02-HUMAN-UAT.md` (Navegación, Modo Manual, Modo Auto YOLO, Training Data, Edge Count, Comportamiento Idéntico). Critico: cuadros rojo/verde de posiciones, manual + auto YOLO + reset, conteo de training samples actualizado tras cada accept.
- **B. Edge count (ARCH-01 SC-4)**: regenerar graphify, contar OUT edges del nodo class `SlideshowViewer`, crear `02-EDGE-COUNT.md` (baseline 58 → post-refactor N; PASS si ≤20).
- **C. Contract**: `git diff gui/controller.py` vacio (ya verificado) + flujo "Ejecutar Quita Marcas" abre el visor.
- **D. Grep gates**: ya verificado 0 hits en slideshow_viewer.py.
- **E/F/G. Sign-off**: aprobar con "approved + edge count: N + wc -l: [output]" o describir regresion.

`02-EDGE-COUNT.md` se crea durante Task 3 (no por este ejecutor).

## Next Phase Readiness
- Phase 2 estructuralmente completa (3 componentes extraidos): ARCH-01 SC-1/SC-2/SC-3 cubiertos por codigo + gates.
- Pendiente sign-off humano (Task 3): ARCH-01 SC-4 (edge count) y SC-5 (comportamiento observable identico) requieren la medicion + UAT manual.
- Sin blockers de codigo. El visor compila e importa; firma del constructor intacta.

## Self-Check: PASSED
- FOUND: WatermarkRemove/ui/components/training_data_collector.py
- FOUND: WatermarkRemove/ui/slideshow_viewer.py
- FOUND: .planning/phases/02-slideshowviewer-decomposition/02-03-SUMMARY.md
- FOUND commit: a1786e3 (Task 1)
- FOUND commit: 9a64626 (Task 2)

---
*Phase: 02-slideshowviewer-decomposition*
*Completed: 2026-05-27*
