---
phase: 04-visual-polish
plan: 03
subsystem: ui
tags: [pyside6, qss, stylesheet, objectname, theming, visual-polish]

requires:
  - phase: 04-visual-polish
    plan: 01
    provides: "QSplitter + WmPersistenceService.set/get_splitter_sizes (setStyleSheet inline ya removidos de finish_btn/cancel_btn)"
  - phase: 04-visual-polish
    plan: 02
    provides: "QStackedWidget + QButtonGroup + WatermarkProcessor.panel_seleccion/recorte/auto (mode-btn ya tiene setObjectName('wm-mode-btn'))"
provides:
  - "gui/stylesheet.py expone WM_STYLE_SHEET con reglas QSS para todos los objectName wm-*"
  - "load_styling() retorna load_stylesheet('dark') + WM_STYLE_SHEET (D-12, D-14)"
  - "Componentes del SlideshowViewer sin setStyleSheet() inline (excepto 2 overlays flotantes — D-13)"
  - "Widgets con setObjectName() consistente: wm-counter, wm-filename, wm-image-scroll, wm-image-label, wm-training-counts, wm-accept-btn, wm-revert-btn, wm-cancel-btn, wm-finish-btn, wm-reset-btn, wm-crop-apply-btn, wm-save-next-btn, wm-mode-btn"
  - "Acento teal #26EE9F consistente en todo el WatermarkRemove — sin azul #2196F3 ni morado #9C27B0 hardcodeados"
affects: [gui/controller, futuras phases que estilicen widgets]

tech-stack:
  added: []
  patterns:
    - "QSS global por objectName en lugar de setStyleSheet() inline por componente (D-12)"
    - "Namespace 'wm-' para todos los objectNames de WatermarkRemove — evita colisiones con widgets de SmartStitchGUI"
    - "Colores semánticos consistentes: verde Accept, rojo Revert/Cancel, teal Finish/CropApply, naranja Reset"
    - "Excepción documentada para overlays flotantes con RGBA transparente (zoom_overlay, manual_overlay)"

key-files:
  created: []
  modified:
    - gui/stylesheet.py
    - WatermarkRemove/ui/components/navigation_controller.py
    - WatermarkRemove/ui/components/watermark_processor.py
    - WatermarkRemove/ui/components/training_data_collector.py
    - WatermarkRemove/ui/slideshow_viewer.py

key-decisions:
  - "WM_STYLE_SHEET vive en gui/stylesheet.py (no en módulo separado) — facilita que load_styling() lo concatene sin import adicional"
  - "Conservar LIGHT_STYLE_SHEET intacta (no usada en producción) — eliminarla quedó fuera de scope del plan"
  - "next_btn y prev_btn NO reciben objectName — usan estilo neutro del dark theme; agregar wm-finish-btn al next_btn confundiría semántica (next ≠ finalizar)"
  - "auto_accept_btn comparte wm-accept-btn con accept_btn (mismo color verde semántico — ambos son 'aceptar')"
  - "auto_accept_next_btn usa wm-save-next-btn (teal) en lugar del azul #4c7faf hardcodeado — alinea con el acento del proyecto"

patterns-established:
  - "QSS global con namespace wm-* es la única vía permitida para estilo persistente; setStyleSheet() inline solo para overlays con RGBA dinámico (D-13)"
  - "Para evolución futura: agregar widget nuevo al SlideshowViewer → asignar setObjectName('wm-<rol>') + agregar regla en WM_STYLE_SHEET"

requirements-completed: [UI-03]

duration: ~3min
completed: 2026-05-28
---

# Phase 04 Plan 03: QSS global con WM_STYLE_SHEET — Summary

**Todos los `setStyleSheet()` inline hardcodeados en los componentes del SlideshowViewer se reemplazan por reglas QSS namespaced en `gui/stylesheet.py`, asignando `setObjectName('wm-*')` a cada widget que necesita estilo específico (UI-03, D-12, D-13, D-14).**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-28T13:25:33Z (plan execution kickoff)
- **Completed:** 2026-05-28T13:27:56Z (commit f95bc34)
- **Tasks:** 2 / 2 completed
- **Files modified:** 5

## Accomplishments

