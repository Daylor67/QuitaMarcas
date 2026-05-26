---
phase: 01-json-persistence
verified: 2026-05-26T22:00:00Z
status: human_needed
score: 3/4 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Abrir la aplicación, cambiar la carpeta de watermarks, cerrar y volver a abrir — verificar que last_watermark_folder se restaura"
    expected: "La carpeta seleccionada previamente reaparece seleccionada al reabrir"
    why_human: "Requiere iniciar la aplicación PySide6 completa; no hay tests de UI automatizados en el proyecto"
  - test: "Abrir la aplicación, ajustar el valor de crop pixels, cerrar y volver a abrir — verificar que last_crop_pixels se restaura"
    expected: "El spinbox de crop pixels muestra el valor guardado al reabrir"
    why_human: "Mismo motivo — requiere sesión GUI real para confirmar round-trip de settings"
---

# Phase 1: JSON Persistence Verification Report

**Phase Goal:** El módulo tiene un único servicio de persistencia JSON — no hay código duplicado entre SettingsHandler y UtilJson
**Verified:** 2026-05-26T22:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Toda llamada de lectura/escritura JSON sobre `last_crop_pixels`/`last_watermark_folder` en WatermarkRemove/ui/ usa el servicio unificado — no hay llamadas directas a UtilJson con settings.json | VERIFIED | `slideshow_viewer.py` líneas 262, 605, 631, 865 usan `wm_persistence.*`; grep confirma 0 ocurrencias de `UtilJson.*settings.json` en WatermarkRemove/; `watermark_tab.py` sin import UtilJson |
| 2 | wm_positions.json y training_data.json se cargan/guardan correctamente (scope ajustado: solo wm_settings.json migrado per D-03) | SCOPED / HUMAN NEEDED | D-03 en CONTEXT.md y ROADMAP cross-cutting constraints excluyen explícitamente wm_positions.json. `wm_settings.json` persiste correctamente (verificado programáticamente). El round-trip completo (set → reopen → get) requiere sesión GUI |
| 3 | SmartStitchGUI.py sigue funcionando sin cambios — la API pública de persistencia no se rompió | VERIFIED | `SmartStitchGUI.py` (3 líneas) sin cambios; `gui/controller.py` importa `WatermarkTab`/`SlideshowViewer` sin modificaciones; `WatermarkTab.get_settings()` / `set_settings()` intactos |
| 4 | No hay regresión en la carga/guardado de settings cuando se abre y cierra la aplicación | PARTIALLY VERIFIED | `wm_persistence.get_last_crop_pixels()` retorna `int: 0` (correcto), `get_last_watermark_folder()` retorna `None` (correcto). Defaults y tipos válidos. Round-trip real (write → restart → read) requiere confirmación humana con sesión GUI |

**Score:** 3/4 truths verified (SC2/SC4 necesitan confirmación GUI para round-trip completo)

### Scope Note on Success Criterion 2

Per design decision **D-03** documentado en `01-CONTEXT.md` y la sección "Cross-cutting constraints" del ROADMAP.md, `wm_positions.json` está **explícitamente fuera de scope** para esta fase. Solo `last_crop_pixels` y `last_watermark_folder` (anteriormente en `settings.json`) fueron migrados a `wm_settings.json`. `training_data.json` usa el módulo `json` estándar de Python directamente (nunca usó UtilJson), por lo que tampoco era candidato a migración.

