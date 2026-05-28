# Phase 3: Logic/Widget Separation - Research

**Researched:** 2026-05-27
**Domain:** PySide6 (Qt) UI/logic separation, refactor estructural sin cambios de comportamiento
**Confidence:** HIGH

## Summary

Phase 3 cierra ARCH-02 y ARCH-04: ningún widget de `WatermarkRemove/ui/` debe contener lógica de dominio inline, y `WatermarkTab` debe quedar como coordinador puro. La buena noticia es que el SlideshowViewer ya quedó como composer puro tras Phase 2 (280 líneas, lógica distribuida en `NavigationController`/`WatermarkProcessor`/`TrainingDataCollector`). Phase 3 ataca los dos widgets que Phase 2 NO tocó: `position_editor.py` (611 líneas, contiene la mayor concentración de lógica de dominio del módulo) y `image_viewer.py` (250 líneas, ligero). Y revisa `watermark_tab.py` (265 líneas).

Tras leer el código real, la distribución de deuda es muy desigual:
- **`position_editor.py` es el objetivo principal.** Contiene cálculo de alineación (`align_watermark`), ejecución de `remove_watermark`, conversión cv2→QPixmap, carga de imágenes/marcas desde disco con `load_images_cv2`+`natsorted`, escaneo del directorio `marcas/`, y persistencia directa a `wm_positions.json` vía `UtilJson` (no usa el `WmPersistenceService` de Phase 1). Toda esta lógica vive inline en el `QDialog`.
- **`watermark_tab.py` está casi limpio ya** — su "lógica de negocio" real es: detección del registro de Windows para el menú contextual (`winreg`), registro/desregistro vía `register_context_menu`, y orquestación del chequeo de actualizaciones (`UpdateChecker`). Estas son responsabilidades de dominio que deben moverse a servicios para satisfacer ARCH-04 estrictamente.
- **`image_viewer.py` es casi todo presentación** — solo el escaneo de carpeta + filtro de extensiones (`_load_images`) es lógica de dominio extraíble; el resto es construcción de thumbnails (presentación legítima).

**Hallazgo crítico de contrato:** el método público es `set_settings()`, NO `apply_settings()` (CLAUDE.md y ROADMAP dicen `apply_settings` por error — discrepancia ya flagueada en `01-REVIEW.md` IN-01). Además, `gui/controller.py` **no llama** `get_settings`/`set_settings` en absoluto — solo lee `watermark_tab.run_quita_marcas.isChecked()` directamente (línea 317) e instancia `WatermarkTab()` (línea 76). Esto significa que el contrato externo real a preservar es: (1) el constructor `WatermarkTab()` sin args, (2) el atributo `run_quita_marcas` accesible, (3) el método `log()` (lo usan los componentes de Phase 2 vía `watermark_tab.log`). Los métodos `get_settings`/`set_settings` deben preservarse por la constraint declarada aunque hoy no tengan callers.

**Primary recommendation:** Extraer la lógica de dominio de `position_editor.py` a un servicio sin estado de UI (p.ej. `PositionEditorService` o reutilizar piezas existentes) y migrar su persistencia al patrón Phase 1; mover `winreg`/menú contextual y `UpdateChecker` de `watermark_tab.py` a servicios; extraer el escaneo de carpeta de `image_viewer.py`. Seguir el patrón Signal/Slot + servicios ya establecido en Phase 2 — no inventar uno nuevo.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Cálculo de alineación de marca (`align_watermark`) | Servicio de dominio (`wm_remove`) | — | Ya existe en `wm_remove.py`; el widget solo debe invocar, no embeber la orquestación |
| Ejecución de `remove_watermark` + preview cv2→QPixmap | Servicio de dominio | Widget (solo `setPixmap`) | La generación del preview es dominio; mostrar el QPixmap es presentación |
| Carga de imágenes/marcas desde disco (`load_images_cv2`, escaneo `marcas/`, `natsorted`) | Servicio de dominio | — | I/O + filtrado de extensiones = lógica de dominio, no presentación |
| Persistencia de posiciones a `wm_positions.json` | Servicio de persistencia | — | Debe usar el patrón Phase 1, no `UtilJson` directo en el widget |
| Detección/registro de menú contextual Windows (`winreg`, `register_context_menu`) | Servicio (OS integration) | Widget (solo botón + texto) | Lógica de OS-state; el widget solo dispara y refleja estado |
| Chequeo de actualizaciones (`UpdateChecker`) | Servicio (ya existe: `core.services.update_checker`) | Widget (solo diálogo) | El widget orquesta hoy; debe solo invocar el servicio y mostrar resultado |
| Escaneo de carpeta + filtro de extensiones (`image_viewer`) | Servicio de dominio | Widget (grid de thumbnails) | El escaneo es dominio; construir thumbnails es presentación legítima |
| Construcción de thumbnails / grid / zoom label | Widget (presentación) | — | Presentación pura — se queda en el widget |
| Coordinación de señales UI ↔ servicios | Widget coordinador (`WatermarkTab`) | — | ARCH-04: el coordinador conecta, no decide lógica de dominio |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | ya instalado (existente) | Framework UI (QWidget/QDialog, Signal/Slot) | Constraint dura de CLAUDE.md — no migrar a otro framework `[CITED: CLAUDE.md]` |
| numpy | ya instalado | Arrays de imagen (cv2 los retorna) | Usado por `wm_remove`/`position_editor` existente `[VERIFIED: codebase grep]` |
| opencv-python (cv2) | ya instalado | Procesamiento de imagen + color convert | Usado en `position_editor._update_preview` `[VERIFIED: codebase grep]` |
| natsort | ya instalado | Orden natural de archivos | Usado en `position_editor`/`image_viewer`/`slideshow_viewer` `[VERIFIED: codebase grep]` |

