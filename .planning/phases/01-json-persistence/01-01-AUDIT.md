# Auditoría de Call Sites UtilJson — WatermarkRemove/

**Fase:** 01-json-persistence
**Plan:** 01-01
**Fecha:** 2026-05-26

---

## Sección 1 — Call sites a migrar

Accesos directos a `UtilJson` en `WatermarkRemove/ui/slideshow_viewer.py` que usan `settings.json`
con las keys `last_crop_pixels` y `last_watermark_folder`.

| Archivo | Línea | Operación | Key JSON | Valor default | Acción en 01-02 |
|---------|-------|-----------|----------|---------------|-----------------|
| `WatermarkRemove/ui/slideshow_viewer.py` | 262 | `get` | `last_crop_pixels` | `0` | Reemplazar con `wm_persistence.get_last_crop_pixels()` |
| `WatermarkRemove/ui/slideshow_viewer.py` | 605 | `get` | `last_watermark_folder` | `None` | Reemplazar con `wm_persistence.get_last_watermark_folder()` |
| `WatermarkRemove/ui/slideshow_viewer.py` | 631 | `set` | `last_watermark_folder` | — | Reemplazar con `wm_persistence.set_last_watermark_folder(folder_name)` |
| `WatermarkRemove/ui/slideshow_viewer.py` | 865 | `set` | `last_crop_pixels` | — | Reemplazar con `wm_persistence.set_last_crop_pixels(int(value))` |

**Contexto de cada call site:**

- **Línea 262** (`__init__` / setup_ui): Al inicializar el `QSpinBox` de crop pixels, lee el último valor guardado para restaurar el estado de la UI.
  ```python
  saved_crop = UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).get('last_crop_pixels', 0) or 0
  ```

- **Línea 605** (`_populate_watermark_folders`): Al poblar el combo de carpetas de marcas, lee la última carpeta usada para preseleccionarla.
  ```python
  folder_to_select = UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).get('last_watermark_folder', None)
  ```

- **Línea 631** (`_on_watermark_folder_changed`): Cuando el usuario cambia la carpeta de marcas, guarda el nombre de la nueva selección.
  ```python
  UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).set('last_watermark_folder', folder_name)
  ```

- **Línea 865** (`_on_crop_pixels_changed`): Cuando el usuario cambia el valor de crop pixels, lo persiste.
  ```python
  UtilJson(os.path.join(SETTINGS_REL_DIR, 'settings.json')).set('last_crop_pixels', int(value))
  ```

---

## Sección 2 — Call sites fuera de scope

| Archivo | Línea | Operación | Archivo JSON | Decisión |
|---------|-------|-----------|--------------|----------|
| `WatermarkRemove/ui/position_editor.py` | 578 | `get` / `set` | `wm_positions.json` | **NO migrar — D-03** |
| `WatermarkRemove/wm_remove.py` | 611 | `get` | `wm_positions.json` | **NO migrar — D-03** |
| `WatermarkRemove/ui/watermark_tab.py` | 19 | import | — | **Eliminar import — dead code** (importa `UtilJson` pero nunca la usa en el módulo) |

**Notas:**

- `wm_positions.json` contiene posiciones de watermarks por sitio (datos estructurados del dominio). Queda fuera del scope de ARCH-03 — es un archivo de configuración de posiciones, no de settings de usuario.
- El import de `UtilJson` en `watermark_tab.py` (línea 19: `from utils import UtilJson`) no tiene ningún uso en ese archivo. Es dead code que debe eliminarse en el plan 01-02 al hacer el cleanup de imports.

---

## Sección 3 — Diferencias SettingsHandler vs UtilJson

| Aspecto | SettingsHandler | UtilJson (uso en WM) |
|---------|----------------|----------------------|
| Propósito | Gestiona perfiles de SmartStitch | Persistencia genérica de K/V JSON |
| Archivo JSON | `__settings__/settings.json` | `__settings__/settings.json` (actualmente) → `__settings__/wm_settings.json` (post-migración) |
| Modelos | Requiere `AppProfiles` / `AppSettings` | Sin modelos — operación directa sobre dict |
| Awareness de perfiles | Sí — gestiona perfil actual, switch de perfiles | No — escribe directo al JSON |
| API | `load(key)` / `save(key, value)` con profile state | `get(key, default)` / `set(key, value)` stateless |
| Responsabilidad | Configuración del pipeline SmartStitch | Estado UI del módulo WatermarkRemove |

**Conclusión:** No hay overlap real de responsabilidad. `SettingsHandler` gestiona el pipeline SmartStitch con awareness de perfiles; el uso de `UtilJson` en WatermarkRemove es para estado propio del módulo WM (últimas carpetas, últimos valores de crop). ARCH-03 se satisface **creando un wrapper con nombres de dominio (`WmPersistenceService`) que oculte la instancia de `UtilJson`** — sin tocar `SettingsHandler` ni `settings.json`.

