---
phase: 01-json-persistence
plan: 02
subsystem: persistence
tags: [python, pyside6, json, UtilJson, singleton, services]

# Dependency graph
requires:
  - phase: 01-json-persistence/01-01
    provides: Contrato WmPersistenceService y mapa de call sites auditados
provides:
  - WatermarkRemove/services/wm_persistence.py con WmPersistenceService (4 metodos de dominio)
  - WatermarkRemove/services/__init__.py exportando singleton wm_persistence
  - slideshow_viewer.py migrado — 4 call sites directos a UtilJson(settings.json) reemplazados por singleton
  - watermark_tab.py limpio — import muerto de UtilJson eliminado
affects:
  - 01-json-persistence
  - phases-depending-on-slideshow_viewer

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Singleton de modulo en WatermarkRemove/services/__init__.py — mismo patron que core/services/"
    - "WmPersistenceService wrappea UtilJson stateless (sin cache en memoria) con nombres de dominio"
    - "Separacion de archivos JSON: wm_settings.json para WM vs settings.json para SmartStitch pipeline"

key-files:
  created:
    - WatermarkRemove/services/__init__.py
    - WatermarkRemove/services/wm_persistence.py
  modified:
    - WatermarkRemove/ui/slideshow_viewer.py
    - WatermarkRemove/ui/watermark_tab.py

key-decisions:
  - "UtilJson retenido en slideshow_viewer.py — sigue usandose en linea 706 para leer wm_positions.json (D-03: fuera de scope)"
  - "SETTINGS_REL_DIR eliminado de slideshow_viewer.py — solo se usaba en los 4 call sites migrados"
  - "wm_settings.json como archivo separado para estado UI de WM — no fusionar con settings.json de SettingsHandler"
  - "Sin migracion automatica de datos: last_crop_pixels y last_watermark_folder en settings.json quedan como legacy ignoradas"

patterns-established:
  - "services/ en submodulo: WatermarkRemove/services/ sigue la convencion de core/services/"
  - "Singleton exportado desde __init__.py permite 'from WatermarkRemove.services import wm_persistence'"

requirements-completed:
  - ARCH-03

# Metrics
duration: 12min
completed: 2026-05-26
---

# Phase 1 Plan 02: JSON Persistence Implementation Summary

**WmPersistenceService singleton wrapping UtilJson con wm_settings.json, eliminando 4 llamadas directas a UtilJson(settings.json) desde slideshow_viewer.py**

## Performance

- **Duration:** 12 min
- **Started:** 2026-05-26T21:10:00Z
- **Completed:** 2026-05-26T21:22:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Creado WatermarkRemove/services/ como nuevo paquete con WmPersistenceService (wm_persistence.py) y singleton wm_persistence (__init__.py)
- Migrados los 4 call sites directos de UtilJson(settings.json) en slideshow_viewer.py a metodos del singleton wm_persistence
- Eliminado el import muerto de UtilJson en watermark_tab.py
- ARCH-03 satisfecho: WatermarkRemove/ui/ ya no tiene llamadas directas a UtilJson para settings de usuario

## Task Commits

Cada task fue commiteado atomicamente:

1. **Task 1: Crear WmPersistenceService y singleton** - `fa7dc56` (feat)
2. **Task 2: Migrar 4 call sites y limpiar import muerto** - `ddc70b8` (feat)

**Plan metadata:** pendiente (docs: complete plan)

## Files Created/Modified

- `WatermarkRemove/services/wm_persistence.py` — WmPersistenceService con 4 metodos: get/set_last_crop_pixels, get/set_last_watermark_folder; wrappea UtilJson(wm_settings.json) stateless
- `WatermarkRemove/services/__init__.py` — Singleton wm_persistence = WmPersistenceService(); exporta wm_persistence y WmPersistenceService
- `WatermarkRemove/ui/slideshow_viewer.py` — Reemplazados 4 UtilJson(settings.json) calls; agregado import wm_persistence; eliminado SETTINGS_REL_DIR; UtilJson retenido para wm_positions.json (linea 706)
- `WatermarkRemove/ui/watermark_tab.py` — Eliminado import muerto 'from utils import UtilJson'

## Decisions Made

- **UtilJson retenido en slideshow_viewer.py:** La auditoria (D-03) identifica que la linea 706 usa `UtilJson(positions_path).read()` para `wm_positions.json` — fuera del scope de ARCH-03. El import se mantiene para ese uso legitimo.
- **SETTINGS_REL_DIR eliminado:** Solo se usaba en los 4 call sites migrados, ningun otro uso encontrado.
- **wm_settings.json separado de settings.json:** Desacopla el estado UI de WM del pipeline SmartStitch (SettingsHandler); legacy keys en settings.json quedan ignoradas — no hay migracion automatica (estado UI de conveniencia, no datos criticos).

## Deviations from Plan

### Auto-noted Issues

**1. [Plan assertion vs audit contract] UtilJson persiste en slideshow_viewer.py**
- **Found during:** Task 2 (verificacion post-migracion)
- **Issue:** El comando verify del plan afirma `assert 'UtilJson' not in content` — pero la auditoria (01-01-AUDIT.md Seccion 2, D-03) explicitamente marca la linea 706 (`UtilJson(positions_path).read()` para `wm_positions.json`) como fuera de scope. El plan asume que los unicos usos eran los 4 call sites de settings.json, sin conocer el uso adicional en wm_positions.json.
- **Resolution:** Se aplica el contrato del audit como fuente de verdad. El import de UtilJson se retiene; solo SETTINGS_REL_DIR fue eliminado. Los 4 call sites de settings.json fueron migrados exitosamente. La verificacion de integracion custom paso; la verificacion literaldel plan (assert UtilJson not in content) no aplica por la excepcion documentada en audit D-03.
- **Success criteria 7 satisfecho:** "no hay llamadas directas a UtilJson desde ningún archivo en WatermarkRemove/ui/ [para settings de usuario]" — ningun archivo UI llama a UtilJson con settings.json despues de la migracion.

---

**Total deviations:** 1 nota (plan assertion vs audit contract, sin scope creep)
**Impact on plan:** El intent de ARCH-03 esta completamente satisfecho. La diferencia es terminologica en la assertion del verify script.

## Issues Encountered

None — implementacion directa siguiendo el contrato de 01-01-AUDIT.md.

## Known Stubs

None — ningun metodo retorna datos hardcodeados o placeholder. get_last_crop_pixels() retorna 0 por default (UtilJson.get default), get_last_watermark_folder() retorna None por default. Estos son defaults legitimos, no stubs.

## Threat Flags

Ninguna nueva superficie de seguridad introducida. wm_settings.json es un archivo local de estado UI (sin PII, sin secretos). El comportamiento defensivo de UtilJson.read() (retorna {} si el archivo no existe o esta corrupto) es heredado por WmPersistenceService — T-01-02-02 mitigado tal como requeria el threat model.

## Next Phase Readiness

- ARCH-03 satisfecho: WatermarkRemove/services/ establece el patron de servicios para el modulo
- slideshow_viewer.py listo para la siguiente fase de refactorizacion (Phase 2: descomposicion SlideshowViewer)
- El singleton wm_persistence puede ser importado por cualquier componente futuro de WatermarkRemove que necesite persistir estado UI

---
*Phase: 01-json-persistence*
*Completed: 2026-05-26*
