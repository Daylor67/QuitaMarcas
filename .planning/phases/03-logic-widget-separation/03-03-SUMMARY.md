---
phase: 03-logic-widget-separation
plan: 03
subsystem: ui
wave: 2

tags: [pyside6, watermark-remove, arch-04, watermark-tab, context-menu-service, coordinator-pattern]

# Dependency graph
requires:
  - phase: 03-logic-widget-separation
    plan: 01
    provides: context_menu_service (singleton del barrel — is_registered / toggle)
  - phase: 03-logic-widget-separation
    plan: 02
    provides: position_editor + image_viewer ya delegando — patrón de "widget coordinador" replicable

provides:
  - WatermarkRemove/ui/watermark_tab.py refactored — 0 hits de dominio OS (ARCH-04)
  - Alias `apply_settings = set_settings` en WatermarkTab — honra la constraint literal de CLAUDE.md / ROADMAP sin romper el método real
  - Phase 3 cerrada con UAT manual aprobado por el usuario — los 3 widgets son coordinadores puros y el contrato externo (gui/controller.py) está intacto

affects: [phase-04, future-phases-touching-WatermarkTab, future-tests-of-context-menu-service]

# Tech tracking
tech-stack:
  added: []   # No new packages — delegación pura a ContextMenuService (ya creado en 03-01)
  patterns:
    - "Widget coordinador puro: la lógica de dominio OS (winreg) sale completa; el widget conserva SOLO presentación (QMessageBox feedback + button text refresh)"
    - "Alias de contrato (apply_settings = set_settings): cuando la constraint externa exige un nombre y el método real tiene otro, un alias de clase resuelve ambas sin duplicar código"
    - "Rigor pragmático en ARCH-04: try/except + toggle de estado del botón en _check_for_updates SE QUEDA (es coordinación de UI, no dominio). Lo que sale es la lógica de dominio OS (winreg)"

key-files:
  created: []
  modified:
    - WatermarkRemove/ui/watermark_tab.py

key-decisions:
  - "Mover SOLO winreg + register_context_menu a ContextMenuService — _check_for_updates se queda intacto (RESEARCH Open Question #2 / A5: try/except + setEnabled/setText es feedback de presentación legítimo, no dominio)"
  - "Agregar `apply_settings = set_settings` como alias de clase (no como método separado): el contrato externo literal de CLAUDE.md se cumple sin duplicar implementación ni romper los call-sites internos que usan set_settings"
  - "_update_context_menu_btn se queda en el widget (presentación pura: texto del botón) pero su condición delega a `context_menu_service.is_registered()` en lugar del método interno eliminado"
  - "Constructor WatermarkTab(parent=None), atributo público run_quita_marcas (QCheckBox), métodos log/get_settings/set_settings — TODOS preservados verbatim, verificado con `git diff gui/controller.py` vacío"

patterns-established:
  - "Coordinador puro tras refactor ARCH-04: import del singleton del barrel + reemplazo de la lógica de dominio inline + preservación de los QMessageBox + presentación intacta + alias de contrato si aplica"
  - "Excepción documentada: cuando un método ya delega a un servicio (UpdateChecker) y solo conserva try/except + toggle de UI, NO se crea un servicio extra para envolver ese try/except — sería over-engineering. Se documenta la decisión en el commit y en el SUMMARY"

requirements-completed: [ARCH-04]

# Metrics
duration: ~12min (Task 1: ~5min refactor + gates; Task 2: UAT manual humano)
completed: 2026-05-27
---

# Phase 3 Plan 03: WatermarkTab Coordinator Refactor Summary

**watermark_tab.py convertida en coordinador puro (ARCH-04): la lógica winreg sale a ContextMenuService, el widget solo cablea señales con servicios y refleja estado en la presentación; alias `apply_settings = set_settings` honra el contrato literal de CLAUDE.md; el contrato externo verificado contra `gui/controller.py` queda intacto (diff vacío) y el usuario aprobó el UAT manual completo de Phase 3.**

## Performance