La separación de archivos (`settings.json` para SmartStitch vs `wm_settings.json` para WM) es la forma correcta de desacoplar, no fusionar en el mismo handler.

---

## Sección 4 — Diseño del servicio (contrato)

### Ubicación

| Item | Valor |
|------|-------|
| Archivo del servicio | `WatermarkRemove/services/wm_persistence.py` |
| Clase | `WmPersistenceService` |
| Path del JSON | `os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')` |
| Import de path | `from core.utils.constants import SETTINGS_REL_DIR` |
| Singleton | `wm_persistence` exportado desde `WatermarkRemove/services/__init__.py` |

### API pública (4 métodos — per D-02)

```python
from typing import Optional
from core.utils.constants import SETTINGS_REL_DIR
from utils import UtilJson
import os

class WmPersistenceService:
    """Servicio de persistencia de estado UI del módulo WatermarkRemove.
    
    Wrappea UtilJson con nombres de dominio para desacoplar slideshow_viewer
    de la implementación concreta de persistencia JSON.
    """

    def __init__(self):
        self._path = os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')

    def get_last_crop_pixels(self) -> int:
        """Retorna el último valor de crop pixels. Default: 0."""
        return UtilJson(self._path).get('last_crop_pixels', 0) or 0

    def set_last_crop_pixels(self, value: int) -> None:
        """Persiste el valor de crop pixels."""
        UtilJson(self._path).set('last_crop_pixels', int(value))

    def get_last_watermark_folder(self) -> Optional[str]:
        """Retorna el nombre de la última carpeta de marcas usada. Default: None."""
        return UtilJson(self._path).get('last_watermark_folder', None)

    def set_last_watermark_folder(self, folder_name: str) -> None:
        """Persiste el nombre de la carpeta de marcas seleccionada."""
        UtilJson(self._path).set('last_watermark_folder', folder_name)
```

### Singleton en `WatermarkRemove/services/__init__.py`

```python
from .wm_persistence import WmPersistenceService

wm_persistence = WmPersistenceService()

__all__ = ['wm_persistence', 'WmPersistenceService']
```

### Uso en slideshow_viewer.py (post-migración)

```python
from WatermarkRemove.services import wm_persistence

# Línea 262 (init):
saved_crop = wm_persistence.get_last_crop_pixels()

# Línea 605 (_populate_watermark_folders):
folder_to_select = wm_persistence.get_last_watermark_folder()

# Línea 631 (_on_watermark_folder_changed):
wm_persistence.set_last_watermark_folder(folder_name)

# Línea 865 (_on_crop_pixels_changed):
wm_persistence.set_last_crop_pixels(int(value))
```

### Decisiones de implementación

| Decisión | Razón |
|----------|-------|
| Wrapping stateless (sin cache en memoria) | Consistente con el patrón actual — slideshow_viewer instancia UtilJson en cada call sin cachear |
| Crear `WatermarkRemove/services/` como nuevo paquete | El patrón `services/` existe en `core/services/` — seguir misma convención |
| `WatermarkRemove/services/__init__.py` exporta el singleton | Permite `from WatermarkRemove.services import wm_persistence` — import limpio sin path largo |

---

## Sección 5 — Estrategia de migración de datos

**Sin migración automática.**

Si `__settings__/settings.json` ya contiene `last_crop_pixels` o `last_watermark_folder` (escritas por versiones anteriores de `slideshow_viewer.py`):

1. El servicio `WmPersistenceService` **NO** lee ni migra esos valores de `settings.json`.
2. Al primer `get_last_crop_pixels()`, si `wm_settings.json` no existe o la key está ausente, `UtilJson.get()` retorna el default (`0`).
3. Al primer `get_last_watermark_folder()`, retorna `None` — el combo de carpetas no preseleccionará ninguna.
4. El usuario recupera el estado simplemente usando la UI (el primer uso escribe `wm_settings.json`).
5. Las keys `last_crop_pixels` y `last_watermark_folder` en `settings.json` quedan como **legacy ignoradas** — no se eliminan para no afectar a `SettingsHandler`.

**Justificación:** El estado previo (últimas carpetas/valores usados) es UX convenience, no datos críticos. La pérdida al primer arranque es aceptable y evita código de migración que complique el servicio.

---

## Resumen para implementación (01-02)

Plan 01-02 puede implementar sin leer código adicional:

1. Crear `WatermarkRemove/services/__init__.py` (si no existe) con el singleton `wm_persistence`
2. Crear `WatermarkRemove/services/wm_persistence.py` con `WmPersistenceService` (firma exacta en Sección 4)
3. En `slideshow_viewer.py`: agregar import `from WatermarkRemove.services import wm_persistence` y reemplazar los 4 call sites (líneas 262, 605, 631, 865) según el mapeo de Sección 1
4. En `watermark_tab.py`: eliminar `from utils import UtilJson` (dead code — Sección 2)
5. El import de `UtilJson` y `SETTINGS_REL_DIR` en `slideshow_viewer.py` puede eliminarse si no tiene otros usos — verificar en 01-02