**No se instalan paquetes nuevos.** Phase 3 es redistribución estructural pura sobre el stack existente.

### Servicios y módulos internos ya existentes (reutilizar, no recrear)
| Módulo/Servicio | Ubicación | Qué provee | Cómo se usa en Phase 3 |
|------|-----------|------------|-------------|
| `WmPersistenceService` (`wm_persistence`) | `WatermarkRemove/services/` | get/set crop pixels + last watermark folder sobre `wm_settings.json` | Patrón a seguir para mover persistencia fuera del widget; NO maneja `wm_positions.json` aún |
| `wm_remove` (público) | `WatermarkRemove/wm_remove.py` | `load_images_cv2`, `align_watermark`, `remove_watermark`, `find_wm`, `guardar`, `load_positions`, `generar_mascara_watermark`, `cargar_lotes_imagenes` | Lógica de dominio que el widget debe invocar vía servicio, no embeber `[VERIFIED: codebase grep]` |
| `auto_detector` | `WatermarkRemove/yolo/auto_detector.py` | `detect_watermarks`, `resolve_png_for_class` | API pública a preservar (Out of Scope tocarla) |
| `training_collector` | `WatermarkRemove/yolo/training_collector.py` | `save_training_sample`, `remove_training_sample` | Ya usado por `TrainingDataCollector` (Phase 2) |
| `UtilJson` | `utils/` | Lectura/escritura JSON cruda | `position_editor._save_to_json` lo usa directo — debe encapsularse en servicio |
| `UpdateChecker` | `core.services.update_checker` | `check_for_updates()` | Servicio ya existe; `watermark_tab` solo debe invocarlo |
| `register_context_menu` | raíz del repo (módulo top-level) | `register()` / `unregister()` | Lógica OS; encapsular detección+toggle en servicio |
| `WatermarkProcessor` / `NavigationController` / `TrainingDataCollector` | `WatermarkRemove/ui/components/` | Componentes de Phase 2 (manual/auto/crop/nav/training) | Molde de patrón Signal/Slot a replicar; NO son destino de la lógica de position_editor (es otro flujo) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Crear `PositionEditorService` nuevo | Reusar `WatermarkProcessor` | `WatermarkProcessor` es del flujo slideshow (manual/auto/crop con state propio); el `PositionEditor` es un flujo distinto (batch de posiciones por marca). Acoplarlos crearía un God Service. Mejor un servicio dedicado o funciones puras `[ASSUMED]` |
| Servicio con estado (clase) para position editor | Funciones puras en un módulo `position_logic.py` | El editor tiene estado de sesión (`saved_positions`, índice actual). Un servicio ligero con métodos puros + el estado de sesión en el widget es lo más limpio. Decidir en discuss/plan `[ASSUMED]` |
| Mover persistencia a `WmPersistenceService` | Crear método específico para `wm_positions.json` | `WmPersistenceService` hoy solo maneja `wm_settings.json`. `wm_positions.json` tiene estructura anidada (carpeta→marca→pos_N). Extender el servicio o crear uno paralelo — Out of Scope dice "no tocar el formato" pero NO prohíbe encapsular su acceso `[CITED: REQUIREMENTS.md Out of Scope]` |

## Package Legitimacy Audit

> No external packages are installed in this phase. Phase 3 is pure structural redistribution over the existing stack (PySide6, numpy, cv2, natsort — all already present and used in prior phases).

**Packages removed due to slopcheck [SLOP] verdict:** none (no installs)
**Packages flagged as suspicious [SUS]:** none (no installs)

## Architecture Patterns

### System Architecture Diagram