- `gui/stylesheet.py` define `WM_STYLE_SHEET` con 12 bloques de reglas QSS namespaced bajo el prefijo `wm-*`:
  - Labels: `#wm-counter` (teal), `#wm-filename` (fondo oscuro sutil), `#wm-image-label` (fondo 2b2b2b), `#wm-training-counts` (gris monospace).
  - ScrollArea: `#wm-image-scroll` (borde 2px + fondo 2b2b2b).
  - Mode selector: `#wm-mode-btn` con estados `:checked`, `:hover:!checked:!disabled` y `:disabled` (highlight teal en activo).
  - Botones semánticos: `#wm-accept-btn` (verde #4CAF50), `#wm-revert-btn`/`#wm-cancel-btn` (rojo #f44336), `#wm-finish-btn` y `#wm-crop-apply-btn`/`#wm-save-next-btn` (teal #26EE9F), `#wm-reset-btn` (naranja #FF9800).
- `load_styling()` ahora retorna `load_stylesheet('dark') + WM_STYLE_SHEET` (antes retornaba solo el dark theme con un comentario `#+ LIGHT_STYLE_SHEET` colgando).
- `navigation_controller.py`: eliminados 6 `setStyleSheet()` inline (counter_label, filename_label, prev_btn, next_btn, scroll, image_label) y agregados `setObjectName()` en counter (`wm-counter`), filename (`wm-filename`), scroll (`wm-image-scroll`) e image_label (`wm-image-label`). Conservados intactos `zoom_overlay_label` y `manual_overlay_label` (overlays RGBA — excepción D-13).
- `watermark_processor.py`: eliminados 6 `setStyleSheet()` inline (crop_apply_btn, reset_btn, accept_btn, revert_btn, auto_accept_btn, auto_accept_next_btn) y agregados `setObjectName()` correspondientes. `auto_accept_btn` comparte `wm-accept-btn` con `accept_btn` (mismo color semántico).
- `training_data_collector.py`: eliminado 1 `setStyleSheet()` inline en `training_counts_label` y agregado `setObjectName('wm-training-counts')`.
- `slideshow_viewer.py`: agregados `setObjectName()` a `finish_btn` (`wm-finish-btn`) y `cancel_btn` (`wm-cancel-btn`). No quedaban `setStyleSheet()` inline residuales (ya fueron eliminados en Plan 04-01).

## Task Commits

Cada tarea se commiteó atómicamente sobre el worktree `worktree-agent-a1257c7f0ce8fce15`:

1. **Task 1: Agregar WM_STYLE_SHEET a gui/stylesheet.py y actualizar load_styling()** — `12265ba` (feat)
2. **Task 2: Eliminar setStyleSheet() inline y agregar setObjectName() en los 4 componentes** — `f95bc34` (feat)

## Files Created/Modified

- `gui/stylesheet.py` — `+125 / -1` líneas: bloque `WM_STYLE_SHEET = """..."""` insertado entre `LIGHT_STYLE_SHEET` y `load_styling()`; cambio del return de `load_styling()` para concatenar `WM_STYLE_SHEET`.
- `WatermarkRemove/ui/components/navigation_controller.py` — `+4 / -10` líneas: eliminados 6 inline setStyleSheet, agregados 4 setObjectName (prev_btn y next_btn quedan sin objectName — heredan estilo neutro del dark theme).
- `WatermarkRemove/ui/components/watermark_processor.py` — `+6 / -12` líneas: eliminados 6 inline setStyleSheet, agregados 6 setObjectName.
- `WatermarkRemove/ui/components/training_data_collector.py` — `+1 / -3` líneas: eliminado 1 inline setStyleSheet, agregado 1 setObjectName.
- `WatermarkRemove/ui/slideshow_viewer.py` — `+2 / -0` líneas: agregados 2 setObjectName (finish_btn, cancel_btn). Sin eliminaciones — el plan ya partió del estado limpio post-04-01.

## Decisions Made

| Decisión | Razón |
|----------|-------|
| `WM_STYLE_SHEET` vive en `gui/stylesheet.py` (no en módulo aparte) | El plan especifica que `load_styling()` debe concatenarlo; mantenerlo en el mismo módulo evita un import adicional y mantiene cohesión del subsistema de styling. |
| Conservar `LIGHT_STYLE_SHEET` intacta | El plan instruye explícitamente "no eliminarla. Solo cambia `load_styling()`" — la constante queda definida pero sin uso para que un futuro plan de toggle dark/light pueda reactivarla sin reescribir el QSS. |
| `prev_btn` y `next_btn` sin `setObjectName` | El plan explícitamente lo descarta: usar estilo neutro del dark theme evita confundir semántica (next ≠ finalizar). |
| `auto_accept_btn` reusa `wm-accept-btn` | Ambos son "aceptar" semánticamente; el plan especifica esa reutilización para mantener consistencia visual del color verde de "acción positiva". |
| `auto_accept_next_btn` usa `wm-save-next-btn` (teal) en lugar de azul `#4c7faf` original | El plan reemplaza el azul hardcodeado por el acento teal del proyecto — alinea con la decisión D-12 de unificar la paleta. |
| Conservar `setStyleSheet` en `zoom_overlay_label` y `manual_overlay_label` | D-13 excepción explícita: ambos usan RGBA con transparencia (`rgba(0,0,0,180)`, `rgba(33,150,243,50)`) que es semánticamente un overlay flotante; expresar la misma semántica en QSS global sería más frágil. |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 — Blocking issue] Worktree creado desde commit muy antiguo sin `.planning/` ni código post-Phase-3**