- **Duration:** ~12 min (Task 1 refactor + gates: ~5 min; Task 2 UAT humano: ~7 min)
- **Tasks:** 2 / 2 completados (1 auto-refactor + 1 checkpoint UAT)
- **Files modified:** 1 (`WatermarkRemove/ui/watermark_tab.py`)
- **Files created:** 0 (delegación pura — ContextMenuService ya existía desde 03-01)
- **Lines net:** -7 (14 inserciones, 21 eliminaciones) — el widget queda más liviano

## Accomplishments

- **`watermark_tab.py` refactored (Task 1, commit `45b3d88`):**
  - Agregado `from WatermarkRemove.services import context_menu_service` (singleton del barrel, definido en Plan 03-01).
  - **Eliminado** el método privado `_is_context_menu_registered` — sus dos usos se reemplazan por `context_menu_service.is_registered()`.
  - **`_update_context_menu_btn` permanece en el widget** (es presentación — texto del botón "Registrar" / "Desregistrar"), pero su condición ahora delega a `context_menu_service.is_registered()` (L149).
  - **`_toggle_context_menu` reescrito**: el cuerpo es ahora `now_registered = context_menu_service.toggle()` dentro de un `try/except`. El widget conserva SOLO el QMessageBox.information apropiado según `now_registered` (mensaje "registrado" con la instrucción de click derecho, o "eliminado") + `self._update_context_menu_btn()` para refrescar el botón. El `except Exception as e: QMessageBox.critical(...)` también se queda en el widget. **El widget ya no importa winreg ni register_context_menu y no toca el registro de Windows directamente.**
  - **`apply_settings = set_settings` agregado como alias de clase** al final de la definición (L235) — honra la constraint literal de CLAUDE.md / ROADMAP que pide `apply_settings`, sin romper los call-sites internos que ya usan `set_settings` (RESEARCH Pitfall 1).
  - **`_check_for_updates` SE QUEDA intacto** (decisión de rigor documentada en el commit y abajo en "Decisions Made"): el método ya delega a `UpdateChecker` (servicio existente en `core.services`); el único código inline es try/except + `setEnabled` + `setText` sobre el botón, que es feedback de presentación legítimo de un coordinador, no lógica de dominio. ARCH-04 exige sacar el dominio OS (winreg), que SÍ se mueve.
  - **Métodos de coordinación legítima preservados intactos**: `_open_image_viewer` y `_open_position_editor` solo instancian diálogos (coordinación), `_get_main_window`, `log`, todo `_setup_ui` y los handlers `_on_*_changed` se quedan.
  - **Imports muertos eliminados verbatim**: el import inline de `winreg` y el import de `register_context_menu` fueron removidos (verificado con grep en 0 hits de dominio OS).

- **ARCH-04 gate verified** — el grep canónico (`winreg.|register_context_menu`, filtrado por comentarios) retorna **0** en `watermark_tab.py`. La excepción documentada (1 hit de `UpdateChecker(`) está aceptada como decisión de rigor — el patrón "delegar a UpdateChecker + UI feedback" ya cumple ARCH-04 porque la lógica de update vive en el servicio, no en el widget.

- **Contrato externo intacto** — `git diff 7f6fafa..HEAD -- gui/controller.py` vacío. Smoke `WT_CONTRACT_OK` confirma que `WatermarkTab()` instancia sin args y expone los 5 símbolos requeridos: `run_quita_marcas`, `log`, `get_settings`, `set_settings`, `apply_settings`.

- **UAT manual Phase 3 aprobado por el usuario (Task 2):** las 5 secciones de `03-HUMAN-UAT.md` pasaron sin regresión. El usuario escribió "approved", cerrando Phase 3 sin gap-closure pendiente:
  - **Sección 1 — Editor de Posiciones:** preview en vivo, "Guardar y Siguiente" hasta la última imagen con QMessageBox "Completado", persistencia en `wm_positions.json` con estructura `carpeta → marca → pos_N` intacta. ✓
  - **Sección 2 — Visor de Imágenes:** grid de thumbnails + contador correcto desde carpeta válida. ✓
  - **Sección 3 — Menú Contextual (Windows):** click registra (texto → "Desregistrar"), entrada visible en click derecho del explorador, click de nuevo desregistra (texto → "Registrar"). ✓
  - **Sección 4 — Buscar Actualizaciones:** diálogo de update / "Ya tienes la última versión". ✓
  - **Sección 5 — Contrato:** marcar checkbox "Ejecutar Quita Marcas" y correr el pipeline → SlideshowViewer abre (flujo completo Phase 2 intacto). ✓