```
                         WatermarkTab (coordinador puro — ARCH-04)
                         ┌──────────────────────────────────────┐
   usuario click ───────>│  run_quita_marcas (checkbox)          │
                         │  view_images_btn ──┐                  │
                         │  edit_positions_btn ┐                 │
                         │  context_menu_btn ──┼─┐               │
                         │  check_updates_btn ─┼─┼─┐             │
                         │  log() / process_console (presentación)│
                         └────────┬────────────┼─┼─┼─────────────┘
                                  │            │ │ │
              (conecta señal → servicio, sin lógica de dominio inline)
                                  │            │ │ │
            ┌─────────────────────┘            │ │ └──────────────┐
            v                                  │ └────────┐       v
   ┌─────────────────┐                         v          v   ┌──────────────────┐
   │  ImageViewer    │              ┌──────────────────┐  │   │ UpdateChecker     │
   │ (QDialog)       │              │ ContextMenuService│  │   │ (core.services)   │
   │  grid thumbnails│              │ (winreg detect +  │  │   │ check_for_updates │
   │  ← FolderScan-  │              │  register/unreg)  │  │   └──────────────────┘
   │    Service      │              └──────────────────┘  │
   └─────────────────┘                                    v
            ^                              ┌──────────────────────────┐
            │                              │  PositionEditor (QDialog) │
   ┌─────────────────────┐                │  controles + zoom + grid  │
   │ FolderScanService   │                │  (PRESENTACIÓN solamente) │
   │ scan + ext filter   │                └────────────┬──────────────┘
   │ (natsorted)         │                             │
   └─────────────────────┘          (invoca servicio, no embebe dominio)
                                                        v
                              ┌──────────────────────────────────────────┐
                              │ PositionEditorService (lógica de dominio)  │
                              │  load_images_cv2 / align_watermark /       │
                              │  remove_watermark / cv2→QPixmap preview /  │
                              │  scan marcas/ folders /                    │
                              │  persistencia wm_positions.json            │
                              └──────────────────────────────────────────┘
                                            │            │
                                            v            v
                              ┌──────────────────┐  ┌──────────────────┐
                              │ wm_remove (dominio)│  │ persistencia JSON │
                              │ align/remove/load  │  │ (patrón Phase 1)  │
                              └──────────────────┘  └──────────────────┘
```

El reader puede trazar el caso principal: usuario abre editor → widget pide a `PositionEditorService` cargar imagen+marca → servicio calcula preview con `align_watermark`/`remove_watermark` → widget solo hace `setPixmap` → usuario guarda → servicio persiste a `wm_positions.json`. El widget nunca toca cv2 ni `align_watermark` directamente.

### Recommended Project Structure
```
WatermarkRemove/
├── services/
│   ├── __init__.py                # barrel: wm_persistence (+ nuevos servicios)
│   ├── wm_persistence.py          # Phase 1 — existente
│   ├── position_editor_service.py # NUEVO — lógica de dominio de PositionEditor
│   ├── folder_scan_service.py     # NUEVO (o función) — escaneo + filtro ext (compartido viewer/editor)
│   └── context_menu_service.py    # NUEVO — winreg detect + register/unregister
├── ui/
│   ├── watermark_tab.py           # coordinador puro (ARCH-04)
│   ├── image_viewer.py            # presentación (usa folder_scan_service)
│   ├── position_editor.py         # presentación (usa position_editor_service)
│   ├── slideshow_viewer.py        # composer puro (Phase 2 — no tocar salvo necesidad)
│   └── components/                # Phase 2 — no tocar
```

> Las decisiones exactas de nombres/granularidad de servicios son discreción del planner/discuss. Lo arquitectónicamente requerido por ARCH-02/ARCH-04 es: la lógica de dominio sale del widget. La estructura arriba es una recomendación, no un mandato.

### Pattern 1: Widget invoca servicio, no embebe dominio
**What:** El widget mantiene su estado de UI (índice actual, valores de spinbox) pero delega cualquier cálculo de imagen, I/O, o persistencia a un servicio. El widget solo traduce eventos UI → llamadas de servicio → actualización de presentación.
**When to use:** Toda extracción de lógica de `position_editor`, `image_viewer`, `watermark_tab`.
**Example (patrón objetivo — basado en el `_update_preview` actual que hay que extraer):**
```python
# ANTES (position_editor.py:474-506 — dominio inline en el widget):
def _update_preview(self):
    img_copy = self.current_image.copy()
    x, y = align_watermark(img_copy, self.current_watermark,
                           offset_x=self.offset_x, offset_y=self.offset_y,
                           side_x=self.side_x, side_y=self.side_y)
    result_img = remove_watermark(img_copy, self.current_watermark, x, y)
    result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
    # ... QImage/QPixmap construction inline ...
    self.image_label.set_image(pixmap)

# DESPUÉS (objetivo — el widget solo coordina):
def _update_preview(self):
    if self.current_image is None or self.current_watermark is None:
        return
    pixmap = self.service.build_preview_pixmap(
        self.current_image, self.current_watermark,
        offset_x=self.offset_x, offset_y=self.offset_y,
        side_x=self.side_x, side_y=self.side_y,
    )
    self.image_label.set_image(pixmap)
    # el resize de ventana puede quedar (es presentación) o moverse según se decida
```
*Fuente: derivado del código real en `WatermarkRemove/ui/position_editor.py` — patrón de extracción.* `[VERIFIED: codebase grep]`

