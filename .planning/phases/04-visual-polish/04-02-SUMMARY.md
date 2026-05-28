---
phase: 04-visual-polish
plan: 02
subsystem: ui
tags: [pyside6, qstackedwidget, qbuttongroup, layout, mode-selector]

requires:
  - phase: 04-visual-polish
    plan: 01
    provides: "QSplitter horizontal + WmPersistenceService.set/get_splitter_sizes + _create_controls_panel sin scroll wrapper"
provides:
  - "NavigationController.create_nav_controls_widget() — QGroupBox 'Navegación' independiente del scroll area"
  - "WatermarkProcessor.panel_seleccion / panel_recorte / panel_auto — QWidgets para QStackedWidget externo"
  - "WatermarkProcessor.set_mode(index) — selector de modo invocado por QButtonGroup externo"
  - "SlideshowViewer._create_controls_panel — cuatro secciones (D-04) con QButtonGroup + QStackedWidget"
  - "_check_yolo_availability — deshabilita botón Automático cuando no hay .onnx en yolo/ (D-08)"
affects: [04-03-PLAN, gui/stylesheet]

tech-stack:
  added: [PySide6.QtWidgets.QStackedWidget, PySide6.QtWidgets.QButtonGroup]
  patterns:
    - "Reparenting controlado: navigation cede sus widgets de nav al composer via método público (create_nav_controls_widget)"
    - "Paneles expuestos como atributos para QStackedWidget externo (WatermarkProcessor ya no es widget visible)"
    - "Mode selector via QButtonGroup exclusivo en lugar de checkboxes ocultos (D-05)"

key-files:
  created: []
  modified:
    - WatermarkRemove/ui/components/navigation_controller.py
    - WatermarkRemove/ui/components/watermark_processor.py
    - WatermarkRemove/ui/slideshow_viewer.py

key-decisions:
  - "Reusar seleccion_group / auto_group como panel_seleccion / panel_auto en lugar de duplicar widgets — Qt reparenta automáticamente al agregar al QStackedWidget"
  - "panel_recorte se construye fresh con QWidget+QVBoxLayout porque sus widgets viven en seleccion_group; al moverlos a recorte_layout Qt los reparenta fuera del grupo de selección"
  - "Conservar auto_mode_checkbox y crop_mode_checkbox como atributos ocultos — _toggle_auto_mode/_toggle_crop_mode siguen referenciándolos en lógica interna; eliminarlos rompería invariantes preservados de Phase 3"
  - "_check_yolo_availability verifica el archivo .onnx en disco (no importa auto_detector) — la importación del módulo no falla sin el modelo; el error sólo aparece al llamar detect_watermarks()"
  - "QGroupBox 'Navegación' aloja finish/cancel buttons dentro del MISMO group del create_nav_controls_widget — evita duplicar el título 'Navegación' del Plan 04-01"

patterns-established:
  - "Composer-driven mode switching: el QButtonGroup vive en el composer (slideshow_viewer), no en el processor — el processor sólo expone set_mode() como API pública"
  - "Widget exposure via attribute: WatermarkProcessor expone sub-widgets (panel_*) en lugar de ser visible él mismo — permite que el composer los reorganice"

requirements-completed: [UI-02]

duration: ~4min
completed: 2026-05-28
---

# Phase 04 Plan 02: Mode selector + QStackedWidget en panel de controles — Summary

**Panel izquierdo del SlideshowViewer pasa de un layout plano con checkboxes ocultos a cuatro secciones jerárquicas (D-04) con un selector de modo tipo tabs (D-05) y un QStackedWidget que cambia entre Selección / Recorte / Automático (D-06, D-07, D-08).**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-05-28T13:15:36Z
- **Completed:** 2026-05-28T13:20:01Z (commit 2a835d8)
- **Tasks:** 3 / 3 completed
- **Files modified:** 3

## Accomplishments

- `NavigationController` expone `create_nav_controls_widget()` — devuelve un `QGroupBox("Navegación")` con `counter_label` / `filename_label` / `prev_btn` / `next_btn` reparenteados, y oculta el `info_group` original que queda vacío.
- `WatermarkProcessor` expone tres paneles independientes (`panel_seleccion`, `panel_recorte`, `panel_auto`) y un método `set_mode(index: int)` que reemplaza los checkboxes internos `auto_mode_checkbox` y `crop_mode_checkbox` como mecanismo de cambio de modo (D-06).
- El checkbox `opciones_avanzadas` cambia su texto de `"Modo selección manual"` a `"Avanzado"` (D-07).
- `SlideshowViewer._create_controls_panel` se reescribe completamente con las cuatro secciones de D-04:
  1. Grupo Navegación (con `finish/cancel` integrados dentro del mismo `QGroupBox`).
  2. Selector de modo: `QButtonGroup` exclusivo con tres `QPushButton` checkables `[Selección][Recorte][Automático]` (D-05).
  3. `QStackedWidget` con tres páginas (`processor.panel_seleccion/recorte/auto`).
  4. Grupo Training Data (`TrainingDataCollector`).