## Task Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Refactorizar watermark_tab.py — delegar winreg a ContextMenuService + alias apply_settings | `45b3d88` (refactor) | `WatermarkRemove/ui/watermark_tab.py` |
| 2 | UAT manual completo de Phase 3 + verificación de contrato | — (no-code checkpoint, sign-off humano "approved") | — |

**Plan metadata:** (este commit, `docs(03-03): complete watermark_tab coordinator refactor — UAT approved`).

## Files Modified

- `WatermarkRemove/ui/watermark_tab.py` — refactor: -21 / +14 líneas. Import `context_menu_service` agregado; `_is_context_menu_registered` eliminado; `_update_context_menu_btn` delega `is_registered()` al servicio (presentación intacta); `_toggle_context_menu` reescrito para llamar `context_menu_service.toggle()` (lógica winreg fuera del widget); `apply_settings = set_settings` alias agregado; constructor / `run_quita_marcas` / `log` / `get_settings` / `set_settings` / `_check_for_updates` preservados verbatim.

## Decisions Made

- **`_check_for_updates` se queda intacto (rigor pragmático ARCH-04):** el método ya delega el trabajo de red/parseo a `UpdateChecker` (servicio en `core.services`). El código inline restante (`try/except` + `setEnabled(False)` + `setText("Buscando…")` + `setEnabled(True)` + reset del texto al terminar) es feedback de presentación de un coordinador, no lógica de dominio. Crear un servicio extra para envolver un try/except de UI sería over-engineering. La excepción documentada (1 hit de `UpdateChecker(` en el grep) está aceptada — ARCH-04 exige sacar la lógica de dominio OS (winreg), que sí se mueve a `ContextMenuService`. (Origen: RESEARCH Open Question #2 / A5.)
- **`apply_settings = set_settings` como alias de clase (no como wrapper):** la constraint literal en CLAUDE.md y ROADMAP pide `apply_settings`, pero el método real (y los call-sites internos) usa `set_settings`. Un alias de clase (`apply_settings = set_settings` a nivel de definición de la clase) hace que ambos nombres apunten al mismo método sin duplicar lógica, sin romper los call-sites internos y sin agregar una capa innecesaria. Cumple la constraint literal con cero impacto operativo. (Origen: RESEARCH Pitfall 1.)
- **`_update_context_menu_btn` se queda en el widget — solo su condición delega al servicio:** el método es presentación pura (texto del botón "Registrar" / "Desregistrar"). Lo que cambia es la fuente de la verdad: en lugar de un método privado que abre winreg, ahora pregunta a `context_menu_service.is_registered()`. Esto deja la presentación en su sitio y mueve solo la consulta de estado al servicio. (Origen: PATTERNS L213 — los métodos `_open_*` y los `_update_*_btn` son coordinación legítima y se quedan en el widget.)
- **Constructor `WatermarkTab(parent=None)` y atributo público `self.run_quita_marcas` (QCheckBox) preservados verbatim:** `gui/controller.py:76` instancia `WatermarkTab()` sin args y `gui/controller.py:317` accede directo a `self.tab.run_quita_marcas.isChecked()`. Cambiar la firma o envolver el checkbox en property habría roto el contrato externo. Verificado con `git diff 7f6fafa..HEAD -- gui/controller.py` vacío. (Origen: RESEARCH Pitfall 2.)

## Deviations from Plan

None — plan ejecutado exactamente como fue escrito. La única "deviation" prevista por el plan (la decisión de rigor sobre `_check_for_updates`) está documentada arriba en "Decisions Made" y en el cuerpo del commit `45b3d88`; no es una desviación porque el plan la describe explícitamente como decisión de rigor aceptada (PLAN L75 + acceptance criteria + Open Question #2 ya resuelta en RESEARCH).

## Issues Encountered

None. Task 1 ejecutado limpio en una sola pasada dentro del worktree correcto (`agent-a9855d5cf029e57b3`); `git status --short` confirmó que el único cambio en el rango del plan fue `WatermarkRemove/ui/watermark_tab.py`. UAT manual del usuario corrió sin regresión en las 5 secciones.

## User Setup Required

None — no se instalaron paquetes, no se cambiaron configs, no se requieren env vars.

## Threat Model Verification

| Threat ID | Disposition | Verification |
|-----------|-------------|--------------|
| T-03-03-01 | accept | `ContextMenuService.toggle` solo reubica el call-site; la clave de registro Windows y su alcance NO cambian; el guard `FileNotFoundError` se preserva en el servicio. Verificado: la rama lógica de toggle (registrar / desregistrar) sigue produciendo los QMessageBox correctos en el UAT Sección 3. |
| T-03-03-02 | mitigate | `git diff 7f6fafa..HEAD -- gui/controller.py` → vacío (0 líneas). Smoke `WT_CONTRACT_OK` confirma que `WatermarkTab()` instancia sin args y expone `run_quita_marcas` / `log` / `get_settings` / `set_settings` / `apply_settings` (los 5 símbolos del contrato). |
| T-03-SC | accept | 0 paquetes instalados en Phase 3 (verificado: cero ejecuciones de pip/npm/cargo install). |

## Next Phase Readiness

- **Phase 3 está cerrada — ARCH-04 + SC-1 + SC-4 satisfechos:**
  - ARCH-04: los 3 widgets (position_editor, image_viewer, watermark_tab) ya son coordinadores puros. La lógica de dominio (cv2/align/remove/load/scan/persist + winreg) vive en servicios.
  - SC-1 (contrato externo): `gui/controller.py` sin cambios; smoke contract OK.
  - SC-4 (flujo completo intacto): UAT humano aprobó las 5 secciones, incluyendo el flujo end-to-end del checkbox "Ejecutar Quita Marcas" → SlideshowViewer.
- **Phase 4 (próxima) puede arrancar sin bloqueos en la capa UI/servicios.** El worktree de este plan está listo para merge a `refactorizacion-WatermrkRemove`.
- **No blockers, no concerns.**

## Self-Check: PASSED

Verified before returning:

- `[ -f WatermarkRemove/ui/watermark_tab.py ]` → FOUND (modified by `45b3d88`)
- `git log --oneline | grep -q 45b3d88` → FOUND (Task 1 commit)
- `python -m py_compile WatermarkRemove/ui/watermark_tab.py` → COMPILE_OK
- ARCH-04 grep `winreg.|register_context_menu` (filtered comments) → WINREG_HITS: 0
- `UpdateChecker(` grep → 1 (excepción aceptada — RESEARCH Open Q #2 / A5)
- Smoke `WatermarkTab()` + hasattr check → WT_CONTRACT_OK (run_quita_marcas / log / get_settings / set_settings / apply_settings)
- Contract markers (`from WatermarkRemove.services import context_menu_service`, `context_menu_service.is_registered()`, `context_menu_service.toggle()`, `apply_settings = set_settings`, `def __init__(self, parent=None)`, `self.run_quita_marcas = QCheckBox`, `def log(self, message`, `def get_settings`, `def set_settings`) → ALL FOUND
- `git diff 7f6fafa..HEAD -- gui/controller.py` → empty (0 líneas; contrato externo intacto)
- UAT manual humano: 5/5 secciones APPROVED por el usuario

---
*Phase: 03-logic-widget-separation*
*Plan: 03 of 3 (Wave 2 — watermark_tab coordinator refactor + Phase 3 UAT close)*
*Completed: 2026-05-27*
