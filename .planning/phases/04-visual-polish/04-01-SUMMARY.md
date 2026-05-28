---
phase: 04-visual-polish
plan: 01
subsystem: ui
tags: [pyside6, qsplitter, persistence, layout, wm_settings]

requires:
  - phase: 03-logic-widget-separation
    provides: "SlideshowViewer composer puro + WmPersistenceService singleton + barrel WatermarkRemove/services"
provides:
  - QSplitter horizontal redimensionable reemplaza el QHBoxLayout con ancho fijo 280px
  - Proporción inicial 35%/65% (controles/visor) configurable y persistente
  - Persistencia round-trip de splitter_sizes via WmPersistenceService
  - closeEvent + _on_splitter_moved garantizan que el último tamaño quede grabado
affects: [04-02-PLAN, 04-03-PLAN, gui/controller, gui/stylesheet]

tech-stack:
  added: [PySide6.QtWidgets.QSplitter]
  patterns:
    - "Persistencia de geometría UI vía WmPersistenceService (continuación del patrón de Phase 1)"
    - "Eliminar setStyleSheet inline en widgets que serán restilizados por QSS global en Plan 04-03"

key-files:
  created: []
  modified:
    - WatermarkRemove/services/wm_persistence.py
    - WatermarkRemove/ui/slideshow_viewer.py

key-decisions:
  - "QSplitter horizontal directo en lugar de splitter anidado — simplicidad sobre granularidad"
  - "Default [315, 585] coincide con el 35/65 sobre los 900px iniciales de la ventana — proporción explícita"
  - "Persistir tanto en splitterMoved como en closeEvent — protección contra splitterMoved que no se emite si el usuario cierra sin tocar el splitter"
  - "Eliminar setStyleSheet inline de finish_btn/cancel_btn ya en Plan 04-01 (no esperar a 04-03) para evitar conflictos con el QSS global futuro"

patterns-established:
  - "Domain-named persistence (WmPersistenceService) en lugar de UtilJson directo en el composer — el composer no conoce el archivo JSON"
  - "Defensive validation en getters (isinstance + int cast) — protege contra wm_settings.json corrupto (T-04-01 mitigation)"

requirements-completed: [UI-01]

duration: ~25min
completed: 2026-05-28
---

# Phase 04 Plan 01: Splitter redimensionable y persistente — Summary

**Layout principal del SlideshowViewer pasa de QHBoxLayout con ancho fijo 280 px a QSplitter horizontal con persistencia entre sesiones (UI-01).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-05-28T13:06:53Z (plan execution kickoff)
- **Completed:** 2026-05-28T13:31:00Z (commit a49f079)
- **Tasks:** 2 / 2 completed
- **Files modified:** 2

## Accomplishments

- WmPersistenceService gana `get_splitter_sizes(default)` / `set_splitter_sizes(sizes)` con validación defensiva contra valores corruptos en JSON (mitigación T-04-01).
- SlideshowViewer reemplaza el `QHBoxLayout` con ancho fijo por un `QSplitter` horizontal de proporción inicial `[315, 585]` (35%/65%), redimensionable en runtime por el usuario.
- La proporción del splitter se persiste vía dos rutas: `splitterMoved` (cada arrastre) y `closeEvent` (al cerrar el diálogo, captura cambios programáticos).
- Se eliminan las hojas de estilo inline en `finish_btn` / `cancel_btn` para preparar Plan 04-03, que aplicará el QSS global con `objectName`.
- El título del QGroupBox de navegación pasa de `"✳️ Navegación"` a `"Navegación"` (D-09: sin emojis en títulos).

## Task Commits

Cada tarea se commiteó atómicamente sobre el worktree:

1. **Task 1: Extender WmPersistenceService con get_splitter_sizes / set_splitter_sizes** — `af5eda6` (feat)
2. **Task 2: Reemplazar QHBoxLayout fijo por QSplitter en SlideshowViewer** — `a49f079` (feat)

## Files Created/Modified

- `WatermarkRemove/services/wm_persistence.py` — `+11` líneas: dos métodos nuevos al final de la clase. No se modifican los métodos existentes (crop pixels, watermark folder).
- `WatermarkRemove/ui/slideshow_viewer.py` — `+34 / -30` líneas: refactor de `_setup_ui` y `_create_controls_panel`, nuevos `_on_splitter_moved` + `closeEvent`, import de `QSplitter` y del singleton `wm_persistence`, eliminación de `QScrollArea` y de `setStyleSheet` inline en finish/cancel buttons.

## Decisions Made

| Decisión | Razón |
|----------|-------|
| QSplitter horizontal único (no anidado) | El plan solo redistribuye dos paneles; un splitter anidado introduciría complejidad sin beneficio. |
| Persistir en `splitterMoved` Y `closeEvent` | `splitterMoved` no se emite si el usuario nunca toca el splitter; `closeEvent` garantiza al menos un escritura por sesión. |
| Default `[315, 585]` hardcoded | Coincide con la proporción 35/65 sobre 900 px iniciales; valores pasados por argumento permiten override en pruebas. |
| Eliminar `setStyleSheet` inline ya en Plan 04-01 | Plan 04-03 va a restilizar via QSS global con `setObjectName()`; mantener los estilos inline aquí los haría persistir y conflictuar. |
| Conservar `self.controls_panel_width = 280` | `NavigationController._request_window_resize` lo usa para sugerir un ancho de ventana al cambiar de imagen — el plan lo declara explícitamente como invariante. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Worktree creado desde rama `main` en vez de `refactorizacion-WatermrkRemove`**