- `_on_mode_changed(idx)` slot conecta `QButtonGroup.idClicked` → `setCurrentIndex(idx)` + `processor.set_mode(idx)`.
- `_check_yolo_availability` deshabilita el botón `[Automático]` cuando no hay archivos `.onnx` bajo `WatermarkRemove/yolo/` (D-08).

## Task Commits

Cada tarea se commiteó atómicamente sobre el worktree `worktree-agent-a0273a1341c2b96fe`:

1. **Task 1: Separar NavigationController — extraer `create_nav_controls_widget()`** — `910e10e` (feat)
2. **Task 2: Refactorizar WatermarkProcessor — exponer 3 paneles y `set_mode()`** — `109300f` (feat)
3. **Task 3: Ensamblar panel de controles reorganizado en slideshow_viewer** — `2a835d8` (feat)

## Files Created/Modified

- `WatermarkRemove/ui/components/navigation_controller.py` — `+38` líneas: una línea agregada en `_setup_ui` (`self._nav_info_group = info_group`) y un método nuevo `create_nav_controls_widget()`. Ningún método existente fue modificado.
- `WatermarkRemove/ui/components/watermark_processor.py` — `+82 / -2` líneas: cambio de texto del checkbox `opciones_avanzadas` (`"Avanzado"`), bloque al final de `_setup_ui` que crea los tres paneles + remueve widgets del outer layout + oculta los checkboxes de modo, y método nuevo `set_mode()` al final de la clase.
- `WatermarkRemove/ui/slideshow_viewer.py` — `+88 / -17` líneas: import de `QStackedWidget` + `QButtonGroup`, reescritura completa de `_create_controls_panel`, métodos nuevos `_on_mode_changed` y `_check_yolo_availability`.

## Decisions Made

| Decisión | Razón |
|----------|-------|
| `panel_seleccion = self.seleccion_group` (no nuevo `QWidget`) | Mover todos los widgets de `seleccion_group` a un nuevo `QWidget` requeriría reparentearlos uno por uno; aprovechar el `QGroupBox` ya construido es mínimamente invasivo. |
| `panel_recorte` se construye nuevo con `QVBoxLayout` | Los widgets de crop viven en `seleccion_group`; al agregarlos a `recorte_layout` Qt los reparenta automáticamente, lo cual logra el aislamiento del modo recorte. |
| Conservar `auto_mode_checkbox` y `crop_mode_checkbox` ocultos | `_toggle_auto_mode` y `_toggle_crop_mode` aún los referencian; eliminarlos rompería invariantes preservados de Phase 3 (las verificaciones `if self.opciones_avanzadas.isChecked(): self.opciones_avanzadas.setChecked(False)` siguen vivas). |
| `_check_yolo_availability` glob en disco en vez de importar `auto_detector` | La importación de `auto_detector` no falla cuando falta el `.onnx`; el error sólo aparece dentro de `detect_watermarks()`. Verificar el archivo es más barato y se ejecuta una vez al iniciar. |
| `finish_btn` / `cancel_btn` van dentro del MISMO `QGroupBox("Navegación")` que crea `create_nav_controls_widget` | El plan especifica que el Grupo Navegación contiene prev/next + contador + filename + finish/cancel; tener un segundo `QGroupBox` duplicaría el título y rompería D-04. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Worktree creado desde `main` en vez de `refactorizacion-WatermrkRemove`**

- **Found during:** Carga inicial, antes de Task 1.
- **Issue:** El worktree contenía el código pre-Phase-3 (sin `WatermarkRemove/services/` ni `WatermarkRemove/ui/components/`). Esto reproduce literalmente la deviation Rule 3 #1 del Plan 04-01.
- **Fix:** `git reset --hard refactorizacion-WatermrkRemove` sincroniza el worktree con HEAD del branch de trabajo (commit `22faade docs(phase-04): update tracking after wave 1 (04-01 complete)`). No se tocó ninguna rama protegida; el branch del worktree sigue siendo `worktree-agent-a0273a1341c2b96fe`.
- **Files modified:** Ninguno (estado del worktree, no del repo).
- **Verification:** `git log --oneline -5` muestra `22faade` como HEAD; `ls WatermarkRemove/services/` y `WatermarkRemove/ui/components/` listan archivos.
- **Committed in:** N/A — operación local del worktree previa al primer commit.

**2. [Rule 3 — Blocking issue] Verificación con `open(...).read()` falla en Windows con `UnicodeDecodeError`**

- **Found during:** Verificación automática de Task 1.
- **Issue:** El verify del plan usa `open('archivo.py').read()` sin `encoding=` — en Windows Python 3.13 usa `cp1252` por defecto y los caracteres acentuados del docstring (`ñ`, `ó`) lanzan `UnicodeDecodeError`.
- **Fix:** Agregar `encoding='utf-8'` a los `open(...)` en los scripts de verificación. No es un cambio del código del producto, sino del wrapper de test.
- **Files modified:** Ninguno (sólo el comando de verificación).
- **Verification:** Las cuatro líneas del bloque `<verification>` del plan corren OK con la corrección: `COMPILE_OK`, `PANELS_OK`, `NAV_SPLIT_OK`, `STACK_OK`.
- **Committed in:** N/A — fix de entorno.

