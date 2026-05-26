# Phase 1: JSON Persistence - Context

**Gathered:** 2026-05-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Crear un único servicio de persistencia JSON para WatermarkRemove que reemplace todos los accesos directos a `UtilJson` desde el código UI. WatermarkRemove no debería hacer llamadas directas a archivos JSON desde sus componentes de vista — todo pasa por el servicio.

**Fuera de scope:** Cambiar el formato de `wm_positions.json` o `training_data.json`. No tocar `SettingsHandler` ni los settings de SmartStitch. No refactorizar `training_collector.py` (usa json crudo, pero `training_data.json` está out of scope para cambios de formato).

</domain>

<decisions>
## Implementation Decisions

### Storage — ¿Dónde viven los settings de WM?
- **D-01:** Los settings de WatermarkRemove van en `wm_settings.json` — archivo separado, NO en el mismo `settings.json` que usa SettingsHandler para perfiles de SmartStitch.
- **D-02:** Solo migrar las 2 claves actuales: `last_crop_pixels` y `last_watermark_folder`. No expandir a otras claves en esta fase.
- **D-03:** `wm_positions.json` NO se toca — sigue leyéndose/escribiéndose como está. Solo las claves de settings migran a `wm_settings.json`.

### Service Location — ¿Dónde vive el nuevo servicio?
- **D-04:** El servicio vive en `WatermarkRemove/services/` — nuevo directorio dentro del módulo. No en `core/services/` ni en `utils/`.
- **D-05:** Patrón de acceso: singleton de módulo. El servicio se instancia una vez (en `WatermarkRemove/services/__init__.py` o similar) y se importa donde se necesita. Sin inyección de constructor.

### Claude's Discretion
- Nombre exacto del archivo del servicio (ej: `wm_persistence.py`, `settings_service.py`)
- Nombre de la clase del servicio
- Si el servicio expone la API tipada de `UtilJson` (get/set) o métodos con nombres de dominio (get_last_folder, set_crop_pixels)
- Manejo de migración: si `settings.json` ya tiene `last_crop_pixels` / `last_watermark_folder`, qué hacer con esas claves al transicionar

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### JSON Persistence — código actual
- `utils/json_utils.py` — UtilJson: utilidad genérica que el servicio nuevo debe wrappear o reemplazar
- `core/services/settings_handler.py` — SettingsHandler: entender qué NO debe cambiarse (perfiles de SmartStitch)
- `core/utils/constants.py` — SETTINGS_REL_DIR: directorio donde viven los archivos JSON de settings

### Consumidores actuales de UtilJson en WatermarkRemove
- `WatermarkRemove/ui/slideshow_viewer.py` — hace 4 llamadas directas a UtilJson(settings.json): líneas 262, 605, 631, 865
- `WatermarkRemove/ui/position_editor.py` — usa UtilJson para wm_positions.json (línea 578)
- `WatermarkRemove/wm_remove.py` — usa UtilJson para posiciones (línea 611)

### Requisitos
- `.planning/REQUIREMENTS.md` §ARCH-03 — "SettingsHandler y UtilJson unificados en único servicio JSON"

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `utils/json_utils.py` (UtilJson): el nuevo servicio puede wrappear esta clase en vez de reimplementar la lógica de archivo
- `core/utils/constants.py` (SETTINGS_REL_DIR): usar esta constante para el path de `wm_settings.json`

### Established Patterns
- WatermarkRemove usa `from utils import UtilJson` — el nuevo servicio sigue el mismo patrón de importación desde la raíz del proyecto
- Singleton de módulo: patrón no usado en WatermarkRemove aún, pero común en `core/services/`

### Integration Points
- `WatermarkRemove/ui/slideshow_viewer.py` líneas 262, 605, 631, 865: reemplazar 4 llamadas directas a UtilJson por llamadas al servicio
- `WatermarkRemove/ui/watermark_tab.py`: importa UtilJson pero no lo usa directamente en el snippet visible — verificar usos completos
- `WatermarkRemove/services/__init__.py`: archivo nuevo que expone el singleton del servicio

</code_context>

<specifics>
## Specific Ideas

- No cambiar el formato de `wm_positions.json` — solo mover `last_crop_pixels` y `last_watermark_folder` a `wm_settings.json`
- El archivo `settings.json` del SmartStitch principal no debe ser tocado por este servicio

</specifics>

<deferred>
## Deferred Ideas

- Unificar `training_collector.py` con el servicio (usa json crudo) — fuera de scope para esta fase, `training_data.json` tiene formato fijo
- Inyección de dependencias para los servicios de WatermarkRemove — over-engineering para esta fase

</deferred>

---

*Phase: 1-JSON Persistence*
*Context gathered: 2026-05-26*