- **Found during:** Carga inicial, antes de Task 1.
- **Issue:** El worktree `worktree-agent-a1257c7f0ce8fce15` arrancó en commit `e58fe2b` (chore: Actualización v3.2 — código pre-Phase-3, sin `.planning/`, sin `WatermarkRemove/ui/components/`, sin `WatermarkRemove/services/`). El plan 04-03 requiere los 3 componentes hijos del SlideshowViewer y el módulo `gui/stylesheet.py` actualizado por las Phases 1-3.
- **Fix:** `git reset --hard refactorizacion-WatermrkRemove` para sincronizar con el HEAD del branch de trabajo (commit `d6794e8 docs(phase-04): update tracking after wave 2 (04-02 complete)`). Esto reproduce literalmente las deviations Rule 3 #1 de Plans 04-01 y 04-02 — patrón recurrente del worktree-agent sandbox de Claude Code.
- **Files modified:** Ninguno (estado del worktree, no del repo).
- **Verification:** `git log --oneline -3` muestra `d6794e8` como HEAD; los archivos de componentes existen; `gui/stylesheet.py` carga sin error.
- **Committed in:** N/A — operación local del worktree previa al primer commit.

**2. [Rule 3 — Blocking issue] Archivos `04-XX-PLAN.md` no existen en el branch `refactorizacion-WatermrkRemove`**

- **Found during:** Tras `git reset --hard`, los archivos del plan no aparecen en el worktree.
- **Issue:** Los archivos `04-01-PLAN.md`, `04-02-PLAN.md` y `04-03-PLAN.md` están untracked en el repo principal de SmartStitch (planning artifacts no commiteados — patrón habitual del workflow GSD donde los PLAN.md son inputs efímeros). El branch del worktree no los contiene.
- **Fix:** `cp` desde `C:/Users/Felix/Desktop/Python/manhwa_ocr/SmartStitch/.planning/phases/04-visual-polish/04-XX-PLAN.md` al worktree. Como `.planning/` está untracked y los PLAN.md no se commitean, no se contamina el branch del worktree.
- **Files modified:** Ninguno commiteado (los archivos quedan untracked en el worktree, igual que en el repo principal).
- **Verification:** `ls .planning/phases/04-visual-polish/` muestra los 3 PLAN.md disponibles para que el agent los lea.
- **Committed in:** N/A — bootstrap del entorno del agent.

**3. [Rule 1 — bug latente, NO bloqueante] `closeEvent` falla con `FileNotFoundError` al cerrar SlideshowViewer si `core/__settings__/` no existe**