### Pattern 2: Servicio sin Qt cuando es posible / con Qt cuando construye QPixmap
**What:** La lógica de I/O y cálculo numérico (cv2/numpy) puede vivir en un servicio sin dependencias Qt. La construcción de `QPixmap` (presentación-adjacente) puede quedar en el servicio o en un helper. Decisión de diseño.
**When to use:** `PositionEditorService` — separar el cómputo del watermark (sin Qt) de la conversión cv2→QPixmap (con Qt).
**Note:** El proyecto NO tiene tests automatizados (ARCH-05 deferred a v2), así que la separación "servicio sin Qt = testeable" no es un beneficio inmediato — pero sigue siendo la dirección correcta. `[CITED: REQUIREMENTS.md ARCH-05 deferred]`

### Pattern 3: Servicio de OS-state con detección + toggle (menú contextual)
**What:** Encapsular la detección de registro (`winreg.OpenKey`) y el `register/unregister` en un servicio que expone `is_registered() -> bool` y `toggle()`. El widget solo refresca el texto del botón según el estado.
**When to use:** Extraer `_is_context_menu_registered`, `_toggle_context_menu` de `watermark_tab.py`.

### Anti-Patterns to Avoid
- **Mover lógica de un widget a OTRO widget:** ARCH-02 exige que la lógica salga de TODOS los widgets, no que se reubique entre ellos. El destino es un servicio, no `WatermarkProcessor` ni otro `QWidget`.
- **Acoplar `PositionEditor` al flujo del slideshow:** son dos flujos independientes. No reusar `WatermarkProcessor` para el editor de posiciones — crearía un God Service y violaría la responsabilidad única que Phase 2 estableció.
- **Romper el formato de `wm_positions.json`:** Out of Scope explícito. Encapsular el ACCESO al archivo está bien; cambiar su ESTRUCTURA no. `[CITED: REQUIREMENTS.md Out of Scope]`
- **Renombrar `set_settings` a `apply_settings` sin alias:** ver Pitfall 1. La constraint dice `apply_settings` pero el código real es `set_settings`. Mantener ambos.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Alineación de marca de agua | Cálculo de coords manual | `wm_remove.align_watermark` (existente) | Ya implementado y probado; la lógica de dominio vive ahí, el widget solo lo invoca `[VERIFIED]` |
| Remoción de marca | Loop de píxeles propio | `wm_remove.remove_watermark` (existente) | Out of Scope tocar `remove_watermark` `[CITED: REQUIREMENTS.md]` |
| Carga de imagen con paths Unicode | `cv2.imread` directo | `wm_remove.load_images_cv2` (usa `np.fromfile`) | Maneja paths con caracteres no-ASCII (Windows) — `cv2.imread` falla con ellos `[VERIFIED: codebase grep]` |
| Persistencia JSON | `json.dump` crudo en el widget | Servicio sobre `UtilJson` (patrón Phase 1) | Parseo defensivo, preservación de claves existentes ya resueltos `[VERIFIED]` |
| Chequeo de actualizaciones | Llamadas HTTP propias | `core.services.update_checker.UpdateChecker` (existente) | Ya existe; el widget solo orquesta hoy `[VERIFIED: codebase grep]` |
| Orden natural de archivos | `sorted()` lexicográfico | `natsort.natsorted` (existente) | "10.png" después de "9.png", no antes `[VERIFIED]` |

**Key insight:** Casi toda la lógica de dominio que Phase 3 debe extraer YA EXISTE en módulos correctos (`wm_remove`, `UpdateChecker`, `register_context_menu`). El problema no es que falten servicios — es que los widgets los **llaman inline mezclados con código de UI**. La extracción consiste en mover esas llamadas a una capa de servicio delgada y dejar el widget como traductor de eventos.

## Runtime State Inventory

> Esta es una refactorización de separación lógica/UI sobre un mismo proceso desktop. No hay rename de strings ni migración de datos persistidos. Aun así se revisan las 5 categorías por disciplina.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `wm_positions.json` (escrito por `position_editor._save_to_json`), `wm_settings.json` (Phase 1), `training_data.json`. **Ninguno cambia de formato ni de clave** — solo cambia QUÉ módulo los escribe (widget → servicio) | Code edit (mover el call site). Sin data migration — el contenido y estructura son idénticos |
| Live service config | Ninguno. El módulo es 100% desktop local; no hay servicios externos con config en UI/DB. **None — verificado: no hay n8n/Datadog/etc en el repo** | none |
| OS-registered state | **Menú contextual de Windows** (`HKEY_CURRENT_USER\Software\Classes\Directory\shell\SmartStitchWR`) detectado/registrado por `watermark_tab._toggle_context_menu` vía `register_context_menu`. La clave del registro NO cambia — solo se mueve el CÓDIGO que la lee/escribe a un servicio | Code edit (mover a `ContextMenuService`). La entrada del registro queda intacta; el comportamiento observable es idéntico |
| Secrets/env vars | Ninguno. No hay secrets ni env vars en el módulo. **None — verificado por grep** | none |
| Build artifacts | Ninguno relevante. No hay rename de paquete ni de `pyproject.toml`. `position_editor_old.py` existe como artefacto legacy pero NO se importa (`__init__.py` importa `position_editor`, no `_old`) | none. Considerar si borrar `position_editor_old.py` es deseable (limpieza opcional, fuera de scope estricto) |