No hubo deviations Rule 1 (bugs), Rule 2 (missing critical functionality) ni Rule 4 (cambios arquitectónicos). El refactor sigue el plan al pie de la letra y todas las constraints (preservación de signals, `decorate_pixmap`, checkboxes ocultos, API pública) quedan respetadas.

## Verification

**Compilación y acceptance criteria (bloque `<verification>` del plan):**

```
python -m py_compile WatermarkRemove/ui/components/navigation_controller.py \
                    WatermarkRemove/ui/components/watermark_processor.py \
                    WatermarkRemove/ui/slideshow_viewer.py
→ COMPILE_OK

# watermark_processor.py
panel_seleccion ✓, panel_recorte ✓, panel_auto ✓, set_mode ✓ → PANELS_OK

# navigation_controller.py
create_nav_controls_widget ✓ → NAV_SPLIT_OK

# slideshow_viewer.py
QStackedWidget ✓, QButtonGroup ✓, _on_mode_changed ✓, _check_yolo_availability ✓
auto_mode_checkbox.stateChanged NOT in src ✓ → STACK_OK
```

**Integración bajo `QApplication` offscreen** (más estricto que el plan):

- `IMPORT_OK` — el módulo `slideshow_viewer` carga sin errores con los tres componentes hijos.
- `CONSTRUCT_OK` — `SlideshowViewer(tmp_folder)` se instancia.
- `STACK_3_PAGES_OK` — `_mode_stack.count() == 3`, `currentIndex() == 0`.
- `SELECCION_DEFAULT_OK` — el botón `[Selección]` está checked al iniciar.
- `PROCESSOR_PANELS_OK` — los tres `panel_*` existen como atributos del processor.
- `SET_MODE_OK` — `set_mode(1)` activa `crop_mode_enabled`; `set_mode(0)` lo desactiva y deja `auto_mode_enabled = False`.
- `YOLO_CHECK_OK` — con el modelo `.onnx` presente en este worktree, el botón `[Automático]` queda habilitado.

## Threat Surface

Sin nuevos flags. El plan declaró:

- `T-04-03` (Tampering en `_check_yolo_availability`): `accept` — sólo lectura de filesystem con `glob('*.onnx')` envuelto en `try/except`; un error deja el botón habilitado y el usuario descubre el problema al intentar detectar.
- `T-04-04` (Tampering en `set_mode`): `accept` — `mode_index` viene del `QButtonGroup` (acotado a `{0,1,2}`); índices fuera de rango caen al `pass` implícito.
- `T-04-05` (DoS por widget reparenting doble): `mitigate` — `create_nav_controls_widget()` se documenta como "solo debe llamarse una vez por instancia" y en el flujo real lo invoca únicamente `_create_controls_panel`.
- `T-04-SC` (paquetes maliciosos): `accept` — no se instaló ningún paquete.

## Known Stubs

Ninguno. Los tres paneles del `QStackedWidget` muestran widgets reales conectados a la lógica existente:

- `panel_seleccion` = el `QGroupBox("Selección")` con todos sus combos / checkboxes / botones funcionales.
- `panel_recorte` = `QWidget` con los widgets de crop (`crop_pixels_input`, `crop_invert_checkbox`, `crop_apply_btn`) cuyo slot `_apply_crop` sigue cableado.
- `panel_auto` = el `QGroupBox("Detección automática")` con `detections_list`, `auto_offset_x/y`, `auto_delete_btn`, `auto_redetect_btn`, `auto_accept_btn`, `auto_accept_next_btn` — todos siguen conectados a sus slots originales.

## Success Criteria

- [x] `NavigationController` expone `create_nav_controls_widget()` que retorna un `QGroupBox("Navegación")` con los widgets de instancia reparentados.
- [x] `WatermarkProcessor` expone `panel_seleccion`, `panel_recorte`, `panel_auto` y `set_mode(index)`.
- [x] `SlideshowViewer._create_controls_panel()` ensambla las 4 secciones con `QButtonGroup` + `QStackedWidget`.
- [x] `_check_yolo_availability()` deshabilita el botón `[Automático]` si no hay `.onnx` en `yolo/`.
- [x] Todos los signal/slot wiring existentes en `_wire_signals()` siguen funcionando intactos (verificado al instanciar `SlideshowViewer` y operar `set_mode`).

## Self-Check: PASSED

- **Files exist:**
  - `WatermarkRemove/ui/components/navigation_controller.py` ✓
  - `WatermarkRemove/ui/components/watermark_processor.py` ✓
  - `WatermarkRemove/ui/slideshow_viewer.py` ✓
  - `.planning/phases/04-visual-polish/04-02-SUMMARY.md` ✓ (este archivo)
- **Commits exist (verificado con `git log --oneline -5`):**
  - `910e10e` ✓ Task 1 (NavigationController create_nav_controls_widget)
  - `109300f` ✓ Task 2 (WatermarkProcessor paneles + set_mode)
  - `2a835d8` ✓ Task 3 (SlideshowViewer QStackedWidget + QButtonGroup)