- **Found during:** Verificación integration final post-Task-2 con `QT_QPA_PLATFORM=offscreen`.
- **Issue:** `wm_persistence.set_splitter_sizes()` invocado desde `closeEvent` (línea 235 de slideshow_viewer.py) escribe `core/__settings__/wm_settings.json` sin asegurar que el directorio existe. En un worktree limpio el path no está y se lanza `FileNotFoundError`. Mismo bug documentado en Summary 04-01 deviation #2.
- **Scope:** Es un bug latente del módulo de persistencia (Phase 1) que sale a la luz solo en entornos limpios. El plan 04-03 no toca `wm_persistence.py` ni `closeEvent`. Está **fuera de scope** según la regla de scope boundary del executor.
- **Action:** NO se fix-eó. Documentado aquí y referenciado en deferred-items para que un futuro plan de robustez del módulo `WmPersistenceService` agregue `mkdir(parents=True, exist_ok=True)`. La integración runtime imprimió `OBJECTNAMES_RUNTIME_OK` ANTES del error — los `setObjectName` están correctamente asignados.
- **Files modified:** Ninguno.
- **Verification:** El error solo afecta cierre limpio en entornos sin `core/__settings__/`; los acceptance criteria del plan 04-03 no exigen runtime de `closeEvent` y los 3 comandos finales del bloque `<verification>` pasaron sin tocar el composer.

No hubo deviations Rule 2 (missing critical functionality) ni Rule 4 (cambios arquitectónicos). El refactor sigue el plan al pie de la letra: 2 tasks, 5 archivos modificados, 13 inline setStyleSheet eliminados, 13 setObjectName agregados (12 únicos + 1 compartido para auto_accept_btn).

## Verification

**Comandos finales del plan (bloque `<verification>`):**

```
python -m py_compile gui/stylesheet.py \
    WatermarkRemove/ui/slideshow_viewer.py \
    WatermarkRemove/ui/components/navigation_controller.py \
    WatermarkRemove/ui/components/watermark_processor.py \
    WatermarkRemove/ui/components/training_data_collector.py
→ COMPILE_OK

python -c "from gui.stylesheet import load_styling; s=load_styling(); assert 'wm-counter' in s; assert 'wm-mode-btn' in s; print('STYLESHEET_OK')"
→ STYLESHEET_OK

# Scan de setStyleSheet inline forbidden (excepto los 2 overlays)
→ NO_INLINE_STYLES_OK
```

**Acceptance criteria individuales por archivo:**

```
NAV_OBJECTNAMES_OK         (wm-counter, wm-image-scroll, wm-image-label presentes en navigation_controller.py)
PROCESSOR_OBJECTNAMES_OK   (wm-accept-btn, wm-revert-btn, wm-crop-apply-btn, wm-reset-btn presentes en watermark_processor.py)
COLLECTOR_OBJECTNAME_OK    (wm-training-counts presente en training_data_collector.py)
VIEWER_OBJECTNAMES_OK      (wm-finish-btn, wm-cancel-btn presentes en slideshow_viewer.py)
```

**Integración runtime bajo QApplication offscreen (más estricto que el plan):**

```
QT_QPA_PLATFORM=offscreen python -c "
  app = QApplication(...); app.setStyleSheet(load_styling())
  v = SlideshowViewer(tmp_folder)
  assert v.navigation.counter_label.objectName() == 'wm-counter'
  assert v.navigation.filename_label.objectName() == 'wm-filename'
  assert v.navigation.scroll_area.objectName() == 'wm-image-scroll'
  assert v.navigation.image_label.objectName() == 'wm-image-label'
  assert v.processor.accept_btn.objectName() == 'wm-accept-btn'
  assert v.processor.revert_btn.objectName() == 'wm-revert-btn'
  assert v.processor.crop_apply_btn.objectName() == 'wm-crop-apply-btn'
  assert v.processor.reset_btn.objectName() == 'wm-reset-btn'
  assert v.processor.auto_accept_btn.objectName() == 'wm-accept-btn'
  assert v.processor.auto_accept_next_btn.objectName() == 'wm-save-next-btn'
  assert v.collector.training_counts_label.objectName() == 'wm-training-counts'
  assert v.finish_btn.objectName() == 'wm-finish-btn'
  assert v.cancel_btn.objectName() == 'wm-cancel-btn'
"
→ OBJECTNAMES_RUNTIME_OK
```