**The canonical question — tras mover toda la lógica a servicios, ¿qué runtime tiene el viejo comportamiento cacheado?** Nada. Es un mismo proceso; al reiniciar la app los servicios nuevos toman el control. La única "state externa" es la clave de registro de Windows del menú contextual, y esa NO cambia de nombre ni de valor — solo el código que la maneja se reubica.

## Common Pitfalls

### Pitfall 1: Confundir el contrato `apply_settings` vs `set_settings`
**What goes wrong:** CLAUDE.md, ROADMAP y STATE dicen que `WatermarkTab.apply_settings()` debe preservarse. El código real implementa `set_settings()` — `apply_settings` **no existe**. Si el plan renombra ciegamente a `apply_settings`, rompería cualquier futuro caller de `set_settings`; si exige que `apply_settings` "siga funcionando", está exigiendo que algo que no existe siga existiendo.
**Why it happens:** Inconsistencia de naming pre-existente, ya documentada en `01-REVIEW.md` IN-01 (sugería `apply_settings = set_settings` como alias).
**How to avoid:** Mantener `set_settings()` (es el método real) Y agregar el alias `apply_settings = set_settings` (o un método delegado) para cumplir la constraint literal sin romper nada. Verificar con grep que NINGÚN caller externo usa ninguno hoy (confirmado: `gui/` no llama ninguno — solo `run_quita_marcas.isChecked()` directo).
**Warning signs:** `AttributeError: 'WatermarkTab' object has no attribute 'apply_settings'` si algún código futuro lo invoca.

### Pitfall 2: El contrato externo REAL no son `get_settings`/`set_settings`
**What goes wrong:** Asumir que preservar `get_settings`/`set_settings` es suficiente. En realidad `gui/controller.py` accede a `watermark_tab.run_quita_marcas.isChecked()` (línea 317) directamente al atributo del checkbox, e instancia `WatermarkTab()` sin args (línea 76). Si el refactor encapsula `run_quita_marcas` detrás de una property o lo renombra, **rompe el controller** aunque `get_settings` siga existiendo.
**Why it happens:** El acoplamiento real es atributo-a-atributo, no método-a-método.
**How to avoid:** Preservar: (1) constructor `WatermarkTab()` sin args, (2) atributo público `run_quita_marcas` (QCheckBox), (3) método `log(message)` (lo usan `NavigationController`/`WatermarkProcessor`/`TrainingDataCollector`/`SlideshowViewer` vía `watermark_tab.log`), (4) `get_settings`/`set_settings`. Verificar `git diff gui/controller.py` vacío al final (misma verificación que Phases 1-2).
**Warning signs:** El flujo "Ejecutar Quita Marcas" no abre el slideshow, o `AttributeError` sobre `run_quita_marcas` / `log`.

### Pitfall 3: Romper `load_images_cv2` por usar `cv2.imread` en el servicio extraído
**What goes wrong:** Al extraer la carga de imágenes a un servicio, reescribir con `cv2.imread(str(path))` en vez de reusar `load_images_cv2`. `cv2.imread` falla silenciosamente (retorna None) con paths que contienen caracteres no-ASCII (común en nombres de manhwa/manga coreanos/japoneses).
**Why it happens:** `load_images_cv2` usa `np.fromfile(str(path))` + `cv2.imdecode` precisamente para esquivar este bug de cv2 en Windows.
**How to avoid:** El servicio extraído DEBE seguir llamando `wm_remove.load_images_cv2`, no `cv2.imread` directo. Es lógica de dominio existente — reusar, no reescribir.
**Warning signs:** Imágenes con nombres no-ASCII muestran "Error cargando imagen" o preview vacío.