- **Found during:** Carga inicial (antes de Task 1).
- **Issue:** El worktree contenía el código pre-Phase-3 (`SlideshowViewer` monolítico de 1574 líneas, sin `WatermarkRemove/services/` ni `WatermarkRemove/ui/components/`). El plan 04-01 asume el composer puro post-Phase-3 con singletons `wm_persistence` y componentes hijos.
- **Fix:** `git reset --hard refactorizacion-WatermrkRemove` para sincronizar el worktree con el HEAD de la rama de trabajo (commit `a10a9ce`). No se modifica ninguna rama protegida y el branch del worktree (`worktree-agent-aa02a8b0fb22a0b81`) sigue siendo independiente.
- **Files modified:** Ninguno (solo state del worktree, no del repo).
- **Verification:** `git log --oneline -3` muestra `a10a9ce docs(state): record phase 4 context session` como HEAD; `ls WatermarkRemove/services/` lista los servicios; `ls WatermarkRemove/ui/components/` lista los componentes.
- **Committed in:** N/A — operación local del worktree previa al primer commit.

**2. [Rule 3 — Blocking issue] Directorio `core/__settings__/` faltante en el worktree**

- **Found during:** Verificación integration de Task 1.
- **Issue:** El primer `set_splitter_sizes([315,585])` falló con `FileNotFoundError` porque `UtilJson` intenta escribir `core/__settings__/wm_settings.json` pero el directorio no existe en el worktree limpio.
- **Fix:** `mkdir -p core/__settings__`. El directorio es runtime-only y `__settings__/` ya está en `.gitignore`, por lo que no se contamina el repo.
- **Files modified:** Ninguno (directorio runtime ignorado por git).
- **Verification:** Segundo round-trip retorna `[315, 585]` + `SPLITTER_PERSIST_OK`.
- **Committed in:** N/A — fix de entorno, no de código.

**3. [Rule 3 — Blocking issue] Docstring contenía la cadena `QScrollArea` y el test estricto del plan la rechaza**

- **Found during:** Verificación de acceptance criteria de Task 2.
- **Issue:** El plan exige `assert 'QScrollArea' not in src` (cadena cruda) y el docstring de `_create_controls_panel` decía "Sin QScrollArea (D-03) ...".
- **Fix:** Reescribir el docstring como "Sin scroll wrapper (D-03) ..." — mismo significado semántico, sin contaminar la cadena con el nombre de la clase eliminada.
- **Files modified:** `WatermarkRemove/ui/slideshow_viewer.py` (mismo archivo de Task 2).
- **Verification:** El test `LAYOUT_OK` pasa.
- **Committed in:** `a49f079` (incluido en el commit principal de Task 2).

No hubo deviations Rule 1 (bugs), Rule 2 (missing critical functionality) ni Rule 4 (cambios arquitectónicos).

## Verification

Comandos finales del plan ejecutados, todos OK:

```
python -m py_compile WatermarkRemove/services/wm_persistence.py WatermarkRemove/ui/slideshow_viewer.py
→ COMPILE_OK

python -c "...; s.set_splitter_sizes([300,600]); print(s.get_splitter_sizes([315,585]))"
→ [300, 600]
→ SPLITTER_PERSIST_OK

python -c "...; assert 'QSplitter' in src; assert 'setSizes' in src; assert 'setFixedWidth' not in src; assert 'QScrollArea' not in src"
→ LAYOUT_OK
```

Además, prueba de importación a nivel módulo con `QApplication` viva: `MODULE_LOAD_OK` (verifica que `QSplitter`, `wm_persistence`, `closeEvent` y `_on_splitter_moved` están todos disponibles en `SlideshowViewer`).

## Threat Surface

Sin nuevos flags. El plan declaró `T-04-01` (Tampering en `get_splitter_sizes`) — la mitigación quedó implementada (`isinstance(value, list)` + `int(v)` cast). `T-04-02` (DoS por valores extremos en `setSizes`) quedó como `accept` por decisión del plan; el comportamiento de Qt internamente sanitiza la suma cero o negativa sin crash. `T-04-SC` (paquetes maliciosos) no aplica: no se instaló ningún paquete.

## Known Stubs

Ninguno. La funcionalidad está completamente cableada — el splitter renderiza widgets reales (`WatermarkProcessor`, `NavigationController`, `TrainingDataCollector`) ya existentes desde Phase 03.

## Success Criteria

- [x] `WmPersistenceService` tiene `get_splitter_sizes` y `set_splitter_sizes`; el round-trip JSON funciona.
- [x] `SlideshowViewer` usa `QSplitter` como layout principal con `setSizes([315, 585])` por defecto.
- [x] No hay `setFixedWidth` ni `QScrollArea` wrapper en el panel de controles.
- [x] `closeEvent` y `_on_splitter_moved` persisten los sizes vía `wm_persistence`.
- [x] Ningún método de la API pública (`get_approved`, `get_output_folder`, `has_processed_images`) fue modificado.

## Self-Check: PASSED

- **Files exist:**
  - `WatermarkRemove/services/wm_persistence.py` ✓
  - `WatermarkRemove/ui/slideshow_viewer.py` ✓
  - `.planning/phases/04-visual-polish/04-01-SUMMARY.md` ✓ (este archivo)
- **Commits exist:**
  - `af5eda6` ✓ Task 1 (wm_persistence)
  - `a49f079` ✓ Task 2 (slideshow_viewer)