El criterio 2 como está redactado en ROADMAP.md es más amplio que el scope aprobado de la fase. La implementación es correcta dentro del scope definido.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `WatermarkRemove/services/wm_persistence.py` | WmPersistenceService con 4 métodos de dominio | VERIFIED | Existe, 39 líneas, clase completa con get/set_last_crop_pixels, get/set_last_watermark_folder, wrappea UtilJson stateless |
| `WatermarkRemove/services/__init__.py` | Singleton `wm_persistence` exportado | VERIFIED | Existe, 5 líneas, exporta `wm_persistence = WmPersistenceService()` y `__all__` correcto |
| `WatermarkRemove/ui/slideshow_viewer.py` (modificado) | 4 call sites migrados a wm_persistence, import de wm_persistence agregado | VERIFIED | 4 llamadas al singleton presentes en líneas 262, 605, 631, 865; `from WatermarkRemove.services import wm_persistence` en línea 23; UtilJson retenido para wm_positions.json (D-03) |
| `WatermarkRemove/ui/watermark_tab.py` (modificado) | Import muerto de UtilJson eliminado | VERIFIED | `from utils import UtilJson` no aparece en el archivo |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `slideshow_viewer.py` | `WatermarkRemove/services/__init__.py` | `from WatermarkRemove.services import wm_persistence` | WIRED | Import en línea 23; 4 llamadas al singleton en líneas 262, 605, 631, 865 |
| `WatermarkRemove/services/wm_persistence.py` | `utils/json_utils.py` | `UtilJson(self._path)` | WIRED | Cada método instancia `UtilJson(self._path)` stateless — patrón correcto per D-05 |
| `WatermarkRemove/services/wm_persistence.py` | `core/utils/constants.py` | `from core.utils.constants import SETTINGS_REL_DIR` | WIRED | Usado en `__init__` para `os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `wm_persistence.get_last_crop_pixels()` | `last_crop_pixels` key | `UtilJson(wm_settings.json).get(...)` | Sí — lee del archivo JSON; default `0 or 0` si ausente | FLOWING |
| `wm_persistence.get_last_watermark_folder()` | `last_watermark_folder` key | `UtilJson(wm_settings.json).get(...)` | Sí — lee del archivo JSON; default `None` si ausente | FLOWING |
| `wm_persistence.set_last_crop_pixels()` | escribe `last_crop_pixels` | `UtilJson(wm_settings.json).set(...)` | Sí — escribe al archivo JSON con `int(value)` | FLOWING |
| `wm_persistence.set_last_watermark_folder()` | escribe `last_watermark_folder` | `UtilJson(wm_settings.json).set(...)` | Sí — escribe al archivo JSON | FLOWING |

Nota: El round-trip write → restart → read no puede verificarse programáticamente sin sesión GUI (ver Human Verification).

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Módulo importa sin error | `python -c "from WatermarkRemove.services import wm_persistence; print(type(wm_persistence).__name__)"` | `WmPersistenceService` | PASS |
| 4 métodos de dominio presentes | `hasattr` checks en los 4 métodos | Todos presentes | PASS |
| `get_last_crop_pixels()` retorna int | `isinstance(v, int)` | `True` — retorna `0` | PASS |
| `get_last_watermark_folder()` retorna str o None | `isinstance(f, str) or f is None` | `True` — retorna `None` | PASS |
| 0 referencias UtilJson+settings.json en WatermarkRemove/ui/ | grep pattern | 0 matches | PASS |
| watermark_tab.py sin import UtilJson | grep | 0 matches | PASS |
| 4 calls al singleton en slideshow_viewer.py | grep | 4 matches en líneas 262, 605, 631, 865 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| ARCH-03 | 01-01-PLAN.md, 01-02-PLAN.md | SettingsHandler y UtilJson unificados en único servicio de persistencia JSON — no hay duplicación de responsabilidad | SATISFIED | WmPersistenceService en WatermarkRemove/services/ centraliza el acceso a wm_settings.json; los 4 call sites directos a UtilJson(settings.json) desde WatermarkRemove/ui/ han sido eliminados; la duplicación UI→JSON fue eliminada |

**Nota ARCH-03:** La redacción del requisito menciona "SettingsHandler y UtilJson unificados". En la práctica, el audit (01-01-AUDIT.md Sección 3) determinó que SettingsHandler y UtilJson NO tienen overlap real de responsabilidad — SettingsHandler gestiona perfiles SmartStitch, UtilJson es utilitario genérico. ARCH-03 se satisface creando un wrapper con nombres de dominio que oculta UtilJson como detalle de implementación en WatermarkRemove/ui/, eliminando el acoplamiento directo. Esta interpretación fue documentada en el audit y aceptada por el plan.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | — |

Sin debt markers (TBD/FIXME/XXX), sin stubs, sin implementaciones vacías en los archivos modificados por esta fase.

**Nota sobre UtilJson retenido en slideshow_viewer.py (línea 22 y 706):** El import de UtilJson permanece porque la línea 706 usa `UtilJson(positions_path).read()` para `wm_positions.json` — uso legítimo fuera de scope per D-03. No es un anti-pattern; es una dependencia justificada documentada en el SUMMARY de 01-02.

### Human Verification Required

#### 1. Round-trip de last_watermark_folder

**Test:** Abrir la aplicación SmartStitch, navegar a la pestaña "Quita Marcas", abrir el SlideshowViewer, seleccionar una carpeta de watermarks, cerrar la aplicación, volver a abrir y verificar que la carpeta seleccionada previamente reaparece.
**Expected:** La carpeta seleccionada en la sesión anterior está pre-seleccionada al reabrir.
**Why human:** Requiere iniciar la aplicación PySide6 completa con GUI real. No hay tests de UI automatizados en el proyecto. El método `set_last_watermark_folder` se llama en slideshow_viewer.py línea 631 dentro de un flujo de interacción de usuario que no puede simularse sin la GUI.

#### 2. Round-trip de last_crop_pixels

**Test:** Abrir la aplicación, en el SlideshowViewer cambiar el valor del spinbox de crop pixels a un valor no-cero (ej. 15), cerrar la aplicación, volver a abrir y verificar que el spinbox muestra 15.
**Expected:** El valor de crop pixels se restaura al valor guardado en wm_settings.json.
**Why human:** Mismo motivo — `set_last_crop_pixels` se llama en línea 865 durante interacción de usuario. El archivo `wm_settings.json` puede no existir aún si la aplicación nunca se ha abierto, por lo que el round-trip real es la única verificación concluyente de SC4.

### Gaps Summary

No hay gaps bloqueantes. Los únicos ítems pendientes son las verificaciones de round-trip que requieren una sesión GUI real (human_needed). La implementación técnica es completa y correcta:

- El servicio `WmPersistenceService` existe, es sustantivo, está cableado y los datos fluyen correctamente.
- Los 4 call sites directos a `UtilJson(settings.json)` en `slideshow_viewer.py` fueron reemplazados por el singleton.
- El import muerto de UtilJson en `watermark_tab.py` fue eliminado.
- La API pública de `WatermarkTab` (`get_settings`/`set_settings`) no fue alterada.
- Sin breaking changes en `SmartStitchGUI.py` ni en `gui/controller.py`.

El éxito de SC2 está acotado por D-03 (wm_positions.json fuera de scope) — este scope fue aprobado en el CONTEXT y documentado en el ROADMAP como cross-cutting constraint. No es un gap de implementación.

---

_Verified: 2026-05-26T22:00:00Z_
_Verifier: Claude (gsd-verifier)_