### Pitfall 4: Persistencia con triple-vs-doble `dirname` según profundidad del módulo
**What goes wrong:** `position_editor._save_to_json` calcula `wm_dir = os.path.dirname(current_dir)` (un nivel arriba desde `WatermarkRemove/ui/`). Si la lógica se mueve a `WatermarkRemove/services/` (también un nivel bajo el package), el cálculo de path cambia. Phase 2 ya pisó esta mina exactamente (ver `02-02-SUMMARY` deviation #1: `components/` está DOS niveles bajo el package, requirió `dirname(dirname(__file__))`).
**Why it happens:** El path a `wm_positions.json` se calcula relativo a `__file__`, que cambia según dónde viva el módulo.
**How to avoid:** El servicio debe calcular el path a `wm_positions.json` según SU propia ubicación. `services/` está un nivel bajo `WatermarkRemove/`, igual que `ui/`, así que `dirname(dirname(__file__))` llega a `WatermarkRemove/`. Verificar que el archivo escrito sea exactamente `WatermarkRemove/wm_positions.json` (mismo destino que hoy). Idealmente encapsular en un servicio de persistencia que calcule el path una vez.
**Warning signs:** Se crea un `wm_positions.json` en una carpeta equivocada; las posiciones guardadas no aparecen al recargar.

### Pitfall 5: Romper el comportamiento de "Guardar y Siguiente" / avance de índice
**What goes wrong:** `position_editor._save_and_next` mezcla lógica de dominio (acumular `saved_positions`, persistir al final) con lógica de presentación (avanzar índice, resetear zoom slider, mostrar QMessageBox). Si se extrae torpemente, se puede perder el comportamiento de "guardar solo al llegar a la última imagen" o duplicar el `_save_to_json`.
**Why it happens:** El método tiene responsabilidades mezcladas — acumulación + navegación + persistencia + feedback.
**How to avoid:** Separar: el servicio acumula y persiste; el widget controla índice/zoom/diálogo. Mantener el comportamiento observable idéntico (guarda al final del batch, muestra el conteo). Verificación manual UAT obligatoria — no hay tests automatizados.
**Warning signs:** Posiciones guardadas de más/de menos; el diálogo "Completado" aparece en el momento equivocado.

## Code Examples

### Patrón de servicio de persistencia (basado en Phase 1, a extender para wm_positions)
```python
# Patrón EXISTENTE en WatermarkRemove/services/wm_persistence.py — molde a seguir:
class WmPersistenceService:
    def __init__(self):
        self._path = os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')

    def get_last_crop_pixels(self) -> int:
        return UtilJson(self._path).get('last_crop_pixels', 0) or 0
    # ... NO cachea: cada llamada crea UtilJson y lee/escribe (consistente con el original)
```
*Fuente: `WatermarkRemove/services/wm_persistence.py` (Phase 1).* `[VERIFIED: codebase grep]`

### Patrón de logging hacia el coordinador (preservar)
```python
# Patrón EXISTENTE en los 3 componentes de Phase 2 — el coordinador es WatermarkTab:
def _log(self, message: str):
    if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
        self.watermark_tab.log(message)
    else:
        print(message)
```
*Fuente: `navigation_controller.py:121`, `watermark_processor.py:143`, `training_data_collector.py:90`.* `[VERIFIED: codebase grep]` — `WatermarkTab.log()` debe preservarse porque estos componentes dependen de él.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| God Class `SlideshowViewer` (2041 líneas) | Composer + 3 componentes Signal/Slot | Phase 2 (2026-05-27) | Molde establecido para Phase 3 |
| Persistencia `UtilJson` directa en widgets | `WmPersistenceService` (Phase 1) | Phase 1 (2026-05-26) | `position_editor` aún NO migrado — Phase 3 lo aborda |
| Lógica de dominio inline en `position_editor`/`image_viewer`/`watermark_tab` | Lógica en servicios; widgets coordinan | Phase 3 (objetivo) | ARCH-02 + ARCH-04 |

**Deprecated/outdated:**
- `WatermarkRemove/ui/position_editor_old.py`: artefacto legacy, NO importado por `__init__.py` (importa `position_editor`). Candidato a borrado opcional (no en scope estricto).
- `SettingsHandler`+`UtilJson` duplicación: ya unificada en Phase 1 (ARCH-03 complete).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Crear un `PositionEditorService` dedicado (no reusar `WatermarkProcessor`) es la separación correcta | Alternatives / Anti-Patterns | Bajo — si discuss decide otro nombre/granularidad, el principio (lógica fuera del widget) se mantiene |
| A2 | Funciones puras + estado de sesión en el widget es preferible a un servicio con estado completo | Alternatives | Bajo — decisión de diseño, ambas satisfacen ARCH-02 |
| A3 | Extender `WmPersistenceService` o crear servicio paralelo para `wm_positions.json` es aceptable mientras NO cambie el formato | Alternatives / Pitfall 4 | Medio — si el plan cambia la estructura del JSON, viola Out of Scope. Confirmar en discuss que solo se encapsula el acceso |
| A4 | `get_settings`/`set_settings` no tienen callers externos hoy (solo `run_quita_marcas.isChecked()` directo) | Summary / Pitfall 2 | Bajo — verificado por grep en todo el repo (excluyendo .planning); confirmado 0 hits fuera del propio archivo |
| A5 | El menú contextual y el update check cuentan como "lógica de negocio" que ARCH-04 exige sacar del coordinador | Responsibility Map | Medio — interpretación de ARCH-04. Si el usuario considera que orquestar diálogos es aceptable en el coordinador, el alcance de `watermark_tab` se reduce. Confirmar en discuss |

## Open Questions

1. **¿`PositionEditorService` debe construir el QPixmap (depende de Qt) o solo retornar el array cv2?**
   - What we know: El preview necesita cv2→QImage→QPixmap. Hoy todo está inline en el widget.
   - What's unclear: Si el servicio debe ser Qt-free (retorna ndarray, widget convierte) o conveniente (retorna QPixmap).
   - Recommendation: Sin tests automatizados (ARCH-05 deferred), la pureza Qt-free no da beneficio inmediato. Sugerir que el servicio retorne QPixmap por conveniencia, o un helper de conversión separado. Decidir en plan.

2. **¿Cuánto de `watermark_tab.py` cuenta como "lógica de negocio"?**
   - What we know: `_open_image_viewer`/`_open_position_editor` solo instancian diálogos (coordinación legítima). `_is_context_menu_registered`/`_toggle_context_menu` tocan `winreg` (dominio OS). `_check_for_updates` orquesta `UpdateChecker` + diálogo.
   - What's unclear: ARCH-04 dice "no contiene lógica de negocio inline". ¿Orquestar un diálogo de update es "lógica"? ¿El acceso a `winreg` claramente sí?
   - Recommendation: Mover `winreg` (claramente dominio OS) a servicio. El update check ya delega a `UpdateChecker` — solo extraer el `try/except` + estado del botón si se quiere ser estricto. Confirmar nivel de rigor en discuss (ver A5).

3. **¿Borrar `position_editor_old.py`?**
   - What we know: No se importa; es legacy.
   - What's unclear: Si está fuera de scope estricto o es limpieza bienvenida.
   - Recommendation: Limpieza opcional; mencionar en plan pero no bloquear.

4. **¿Hay UAT manual definido para Phase 3 (como `02-HUMAN-UAT.md`)?**
   - What we know: Phase 2 usó UAT manual con secciones; no hay tests automatizados.
   - What's unclear: Phase 3 necesitará su propio guion UAT (abrir editor → cargar imagen/marca → ajustar offset → guardar → recargar y verificar persistencia; abrir viewer → ver thumbnails; menú contextual register/unregister; update check).
   - Recommendation: El plan debe incluir un checkpoint human-verify con guion UAT cubriendo SC-4 (flujo completo sin regresión).

## Environment Availability

> Phase 3 es refactor de código sobre dependencias ya presentes y en uso por Phases 1-2. No introduce dependencias externas nuevas.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PySide6 | Todo el módulo UI | ✓ (usado Phases 1-2) | existente | — |
| numpy | cv2 arrays | ✓ | existente | — |
| opencv-python (cv2) | preview/color convert | ✓ | existente | — |
| natsort | orden de archivos | ✓ | existente | — |
| `winreg` (stdlib Windows) | menú contextual | ✓ (Windows-only) | stdlib | El código ya maneja `FileNotFoundError`; en no-Windows el botón simplemente no aplica |

**Missing dependencies with no fallback:** ninguna.
**Missing dependencies with fallback:** ninguna.

## Validation Architecture

> `nyquist_validation: true` en config. Sin embargo, este proyecto NO tiene framework de tests automatizados (ARCH-05 — tests unitarios — está deferred a v2). La "validación" de Phases 1-2 fue: `py_compile` + grep semántico + smoke test runtime (`QApplication` + instanciación) + UAT manual con sign-off humano. Phase 3 sigue el mismo patrón.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Ninguno automatizado (ARCH-05 deferred a v2) |
| Config file | none — no hay pytest.ini/jest/etc en el repo |
| Quick run command | `python -m py_compile <archivos del plan>` |
| Full suite command | Smoke runtime: `python -c "from PySide6.QtWidgets import QApplication; import sys; app=QApplication(sys.argv); from WatermarkRemove.ui import WatermarkTab, PositionEditor, ImageViewer; WatermarkTab(); print('OK')"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ARCH-02 | Ningún widget en `ui/` tiene lógica de dominio inline | grep negativo | `grep -cE "align_watermark\(\|remove_watermark\(\|load_images_cv2\(\|cv2\.\|UtilJson\(\|winreg\." WatermarkRemove/ui/position_editor.py WatermarkRemove/ui/image_viewer.py WatermarkRemove/ui/watermark_tab.py` → debe tender a 0 (solo imports/coordinación quedan) | grep — ❌ Wave 0 (definir patrón exacto en plan) |
| ARCH-04 | `WatermarkTab` solo conecta señales con servicios | grep + review | grep de `winreg`/`UpdateChecker` inline en watermark_tab.py → 0 | grep |
| SC-1 (contrato) | `get_settings`/`set_settings`/`apply_settings`/`run_quita_marcas`/`log` preservados; `gui/controller.py` sin cambios | smoke + git diff | `git diff gui/controller.py` (vacío) + smoke instanciación + `hasattr` checks | ✅ patrón Phases 1-2 |
| SC-4 (flujo completo) | abrir imágenes → detectar/remover → guardar sin regresión | manual UAT | checkpoint human-verify (guion UAT) | ❌ Wave 0 (crear guion UAT) |

### Sampling Rate
- **Per task commit:** `python -m py_compile <archivos tocados>` + grep semántico del task
- **Per wave merge:** smoke runtime (instanciar `WatermarkTab`/`PositionEditor`/`ImageViewer`) + `git diff gui/controller.py` vacío
- **Phase gate:** UAT manual completo + grep negativos de dominio en widgets en 0

### Wave 0 Gaps
- [ ] Guion UAT manual de Phase 3 (análogo a `02-HUMAN-UAT.md`): editor de posiciones (cargar/ajustar/guardar/recargar), viewer (thumbnails), menú contextual (register/unregister), update check
- [ ] Definir el patrón grep exacto de "lógica de dominio en widget" que cuenta como 0 (qué símbolos: `align_watermark(`, `remove_watermark(`, `load_images_cv2(`, `cv2.`, `UtilJson(`, `winreg.`, `UpdateChecker(`)
- [ ] No se requiere instalar framework de tests (ARCH-05 deferred)

*(No hay infraestructura de tests automatizados; la validación es compile + grep + smoke + UAT manual, consistente con Phases 1-2.)*

## Security Domain

> `security_enforcement: true`, `security_asvs_level: 1` en config. Phase 3 es redistribución estructural pura — sin nuevas superficies de ataque, sin nuevos endpoints, sin nuevos paths de filesystem (hereda las mitigaciones existentes, igual que Phases 1-2 documentaron en sus Threat Flags).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | App desktop local, sin auth |
| V3 Session Management | no | Sin sesiones |
| V4 Access Control | no | Sin control de acceso multiusuario |
| V5 Input Validation | parcial | Paths de archivo: `load_images_cv2` usa `np.fromfile(str(path))`; filtros de extensión (`SUPPORTED_FORMATS`) ya validan tipos. El refactor debe PRESERVAR estos guards, no introducir `cv2.imread` crudo (Pitfall 3) |
| V6 Cryptography | no | Sin criptografía |

### Known Threat Patterns for {PySide6 desktop / filesystem}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path con caracteres no-ASCII rompe carga (no es ataque, es robustez) | — | `load_images_cv2` con `np.fromfile` — preservar al extraer |
| JSON corrupto/malformado en `wm_positions.json` | Tampering/DoS | `UtilJson` con parseo defensivo (try/except) — preservar vía servicio |
| Modificación del registro de Windows (menú contextual) | Tampering | Ya gestionado por `register_context_menu`; solo se reubica el call site, no se cambia el alcance del registro |

**Conclusión de seguridad:** Sin nuevos vectores. La verificación de seguridad de Phase 3 es confirmar que los guards existentes (`load_images_cv2`, parseo JSON defensivo, manejo de `winreg.FileNotFoundError`) se PRESERVAN al moverse a servicios — no que se introduzcan nuevos.

## Sources

### Primary (HIGH confidence)
- `WatermarkRemove/ui/watermark_tab.py` (265 líneas) — coordinador actual, API `get_settings`/`set_settings`, menú contextual, update check
- `WatermarkRemove/ui/position_editor.py` (611 líneas) — mayor concentración de lógica de dominio (align/remove/cv2/load/persist)
- `WatermarkRemove/ui/image_viewer.py` (250 líneas) — escaneo de carpeta + thumbnails
- `WatermarkRemove/ui/slideshow_viewer.py` (303 líneas) — composer puro de Phase 2 (molde de patrón)
- `WatermarkRemove/ui/components/{navigation_controller,watermark_processor,training_data_collector}.py` — patrón Signal/Slot + `_log` hacia `watermark_tab`
- `WatermarkRemove/services/wm_persistence.py` — patrón de servicio de persistencia (Phase 1)
- `WatermarkRemove/wm_remove.py` + `WatermarkRemove/__init__.py` — API pública de dominio
- `gui/controller.py:76,317,321` — contrato externo REAL (instanciación + `run_quita_marcas.isChecked()` + `SlideshowViewer`)
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md`, `.planning/STATE.md`, `CLAUDE.md` — requisitos y constraints
- `.planning/phases/02-slideshowviewer-decomposition/02-0{1,2,3}-SUMMARY.md` — patrones establecidos y minas pisadas
- `.planning/phases/01-json-persistence/01-REVIEW.md` IN-01 — discrepancia `apply_settings` vs `set_settings`

### Secondary (MEDIUM confidence)
- ninguna (todo verificado en codebase)

### Tertiary (LOW confidence)
- ninguna

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — todo verificado en el codebase; no se instala nada nuevo
- Architecture: HIGH — el patrón Signal/Slot + servicios ya está establecido y validado en Phase 2; Phase 3 lo replica
- Pitfalls: HIGH — derivados del código real y de minas documentadas en Phase 2 (path dirname, contrato, load_images_cv2)
- Contrato externo: HIGH — verificado por grep exhaustivo (callers reales identificados)

**Research date:** 2026-05-27
**Valid until:** estable (refactor interno, sin dependencias externas que cambien) — re-verificar solo si Phase 2 se modifica
```
