---
phase: 01-json-persistence
plan: 01
subsystem: persistence
tags: [json, utiljson, audit, wm_persistence, settings]

# Dependency graph
requires: []
provides:
  - "Mapa completo de los 4 call sites de UtilJson en slideshow_viewer.py con keys last_crop_pixels y last_watermark_folder"
  - "Contrato completo de WmPersistenceService: archivo, clase, 4 métodos, singleton path"
  - "Identificación de dead code (import UtilJson en watermark_tab.py) y fuera-de-scope (wm_positions.json)"
  - "Estrategia de migración: sin migración automática desde settings.json"
affects: [01-02-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "WmPersistenceService: wrapper con nombres de dominio sobre UtilJson stateless — pattern de servicio delgado"
    - "Singleton exportado desde services/__init__.py — import limpio en callers"

key-files:
  created:
    - ".planning/phases/01-json-persistence/01-01-AUDIT.md"
  modified: []

key-decisions:
  - "WmPersistenceService usa wrapping stateless (sin cache en memoria) — consistente con el patron actual en slideshow_viewer.py"
  - "Sin migracion automatica desde settings.json — las keys legacy quedan como ignored para no afectar SettingsHandler"
  - "Separacion de archivos JSON: settings.json (SmartStitch) vs wm_settings.json (WM module) — desacoplamiento correcto"
  - "wm_positions.json queda fuera del scope (D-03) — es config de dominio, no state de UI"

patterns-established:
  - "Services wrapper pattern: clase delgada que expone metodos de dominio y oculta UtilJson como detalle de implementacion"
  - "Singleton en __init__.py del paquete services/ para imports limpios"

requirements-completed:
  - ARCH-03

# Metrics
duration: 2min
completed: 2026-05-26
---

# Phase 1 Plan 01: JSON Persistence Audit Summary

**Mapa completo de 4 call sites de UtilJson en slideshow_viewer.py y contrato firmado de WmPersistenceService con wm_settings.json separado**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-26T21:10:53Z
- **Completed:** 2026-05-26T21:12:20Z
- **Tasks:** 1 of 1
- **Files modified:** 1 created

## Accomplishments

- Auditados los 4 call sites exactos de UtilJson en slideshow_viewer.py (líneas 262, 605, 631, 865) con keys, operación y valor default documentados
- Identificado dead code: import de UtilJson en watermark_tab.py sin ningún uso — candidato a eliminar en 01-02
- Delimitado el scope: wm_positions.json (position_editor.py:578, wm_remove.py:611) explícitamente fuera del scope con nota D-03
- Producido contrato completo de WmPersistenceService con firma de 4 métodos de dominio, path del singleton y estrategia de migración — suficiente para que 01-02 implemente sin leer código adicional

## Task Commits

1. **Task 1: Auditar call sites de UtilJson en WatermarkRemove/ y producir contrato del servicio** - `334d17c` (docs)

**Plan metadata:** (pending — summary commit)

## Files Created/Modified

- `.planning/phases/01-json-persistence/01-01-AUDIT.md` — Auditoría completa: tabla de call sites, call sites fuera de scope, diferencias SettingsHandler vs UtilJson, contrato de WmPersistenceService con 4 métodos firmados, estrategia de migración

## Decisions Made

- WmPersistenceService wrappea UtilJson stateless (instancia nueva en cada call, sin cache) — replica el patrón existente en slideshow_viewer.py y evita estado compartido entre instancias
- Archivo JSON separado `wm_settings.json` en lugar de seguir usando `settings.json` — desacopla la persistencia del módulo WM de los perfiles SmartStitch gestionados por SettingsHandler
- Sin migración automática desde settings.json — las keys `last_crop_pixels` y `last_watermark_folder` pre-existentes quedan como legacy ignoradas; el usuario recupera el estado con el primer uso

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- 01-01-AUDIT.md está completo y es suficiente para que el plan 01-02 implemente WmPersistenceService sin ambigüedades
- El contrato especifica: archivo (`WatermarkRemove/services/wm_persistence.py`), clase (`WmPersistenceService`), 4 métodos firmados, singleton (`wm_persistence` en `WatermarkRemove/services/__init__.py`), path JSON (`os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')`)
- No hay blockers para 01-02

---
*Phase: 01-json-persistence*
*Completed: 2026-05-26*