Los 13 widgets con estilo específico tienen el `setObjectName()` correcto y el QSS global de `WM_STYLE_SHEET` está aplicado al `QApplication`. El bug `closeEvent`/`FileNotFoundError` documentado arriba aparece tras `OBJECTNAMES_RUNTIME_OK` y no invalida el resultado.

## Threat Surface

Sin nuevos flags. El plan declaró:

- `T-04-06` (Tampering en WM_STYLE_SHEET scope): `mitigate` — TODAS las reglas usan selectores con ID (`#wm-*`); no hay selectores de tipo genérico como `QPushButton { }` que afectarían toda la app. El prefijo `wm-` actúa como namespace.
- `T-04-07` (Elevation of Privilege en concatenación QSS): `accept` — `load_styling()` retorna `dark + WM_STYLE_SHEET`; el QSS de qdarktheme tiene prioridad base (especificidad CSS) y `WM_STYLE_SHEET` sobreescribe solo los selectores `#wm-*` específicos. Sin superficie de ataque.
- `T-04-08` (Tampering en overlays flotantes inline): `accept` — los dos `setStyleSheet()` que permanecen usan RGBA semánticamente único (transparencia para overlays flotantes); documentados como excepción permitida (D-13).
- `T-04-SC` (paquetes maliciosos): `accept` — no se instaló ningún paquete.

## Known Stubs

Ninguno. Todos los widgets que reciben `setObjectName` están conectados a su lógica y reciben el estilo del `WM_STYLE_SHEET` cuando la app se inicia con `load_styling()`. Verificado runtime con `OBJECTNAMES_RUNTIME_OK`.

## Deferred Issues

- **Bug latente del módulo `WmPersistenceService` en `closeEvent`:** `set_splitter_sizes` falla con `FileNotFoundError` si `core/__settings__/` no existe. Fuera de scope de este plan (es código de Phase 1). Recomendación: futuro plan de robustez del persistence service agregar `mkdir(parents=True, exist_ok=True)` antes del `UtilJson(...).set(...)`. Mientras tanto, el bug solo afecta entornos limpios (worktrees nuevos, CI sin warmup) — el flujo normal del usuario no lo encuentra porque la carpeta se crea al primer guardado de `wm_settings`.
- **`LIGHT_STYLE_SHEET` queda definida pero sin uso:** Eliminarla quedó fuera de scope del plan. Si en una phase futura se decide un toggle dark/light, hay que decidir si reactivarla o reescribirla con el patrón `WM_STYLE_SHEET`-style.

## Success Criteria

- [x] `gui/stylesheet.py` define `WM_STYLE_SHEET` con reglas para todos los `wm-*` objectNames del plan (12 reglas distintas).
- [x] `load_styling()` retorna `load_stylesheet('dark') + WM_STYLE_SHEET`.
- [x] Los 4 archivos de componentes no tienen `setStyleSheet()` inline excepto `zoom_overlay_label` y `manual_overlay_label` (verificado por scan automático `NO_INLINE_STYLES_OK`).
- [x] Todos los widgets con necesidad de estilo específico tienen `setObjectName("wm-*")` correspondiente (verificado runtime con `OBJECTNAMES_RUNTIME_OK`).
- [x] Los colores semánticos se preservan: verde `#4CAF50` para Accept/Guardar, rojo `#f44336` para Revertir/Cancelar, teal `#26EE9F` para Finalizar y Aplicar recorte, naranja `#FF9800` para Reset.

## Self-Check: PASSED

- **Files exist:**
  - `gui/stylesheet.py` ✓
  - `WatermarkRemove/ui/components/navigation_controller.py` ✓
  - `WatermarkRemove/ui/components/watermark_processor.py` ✓
  - `WatermarkRemove/ui/components/training_data_collector.py` ✓
  - `WatermarkRemove/ui/slideshow_viewer.py` ✓
  - `.planning/phases/04-visual-polish/04-03-SUMMARY.md` ✓ (este archivo)
- **Commits exist (verificado con `git log --oneline -3`):**
  - `12265ba` ✓ Task 1 (gui/stylesheet.py + WM_STYLE_SHEET + load_styling)
  - `f95bc34` ✓ Task 2 (4 componentes — setStyleSheet inline removidos + setObjectName agregados)
