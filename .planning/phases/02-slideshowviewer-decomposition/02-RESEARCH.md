# Phase 2: SlideshowViewer Decomposition — Research

**Researched:** 2026-05-26
**Domain:** PySide6 QDialog refactoring — extracción de componentes (navegación / procesamiento de watermarks / training data collection) desde un God Class
**Confidence:** HIGH

## Summary

`SlideshowViewer` (`WatermarkRemove/ui/slideshow_viewer.py`) es un `QDialog` de **2041 líneas / 58 métodos** que mezcla cinco responsabilidades distintas: construcción de UI, navegación de imágenes, modo manual de remoción, modo automático YOLO, y recopilación de training data. El grafo del proyecto confirma 58 edges salientes desde la clase (consistente con los "63 actuales" citados en el roadmap — la diferencia se explica por edges adicionales detectados a nivel archivo). El objetivo de la fase es reducir esa cifra a **≤20** distribuyendo las responsabilidades en componentes con propósito único, sin alterar el comportamiento observable.

La estrategia técnica recomendada es **composición de QWidget con señales Qt** — no MVC formal, no inyección de dependencias. Cada responsabilidad extraída vive en un `QWidget` (o `QObject` puro si no tiene UI) en `WatermarkRemove/ui/components/`, comunicándose con `SlideshowViewer` vía `Signal`/slot. El estado compartido (la `working_image` numpy, el `current_index`, el `output_folder`) queda en un único componente "navegador" que actúa como source-of-truth, y los demás componentes lo consultan por slot público o señal. Esta es la forma idiomática de descomposición en Qt y mantiene 100% intacta la API pública usada por `gui/controller.py` (constructor `SlideshowViewer(input_path, MainWindow, watermark_tab=...)` + métodos `get_approved()`, `get_output_folder()`, `has_processed_images()`).

**Primary recommendation:** Descomponer en tres `QWidget`/`QObject` extraídos — `NavigationController` (estado de índice + carga de working_image + output_folder), `WatermarkProcessor` (manual + auto YOLO + remove_watermark) y `TrainingDataCollector` (wrap delgado sobre `yolo/training_collector.py` con UI de conteo) — y dejar `SlideshowViewer` como **composer** que solo arma layout, instala event handlers globales (teclas, mouse) y conecta señales entre los tres componentes. Mantener el estado compartido (working_image, current_index) en `NavigationController` y exponerlo vía getters/señales.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Construcción de layout y window chrome | UI Composer (`SlideshowViewer`) | — | El composer arma el diálogo y orquesta hijos — única responsabilidad |
| Navegación de imágenes (índice, prev/next, load) | UI Component (`NavigationController`) | — | Estado de "qué imagen estamos viendo" + carga de working_image |
| Render de imagen + zoom + overlays | UI Component (`NavigationController` o split en `ImageCanvas`) | — | El render depende del estado de navegación + de los overlays activos |
| Modo crop (recorte de píxeles superiores/inferiores) | UI Component (`CropTool` o método de `NavigationController`) | — | Operación sobre working_image — comparte estado con navegación |
| Detección manual + preview + accept | UI Component (`WatermarkProcessor`) | — | Lógica de evento atómico de remoción manual |
| Detección automática YOLO + lista + accept | UI Component (`WatermarkProcessor`) | — | Conceptualmente la misma responsabilidad: aplicar `remove_watermark()` a coordenadas |
| Posiciones guardadas (`wm_positions.json`) + cuadros rojo/verde | UI Component (`PositionsOverlay` o método de `WatermarkProcessor`) | — | Es una tercera vía de remoción — comparte `remove_watermark()` con manual/auto |
| Save / remove de training samples | UI Component (`TrainingDataCollector`) | — | Wrap sobre `yolo/training_collector.py` — UI = conteo + reset |
| Reset de imagen procesada | Cross-component | — | Toca state de Navigation + Processor + Collector — debe ser una señal de "reset image N" |
| Persistencia de UI state (`wm_persistence`) | Service (existente, Phase 1) | — | Singleton — cada componente lo usa donde lo necesita |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PySide6 | 6.10.0 | Framework UI obligatorio | [VERIFIED: instalado en venv]; impuesto por CLAUDE.md como constraint |
| numpy | (instalado) | working_image / preview_image como arrays | [VERIFIED: usado en wm_remove.py]; ya en uso, no se agrega nada |
| opencv-python (cv2) | (instalado) | I/O de imágenes, template matching | [VERIFIED: usado en wm_remove.py]; ya en uso |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Ninguna nueva | — | — | La fase es 100% refactor estructural — **no se introducen dependencias nuevas** |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Composición de QWidget con signal/slot | MVC formal con clases Model/View/Controller separadas | [ASSUMED] Over-engineering para este scope. La guía oficial de Qt favorece "small composition tree of widgets over a giant window class" — el patrón composición/señales ya es el MVC de facto en Qt |
| Composición de QWidget | Inyección de dependencias (factory de servicios) | [ASSUMED] Over-engineering; CONTEXT.md de Phase 1 D-05 explícitamente rechazó DI ("singleton de módulo" como patrón). Consistencia con `wm_persistence` |
| `QObject` puro para `WatermarkProcessor` | `QWidget` para todos | [ASSUMED] `WatermarkProcessor` tiene UI (lista de detecciones, botones accept/revert) — debe ser `QWidget`. Si parte de su lógica no necesita UI, puede separarse en sub-objetos `QObject` (ej. `WatermarkProcessingEngine` sin widgets) — decisión de granularidad para el planner |
| Mover lógica a `WatermarkRemove/services/` | Mantener lógica en componentes UI | Para Phase 2 mantener componentes UI; Phase 3 (`ARCH-02`) extraerá lógica a services. El roadmap separa intencionalmente estas dos fases |

**Installation:**
```bash
# Ninguna instalación nueva — todas las dependencias ya están presentes
```

**Version verification:** `python -c "import PySide6; print(PySide6.__version__)"` → `6.10.0` [VERIFIED: ejecutado en este entorno 2026-05-26]. No hay cambio de versión de dependencias en esta fase.

## Package Legitimacy Audit

> No aplica — esta fase no instala paquetes externos. Es 100% refactor estructural en Python con dependencias preexistentes (PySide6, numpy, cv2, natsort), todas ya validadas en producción durante Phase 1.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (ninguno nuevo) | — | N/A |

## Architecture Patterns

### System Architecture Diagram

```
                       gui/controller.py
                              |
                              v
                  +-----------------------+
                  |  SlideshowViewer      |   ← composer / QDialog
                  |  (window chrome,      |
                  |   keyPressEvent,      |
                  |   mousePressEvent,    |
                  |   wheelEvent,         |
                  |   signal wiring)      |
                  +-----------------------+
                   /         |          \
                  v          v           v
       +--------------+ +-----------+ +-------------------+
       | NavigationCt | | Watermark | | TrainingDataColl. |
       | (QWidget):   | | Processor | |  (QWidget):       |
       | - image_list | | (QWidget):| | - count label     |
       | - cur_index  | | - manual  | | - calls save_     |
       | - working_im | |   preview | |   training_sample |
       | - output_dir | | - auto    | | - calls remove_   |
       | - load img   | |   YOLO    | |   training_sample |
       | - prev/next  | | - position|+-------------------+
       | - crop tool  | |   editor  |          ^
       | - zoom panel |+-----------+           |
       +--------------+      |                 |
            |  ^             v                 |
            |  |       wm_remove.py            |
            |  |   (align/find/remove          |
            |  |    /quick_align_preview)      |
            |  |                               |
            |  |       yolo/auto_detector.py   |
            |  |       (detect_watermarks,     |
            |  |        resolve_png_for_class) |
            |  |                               |
            |  +-------- signals --------------+
            |       (image_changed, accepted,
            |        reset_requested)
            v
        wm_persistence (services/, Phase 1)
        UtilJson(wm_positions.json) [legacy, retained]
```

**Data flow primary use case (manual flow):**
1. User opens dialog → `SlideshowViewer.__init__` builds layout, instantiates 3 components
2. `NavigationController._load_image_list()` carga lista, emite `image_changed(QPixmap, np.ndarray)` con working_image
3. Usuario activa "Modo selección manual" → `WatermarkProcessor._toggle_manual_mode(True)` muestra botones
4. Usuario clickea sobre la imagen → `SlideshowViewer.eventFilter` enruta al `WatermarkProcessor._remove_watermark_preview(pos)`
5. `WatermarkProcessor` llama `find_wm` + `quick_align_preview`, emite `preview_changed(np.ndarray)` → `NavigationController` re-renderiza
6. Usuario click Aceptar → `WatermarkProcessor._accept_preview()` aplica `remove_watermark()` con jpeg filter, llama `guardar()`, emite `image_processed(np.ndarray, x, y, watermark_array)` → `TrainingDataCollector` recibe y llama `save_training_sample()`

### Component Responsibilities

| Component | File | Class | Responsibility | Key state | Key signals |
|-----------|------|-------|----------------|-----------|-------------|
| Composer | `WatermarkRemove/ui/slideshow_viewer.py` | `SlideshowViewer(QDialog)` | Layout, window chrome, eventos globales (keyPress, wheelZoom), conexión de señales hijas, `review_completed` signal, métodos públicos `get_approved`/`get_output_folder`/`has_processed_images` | `user_approved`, `controls_panel_width` | `review_completed(bool)` [PRESERVAR — usado por `gui/controller.py`] |
| Navigation | `WatermarkRemove/ui/components/navigation_controller.py` | `NavigationController(QWidget)` | Lista de imágenes, índice actual, working_image, output_folder, crop, zoom, render | `image_files`, `current_index`, `working_image`, `output_folder`, `zoom_level`, `current_pixmap`, `processed_images`, `processed_positions` | `image_changed(index, path, np.ndarray)`, `requested_save_as_is(path)`, `output_folder_ready(Path)` |
| Processor | `WatermarkRemove/ui/components/watermark_processor.py` | `WatermarkProcessor(QWidget)` | Modo manual + auto YOLO + posiciones guardadas (cuadros rojo/verde); orquesta `find_wm` + `remove_watermark` + `align_watermark` | `watermark_folder`, `watermark_files`, `watermark_positions`, `detected_marks`, `is_preview_active`, `current_event_*` | `preview_changed(np.ndarray)`, `image_processed(file, working_image, x, y, wm_array, wm_path, wm_folder, base_image)`, `processing_blocked(bool)` |
| TrainingData | `WatermarkRemove/ui/components/training_data_collector.py` | `TrainingDataCollector(QWidget)` | UI de conteo (groupbox "Datos recopilados"), llama `save_training_sample` y `remove_training_sample` | `training_counts_label`, path a `training_data.json` | `counts_updated()` (interna; se llama desde slots `on_image_processed` / `on_image_reset`) |

### Pattern 1: QWidget child with signals

**What:** Cada componente extraído es `QWidget` que se construye con `parent=None` y se inserta en el layout del composer. La comunicación entre componentes va **siempre** por `Signal` (no por referencia directa al componente hermano). El composer hace el wiring.

**When to use:** Cuando el componente necesita UI propia (botones, labels, list widgets). Es el caso de los tres componentes de esta fase.

**Example:**
```python
# WatermarkRemove/ui/components/navigation_controller.py
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

class NavigationController(QWidget):
    # Señales públicas — el composer las conecta a slots de otros componentes
    image_changed = Signal(int, object, object)   # index, Path, np.ndarray
    output_folder_ready = Signal(object)           # Path

    def __init__(self, folder_path, parent=None):
        super().__init__(parent)
        self.image_files = []
        self.current_index = 0
        self.working_image = None
        # ... construir UI propia (botones prev/next, label de contador, image panel)
        self._setup_ui()
        self._load_image_list(folder_path)

    def next_image(self):
        # Lógica de avance + cambio de working_image
        self.current_index += 1
        self._load_working_image()
        self.image_changed.emit(self.current_index,
                                self.image_files[self.current_index],
                                self.working_image)
```

**Composer wiring:**
```python
# WatermarkRemove/ui/slideshow_viewer.py (después del refactor)
class SlideshowViewer(QDialog):
    review_completed = Signal(bool)  # PRESERVADA

    def __init__(self, folder_path, parent=None, watermark_tab=None):
        super().__init__(parent)
        self.watermark_tab = watermark_tab
        self.user_approved = False

        # Construir hijos
        self.navigation = NavigationController(folder_path)
        self.processor = WatermarkProcessor()
        self.collector = TrainingDataCollector()

        # Wiring: la navegación notifica un cambio de imagen → processor + collector reaccionan
        self.navigation.image_changed.connect(self.processor.on_image_changed)
        self.navigation.image_changed.connect(self.collector.on_image_changed)

        # Wiring: el processor termina una remoción → navegación refresca, collector guarda training data
        self.processor.image_processed.connect(self.navigation.on_image_processed)
        self.processor.image_processed.connect(self.collector.on_image_processed)
        self.processor.preview_changed.connect(self.navigation.on_preview_changed)

        # Wiring: reset emitido desde processor (botón ↺) → navegación + collector limpian
        self.processor.reset_requested.connect(self.navigation.reset_current_image)
        self.processor.reset_requested.connect(self.collector.reset_current_image)

        self._setup_layout()  # solo crea QHBoxLayout y agrega hijos
```

### Pattern 2: Signal vs direct call decision rule

**When to use Signal (one-way notification):**
- "Algo cambió en mí" (image_changed, preview_changed, image_processed)
- "Alguien debería reaccionar a X" (reset_requested)

**When to use direct slot call (request/response):**
- El composer (padre) llamando a un slot público del hijo (ej. `self.navigation.next_image()` desde `keyPressEvent`)
- Nunca: hijo → hijo directo (siempre vía señales mediadas por el composer)

### Recommended Project Structure
```
WatermarkRemove/
├── services/                          # Existente (Phase 1)
│   ├── __init__.py                    # exporta singleton wm_persistence
│   └── wm_persistence.py
├── ui/
│   ├── __init__.py                    # exporta WatermarkTab, SlideshowViewer (preservar)
│   ├── slideshow_viewer.py            # SlideshowViewer adelgazado (composer)
│   ├── watermark_tab.py
│   ├── image_viewer.py
│   ├── position_editor.py
│   └── components/                    # NUEVO directorio
│       ├── __init__.py                # exporta los 3 componentes
│       ├── navigation_controller.py   # NavigationController(QWidget)
│       ├── watermark_processor.py     # WatermarkProcessor(QWidget)
│       └── training_data_collector.py # TrainingDataCollector(QWidget)
├── yolo/
│   ├── auto_detector.py               # NO TOCAR
│   └── training_collector.py          # NO TOCAR
├── wm_remove.py                       # NO TOCAR
└── __init__.py
```

### Anti-Patterns to Avoid

- **God Class regression:** Crear un nuevo componente que vuelva a mezclar responsabilidades (ej. `WatermarkProcessor` que también gestione zoom + navegación). Cada componente debe responder "¿qué hace?" en una frase.
- **Tight coupling vía referencia hermana:** Hijo guardando `self.sibling = other_child`. Síntoma: cambiar el orden de construcción rompe el hijo. Solución: el composer conecta señales, los hijos no se conocen.
- **State duplicado:** Mantener `current_index` en dos componentes que se sincronizan. La fuente de verdad es `NavigationController` — los demás reciben el valor por señal cuando lo necesitan o lo piden por getter público (`navigation.current_image_path()`).
- **`self.parent()` para acceder al composer:** Frágil al refactor de árboles de widgets. Si el processor necesita el `watermark_tab` para logging, recibirlo como parámetro en `__init__` o conectar señal `log_requested(str)` al composer.
- **Mover código sin separar responsabilidades:** "Cortar y pegar" 700 líneas dentro de `WatermarkProcessor` sin refactor interno no cuenta como descomposición — los métodos siguen acoplados internamente. Verificar que cada método del componente extraído tiene una razón de existir dentro de **ese** componente.
- **Romper la API pública del composer:** `gui/controller.py` (línea 321) construye `SlideshowViewer(input_path, MainWindow, watermark_tab=watermark_tab)` y llama `viewer.exec()`, `viewer.get_approved()`, `viewer.has_processed_images()`, `viewer.get_output_folder()`. Estas cuatro entradas son contrato externo — no cambiar firmas.
- **Romper la API de `WatermarkTab`:** `get_settings()` / `set_settings()` son contrato con `SmartStitchGUI`. CLAUDE.md lo establece como constraint duro. No tocar en esta fase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Comunicación entre componentes UI | Callbacks manuales / observer pattern custom | `PySide6.QtCore.Signal` + `connect()` | Es el mecanismo nativo de Qt — thread-safe, soporta múltiples slots, debug tooling, ya en uso (`review_completed` signal en código actual) |
| Persistencia de UI state | Reimplementar JSON read/write | Singleton `wm_persistence` existente (Phase 1) | Ya resuelve `last_crop_pixels` y `last_watermark_folder`. Si un componente nuevo necesita persistir estado, agregar método al singleton |
| Carga/guardado de imágenes con caracteres Unicode | `cv2.imread`/`cv2.imwrite` directo | `load_images_cv2()` y `guardar()` desde `wm_remove.py` | Son los wrappers que ya manejan Unicode paths (usados por todo el código actual). Documentado en `wm_remove.py:34-43` |
| Detección de marca de agua | Reescribir template matching | `find_wm()` y `find_wm_gpu()` desde `wm_remove.py` | Ya optimizado para GPU/OpenCL con fallback CPU — no tocar |
| Inferencia YOLO | Reescribir loading ONNX | `detect_watermarks()` desde `yolo/auto_detector.py` | API pública preservada por constraint de CLAUDE.md; cache de modelo ya gestionado internamente |
| Cálculo de bbox YOLO + base64 + write JSON | Implementar serialización custom | `save_training_sample()` / `remove_training_sample()` desde `yolo/training_collector.py` | `training_data.json` es out-of-scope (REQUIREMENTS Out of Scope) — no tocar formato |
| Resolver PNG por clase + ancho de imagen | Re-implementar matching | `resolve_png_for_class()` desde `yolo/auto_detector.py` | Ya gestiona _candidate_folders fallback |

**Key insight:** Esta fase es **redistribución de responsabilidades**, no reescritura de lógica. Toda la lógica de dominio existente debe seguir siendo llamada — solo cambia **desde dónde** se llama. Si encontrás vos mismo escribiendo un algoritmo nuevo, parate: probablemente estás violando ARCH-01 vs ARCH-02 (Phase 3).

## Runtime State Inventory

> Phase 2 es un refactor estructural (extracción de componentes desde un archivo Python a tres archivos Python). No hay rename / no hay cambio de identifiers públicos / no hay cambio de paths persistidos. Sin embargo, verifico cada categoría explícitamente.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | Ninguno — los archivos `wm_settings.json`, `wm_positions.json`, `training_data.json` mantienen exactamente sus mismas keys y schemas. Ningún componente extraído cambia formato | None |
| Live service config | Ninguno — sin servicios externos (sin n8n, sin Datadog, sin Tailscale, sin Cloudflare). El módulo es desktop puro | None |
| OS-registered state | El `register_context_menu.py` registra menú contextual de Windows referenciando `SmartStitchGUI.py` — no toca `SlideshowViewer`. No hay tarea Scheduler / launchd / systemd ligada a este código | None |
| Secrets/env vars | Ninguno — el módulo no usa variables de entorno ni secretos | None |
| Build artifacts / installed packages | `WatermarkRemove/__pycache__/`, `WatermarkRemove/ui/__pycache__/`, `WatermarkRemove/services/__pycache__/`. **`.pyc` cache pierde su validez al renombrar/mover módulos** — Python lo regenera automáticamente al re-import, pero un desarrollador con `__pycache__` viejo viendo el repo después del refactor podría confundirse si revisa archivos `.pyc`. Acción recomendada: borrar `__pycache__` en `WatermarkRemove/` antes del verify final del phase | Borrar `__pycache__` recursivo: `find WatermarkRemove -name __pycache__ -exec rm -rf {} +` (un solo paso al final de la phase) |

**Public import surface (verified via Grep):**
- `gui/controller.py:16` → `from WatermarkRemove.ui import WatermarkTab, SlideshowViewer` — debe seguir funcionando
- `gui/controller.py:321` → `SlideshowViewer(input_path, MainWindow, watermark_tab=watermark_tab)` — firma del constructor debe seguir funcionando
- `WatermarkRemove/ui/__init__.py:9` → `from .slideshow_viewer import SlideshowViewer` — preservar

## Common Pitfalls

### Pitfall 1: Romper el flujo de eventos de mouse/teclado durante la extracción
**What goes wrong:** `SlideshowViewer` actualmente sobreescribe `mousePressEvent`, `wheelEvent`, `keyPressEvent` y un `eventFilter` sobre `image_label`. Si esos handlers se quedan en el composer pero el state que consultan (`watermark_rectangles`, `is_preview_active`, `mouse_position`) se mueve a un hijo, los handlers leen state stale.
**Why it happens:** Qt entrega eventos al widget que tiene focus o sobre el que ocurrieron — no a sus hijos a menos que se instale event filter o se haga override.
**How to avoid:**
- Decisión arquitectónica: el composer mantiene los handlers globales (`keyPressEvent` para Space/Backspace, `wheelEvent` para Ctrl+rueda), pero **delega** a slots públicos del hijo apropiado: `keyPressEvent(Key_Space)` → `self.navigation.next_image()` o `self.processor.accept_preview()` según `self.processor.is_preview_active()`.
- El `eventFilter` sobre `image_label` debe moverse al componente que **owns** `image_label`. Si `image_label` vive en `NavigationController`, el `eventFilter` debe instalarse desde `NavigationController` y delegar al `WatermarkProcessor` vía señal `image_clicked(QPoint)`.
**Warning signs:** Space deja de avanzar imágenes; click izquierdo no inicia preview manual; Ctrl+rueda no zoomea.

### Pitfall 2: Pérdida de la "atomicidad de eventos" durante la remoción manual
**What goes wrong:** El código actual implementa un "sistema de eventos atómicos" (líneas 97-104, 1419-1618): mientras `is_preview_active=True`, los botones prev/next/combo se deshabilitan, alpha/offset recalculan preview en vivo, y solo Accept o Revert salen del evento. Si esta máquina de estados se reparte mal entre dos componentes, los botones quedan habilitados durante el preview → el usuario puede navegar y corromper el state.
**Why it happens:** El state `is_preview_active`, `base_image_for_preview`, `current_event_position` y `current_event_watermark` debe vivir en **un solo lugar** (el `WatermarkProcessor`). El bloqueo UI de prev/next vive en `NavigationController`. El sync entre ambos es vía señal `processing_blocked(bool)`.
**How to avoid:**
- `WatermarkProcessor` emite `processing_blocked(True)` al iniciar el evento y `processing_blocked(False)` al aceptar/revertir.
- `NavigationController` conecta esa señal a un slot que hace `self.prev_btn.setEnabled(not blocked)` etc.
- El composer **también** conecta esa señal a un guard en su `keyPressEvent` (si is_blocked, Space va a `accept_preview` en vez de `next_image` — exactamente como hoy en líneas 1991-2000).
**Warning signs:** Durante un preview activo, presionar Space avanza la imagen sin aceptar → working_image stale; alpha_adjust no recalcula preview; Reset no cancela el preview activo.

### Pitfall 3: Confundir cambio estructural con cambio de comportamiento
**What goes wrong:** Durante el refactor uno "limpia" código que parece raro (ej. el `blockSignals` en `_load_watermark_folders` línea 585-613, o el guard `hasattr(self, 'alpha_adjust')` en línea 682) y rompe el orden de inicialización implícito.
**Why it happens:** Esos patrones existen por razones específicas (evitar disparar callbacks durante la construcción del combo, manejar el caso de construcción parcial del panel). El refactor estructural no los puede tirar.
**How to avoid:**
- Lectura previa **completa** del método antes de moverlo. Si hay un `blockSignals` o un `hasattr` defensive, copiarlo verbatim al componente destino.
- Antes de "mejorar" un guard defensivo, abrir un issue separado — fuera del scope de Phase 2 (ARCH-02 / ARCH-04 de Phase 3 puede tocar esto).
**Warning signs:** Tests manuales del usuario detectan que la lista de marcas se reinicia sola; el combo de carpeta dispara el callback al abrir el diálogo (cuando antes no lo hacía).

### Pitfall 4: Sub-process imports (training_collector) terminan en el archivo equivocado
**What goes wrong:** Las líneas 1540, 1662, 1854 del original hacen `from WatermarkRemove.yolo.training_collector import save_training_sample` **dentro del método** (no en imports del archivo). Si se mueven a un componente nuevo manteniendo el `import` local, todo bien. Si alguien "limpia" subiendo el import al top del nuevo componente y la fase no lo verifica, está ok — pero rompería si el componente se importa en un contexto sin numpy/cv2.
**Why it happens:** Los imports locales del original son intencionalmente lazy (carga el módulo recién cuando se necesita).
**How to avoid:**
- Documentar la decisión: en el nuevo `TrainingDataCollector`, hacer los imports al top del archivo (es seguro, el componente solo se construye dentro de `SlideshowViewer` que ya garantiza el entorno). Pero **documentarlo** en docstring para que un futuro lector entienda el cambio respecto al original.

### Pitfall 5: Tests de PySide6 ausentes — fix-by-eye-test only
**What goes wrong:** No hay tests automatizados de UI en el repo (ARCH-05 está deferred a v2). El refactor se valida 100% por inspección manual del usuario.
**Why it happens:** Decisión explícita en CONTEXT.md de Phase 1 / REQUIREMENTS.md (ARCH-05 deferred). Es legítimo, pero crea riesgo.
**How to avoid:**
- Definir un checklist UAT explícito en el plan: las 5 success criteria del roadmap (navegación Space/Backspace, manual flow, auto YOLO flow, training data save, comportamiento idéntico).
- Recomendación al planner: incluir una task de "before/after smoke test" donde el usuario opere sobre la misma carpeta con la versión anterior y la nueva. Phase 1 ya estableció el patrón con `01-HUMAN-UAT.md`.

### Pitfall 6: Métricas del grafo no se regeneran automáticamente
**What goes wrong:** El criterio "20 o menos edges" del roadmap se mide contra `graphify-out/graph.json`. Ese archivo fue generado en algún momento previo y no se regenera en CI.
**Why it happens:** `graphify` se corre manualmente. STATE.md cita "63 edges" y graph.json (verificado en este research) reporta **58 edges salientes** desde la clase `SlideshowViewer` + 12 imports a nivel de archivo. Hay drift entre el conteo del roadmap y el del grafo actual.
**How to avoid:**
- En el plan, incluir una task "Regenerar grafo y medir edges del nuevo SlideshowViewer". Verificar contra los **archivos nuevos** (3 componentes + composer), no contra el archivo viejo monolítico.
- Documentar en el plan la metodología de conteo: ¿edges a nivel archivo `slideshow_viewer.py` o edges a nivel clase `SlideshowViewer`? El roadmap dice "edges de dependencia directa" — recomendado: contar edges salientes a nivel **clase** del nuevo `SlideshowViewer` (composer), porque ese es el "God Class" a destronar.

## Code Examples

### Example 1: Componente extraído con señales (NavigationController esqueleto)
```python
# WatermarkRemove/ui/components/navigation_controller.py
# Source: PySide6 patrón composición (https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDialog.html)
from pathlib import Path
from typing import Optional
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from natsort import natsorted

from WatermarkRemove.wm_remove import load_images_cv2


class NavigationController(QWidget):
    """Gestor de navegación: lista de imágenes, índice actual, working_image, output_folder."""

    SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tga', '.psd', '.psb', '.jfif')

    # Señales públicas
    image_changed = Signal(int, object, object)     # (index, Path, np.ndarray)
    output_folder_ready = Signal(object)             # Path

    def __init__(self, folder_path: str, parent=None):
        super().__init__(parent)
        self.folder_path = Path(folder_path) if folder_path else None
        self.image_files: list = []
        self.current_index = 0
        self.working_image: Optional[np.ndarray] = None
        self.output_folder: Optional[Path] = None
        self.processed_images: set = set()
        self.processed_positions: dict = {}

        self._setup_ui()
        self._load_image_list()
        if self.image_files:
            self._refresh_current()

    def _setup_ui(self) -> None:
        """Construye SOLO la UI de navegación (botones prev/next, label de contador, image panel)."""
        ...

    def next_image(self) -> None:
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._refresh_current()

    def _refresh_current(self) -> None:
        current_file = self.image_files[self.current_index]
        self.working_image = load_images_cv2(current_file)
        self.image_changed.emit(self.current_index, current_file, self.working_image)

    # Slot público: el composer puede invocarlo desde keyPressEvent
    def request_next(self) -> None:
        self.next_image()
```

### Example 2: Composer wiring (SlideshowViewer adelgazado)
```python
# WatermarkRemove/ui/slideshow_viewer.py (después)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QHBoxLayout

from WatermarkRemove.ui.components import (
    NavigationController,
    WatermarkProcessor,
    TrainingDataCollector,
)


class SlideshowViewer(QDialog):
    """Composer: arma layout, conecta señales, expone API pública estable."""

    review_completed = Signal(bool)  # PRESERVADA — consumida por gui/controller.py

    def __init__(self, folder_path: str, parent=None, watermark_tab=None):
        super().__init__(parent)
        self.setWindowTitle("Revisión de Imágenes")
        self.setModal(True)
        self.user_approved = False
        self.watermark_tab = watermark_tab

        self.navigation = NavigationController(folder_path, parent=self)
        self.processor = WatermarkProcessor(parent=self)
        self.collector = TrainingDataCollector(parent=self)

        self._wire_signals()
        self._setup_layout()

    def _wire_signals(self) -> None:
        # Navegación → procesador (informa cambio de imagen)
        self.navigation.image_changed.connect(self.processor.on_image_changed)
        self.navigation.image_changed.connect(self.collector.on_image_changed)

        # Procesador → navegación (preview / final / bloqueo UI)
        self.processor.preview_changed.connect(self.navigation.on_preview_changed)
        self.processor.image_processed.connect(self.navigation.on_image_processed)
        self.processor.processing_blocked.connect(self.navigation.set_navigation_enabled)

        # Procesador → collector (training data + conteo)
        self.processor.image_processed.connect(self.collector.on_image_processed)
        self.processor.image_reset.connect(self.collector.on_image_reset)

    def _setup_layout(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)
        # Panel izquierdo = controles del processor + collector apilados
        # Panel derecho = navigation (que incluye image_label + scroll + zoom)
        ...

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        # Si hay preview activo en processor, Space/Backspace van a accept/revert
        if self.processor.is_preview_active():
            if key == Qt.Key.Key_Space:
                self.processor.accept_preview(); return
            if key == Qt.Key.Key_Backspace:
                self.processor.revert_preview(); return
        # Caso normal: navegación
        if key == Qt.Key.Key_Space:
            self.navigation.request_next(); return
        if key == Qt.Key.Key_Backspace:
            self.navigation.request_previous(); return
        super().keyPressEvent(event)

    # API pública estable (preservada del original)
    def get_approved(self) -> bool: return self.user_approved
    def get_output_folder(self): return self.navigation.output_folder
    def has_processed_images(self) -> bool: return len(self.navigation.processed_images) > 0
```

### Example 3: Llamada existente a `wm_remove.remove_watermark` desde componente
```python
# WatermarkRemove/ui/components/watermark_processor.py
from WatermarkRemove import align_watermark, remove_watermark
from WatermarkRemove.wm_remove import find_wm, quick_align_preview, guardar, load_images_cv2

def accept_preview(self):
    """Aplica remove_watermark con jpeg filter y guarda. Mismo flow que el original."""
    if not self._is_preview_active or self._preview_image is None:
        return
    best_x, best_y = self._current_event_position
    result = remove_watermark(
        self._base_image_for_preview,
        self._current_event_watermark,
        best_x + self.offset_x_adj.value(),
        best_y + self.offset_y_adj.value(),
        alpha_adjust=self.alpha_adjust.value(),
        apply_jpeg_filter=True,
    )
    guardar(self._current_file, result, self._output_folder)
    self.image_processed.emit(
        self._current_file, result, best_x, best_y,
        self._current_event_watermark, self._current_event_watermark_path,
        self._watermark_folder.name, self._base_image_for_preview,
    )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| QDialog monolítico con 50+ métodos | Composición de QWidgets con signals/slots | Patrón Qt desde siempre (Qt 4.x); reforzado en Qt 6 con Python type hints | Cleanup propiamente arquitectónico, mismo runtime cost |
| Comunicación callback-based entre widgets | `Signal`/`Slot` de Qt | Patrón nativo Qt | Más debuggeable, soporta múltiples receivers |

**Deprecated/outdated:** Ninguno — PySide6 6.10.0 es estable; el patrón composición + señales sigue siendo current.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | El target "20 edges" se refiere a edges del **composer adelgazado**, no del archivo `slideshow_viewer.py` completo (que importa los componentes hijos). | Pitfall 6 + Architectural Map | Si el roadmap se interpreta a nivel archivo, importar los 3 componentes nuevos suma 3 edges → el target sigue alcanzable. Plan debe documentar la métrica usada. |
| A2 | Tres componentes (navigation / processor / collector) es la granularidad correcta. Podría argumentarse 4 (split de "modo manual" vs "modo auto YOLO" en el processor) o 2 (collector dentro de processor). | Architectural Map + Recommended Project Structure | El roadmap del proyecto **ya decidió** la división en tres (02-01, 02-02, 02-03). Esta no es una asunción del researcher — es prescriptivo del roadmap. Confianza HIGH. |
| A3 | `WatermarkProcessor` debe owns el `eventFilter` lógicamente, pero `image_label` puede vivir en `NavigationController` (componente que renderiza la imagen). | Pitfall 1 | Si la ownership de `image_label` queda en navigation pero el event filter lo necesita el processor, hay dos opciones: (a) `image_label` se mueve al processor (y navigation emite QPixmap al processor para que renderice); (b) el filter se instala desde navigation y emite `image_clicked(QPoint)` al processor. Opción (b) es más limpia. El planner decide. |
| A4 | El "controls_panel_width = 280" hardcoded y los layout fijos pueden mantenerse durante Phase 2 — el rebalanceo de layout es Phase 4 (UI-01). | Don't Hand-Roll, Pitfall 3 | Cambiar layouts durante Phase 2 abre scope creep contra UI-01/UI-02/UI-03. Risk si se ignora: la fase se hace pesada. |
| A5 | El comportamiento de `_save_current_image_as_is` (auto-guardar imagen sin cambios al avanzar) es funcionalidad **deseada** y debe preservarse. | Pitfall 2 | Si fuera bug latente, el roadmap success criterion 5 ("comportamiento idéntico al anterior") lo confirma — preservarlo. |
| A6 | Borrar `__pycache__` recursivo al final de la fase es seguro. | Runtime State Inventory | Python regenera `__pycache__` en el próximo import. Es safe; documentar como step opcional. |

## Open Questions (RESOLVED)

1. **¿Ownership de `image_label` y zoom controls?**
   - What we know: `image_label`, `current_pixmap`, `zoom_level`, `_apply_zoom()`, `_set_zoom()`, overlays se comportan como una unidad visual cohesionada
   - What's unclear: ¿queda todo dentro de `NavigationController`, o se extrae `ImageCanvas` como cuarto componente?
   - Recommendation: empezar con todo en `NavigationController` (es lo que el roadmap describe como "carga de imagen"). Si después de extraer todo se ve que `NavigationController` quedó >800 líneas, abrir un sub-task de extracción extra. Decisión del planner.
   - **RESOLVED** — Plan 02-01 Task 2 assigns image_label to NavigationController (todo el bloque del panel derecho de imagen + scroll_area + zoom_overlay_label + manual_overlay_label vive en NavigationController._setup_ui). No se extrae un cuarto componente `ImageCanvas`.

2. **¿`_draw_watermark_overlays()` (cuadros rojo/verde de posiciones guardadas) va en `NavigationController` o `WatermarkProcessor`?**
   - What we know: Los cuadros se dibujan **sobre** el pixmap escalado (`_apply_zoom` los pinta encima); la lógica de **click** sobre ellos vive en `mousePressEvent` (línea 1913) que llama `_process_watermark_at_position`
   - What's unclear: El dibujo es renderizado (navigation) pero el comportamiento es procesamiento (processor). Está a horcajadas
   - Recommendation: las **posiciones** (`watermark_positions`, `watermark_rectangles`) y el handler de click viven en `WatermarkProcessor` (tercera vía de remoción junto a manual + auto). El render se hace pasando el pixmap a un método del processor: `pixmap = self.processor.decorate_with_position_overlays(pixmap, scale_factor)` desde `NavigationController._apply_zoom`. Esto mantiene render simple en navigation y el dominio (qué pintar y por qué) en el processor.
   - **RESOLVED** — Plan 02-02 Task 1 implements `decorate_pixmap(pixmap, scale_factor)` on WatermarkProcessor; Plan 02-02 Task 2 modifies NavigationController._apply_zoom to invoke the callback via `set_processor_decorator`. Las posiciones, rectangles y handler de click viven todas en WatermarkProcessor.

3. **¿Cómo medir y verificar el target "≤20 edges"?**
   - What we know: graphify-out/graph.json reporta 58 edges desde la clase actual + 12 imports a nivel archivo
   - What's unclear: la herramienta `graphify` no está integrada en CI; regenerar el grafo y comparar es un step manual
   - Recommendation: el planner debe agregar una task explícita "Regenerar graphify y verificar conteo del nuevo SlideshowViewer (clase)". Si el conteo es >20, abrir un task de extracción adicional. Usar comando: `gsd-sdk` o el script Node del graphify.
   - **RESOLVED** — Plan 02-03 Task 3 measures edge count via `02-EDGE-COUNT.md` (checkpoint UAT con instrucciones de regenerar grafo + comando node -e para contar OUT edges del nodo class SlideshowViewer + verdict PASS/FAIL contra el target ≤20).

4. **¿Cómo se aplica el patrón a `position_editor.py` que sigue el mismo problema?**
   - What we know: `position_editor.py` también es un widget grande con responsabilidades múltiples
   - What's unclear: si se decora con el mismo patrón
   - Recommendation: **fuera de scope** — REQUIREMENTS ARCH-06 está deferred a v2. Mencionar como deferred para futura phase.
   - **RESOLVED** — Out of scope per REQUIREMENTS ARCH-06 (deferred a v2). No se aborda en Phase 2.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | Refactor | ✓ | 3.x | — |
| PySide6 | UI framework | ✓ | 6.10.0 | — (obligatorio por CLAUDE.md) |
| numpy | working_image arrays | ✓ | (instalado) | — |
| opencv-python (cv2) | I/O imagen, template matching, GPU | ✓ | (instalado) | — |
| natsort | Ordenar archivos | ✓ | (instalado) | — |
| onnxruntime | YOLO ONNX runtime | ✓ | (instalado) | — (delegado a auto_detector.py, no se toca) |
| pytest | Tests automatizados | ✗ | — | Manual UAT (Phase 1 pattern, `01-HUMAN-UAT.md`) — ARCH-05 deferred |
| pytest-qt | Tests UI Qt | ✗ | — | Manual UAT |
| graphify (Node CLI) | Medir edges post-refactor | (verificar) | — | Si no disponible, contar imports/calls manualmente en `slideshow_viewer.py` adelgazado |

**Missing dependencies with no fallback:** Ninguna que bloquee la fase. La ausencia de pytest/pytest-qt es **decisión explícita** del proyecto (ARCH-05 deferred), no un bloqueo.

**Missing dependencies with fallback:** pytest/pytest-qt → manual UAT (mismo pattern que Phase 1). Esto fue aceptado en el contexto del proyecto y no debe re-discutirse en esta fase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Ninguno automatizado para UI (pytest **no instalado**); UAT manual via `XX-HUMAN-UAT.md` |
| Config file | none — see Wave 0 (no se introduce framework en esta fase, ARCH-05 deferred) |
| Quick run command | `python -m WatermarkRemove.ui.slideshow_viewer` (entrypoint de prueba existente en `__main__` línea 2022) |
| Full suite command | `python SmartStitchGUI.py` (smoke manual end-to-end con la app) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ARCH-01 | Visor navega con Space/Backspace sin lógica inline | manual UAT | — | ❌ documentar en `02-HUMAN-UAT.md` Wave 0 |
| ARCH-01 | YOLO + remove_watermark en componente separado | manual UAT + grep | `grep -n "remove_watermark\|detect_watermarks" WatermarkRemove/ui/slideshow_viewer.py` (esperado: 0 hits) | parcial (grep funciona; UAT en Wave 0) |
| ARCH-01 | Training data collection en componente separado | manual UAT + grep | `grep -n "save_training_sample\|remove_training_sample" WatermarkRemove/ui/slideshow_viewer.py` (esperado: 0 hits) | parcial |
| ARCH-01 | SlideshowViewer composer ≤20 edges | semi-automated | `node bin/graphify.js && node -e "...query SlideshowViewer node..."` | ❌ documentar metodología en plan |
| ARCH-01 | Comportamiento observable idéntico | manual UAT | — | ❌ checklist UAT in Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m py_compile WatermarkRemove/ui/slideshow_viewer.py WatermarkRemove/ui/components/*.py` (sintaxis + imports OK)
- **Per wave merge:** smoke manual abriendo `python -m WatermarkRemove.ui.slideshow_viewer` con la carpeta de test
- **Phase gate:** UAT completo siguiendo `02-HUMAN-UAT.md` antes de `/gsd-verify-work` (mismo patrón Phase 1)

### Wave 0 Gaps
- [ ] `.planning/phases/02-slideshowviewer-decomposition/02-HUMAN-UAT.md` — checklist UAT con los 5 success criteria del roadmap
- [ ] Comando/script para regenerar `graphify-out/graph.json` y verificar el conteo de edges del nuevo `SlideshowViewer`
- [ ] Comandos de grep documentados como "verify-script" en cada plan (uno por componente extraído)
- [ ] Decisión final del planner sobre A1 (qué edge se mide) y A3 (ownership de image_label) — pueden ir a discuss-phase

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Aplicación desktop local sin auth |
| V3 Session Management | no | Sin sesiones |
| V4 Access Control | no | Local single-user |
| V5 Input Validation | yes (parcial) | El path de carpeta entrante (`folder_path`) viene de `gui/controller.py` → `inputField.text()` — ya validado upstream (`if not Path(input_path).exists()`). No se introducen nuevos puntos de entrada en esta fase |
| V6 Cryptography | no | No se manejan secretos ni se hace criptografía |

### Known Threat Patterns for {Python desktop refactor}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal vía nombre de archivo de imagen | Tampering | Ya mitigado: `load_images_cv2` lee bytes vía `np.fromfile(str(path))`; `guardar()` escribe a `output_folder / image_path.name` — todas las paths son `pathlib.Path` y no concatenan strings de usuario. **Sin cambio en esta fase**. |
| Deserialización insegura de JSON | Tampering | `wm_persistence` + `UtilJson` ya implementan defensive `try/except` que retorna `{}` ante JSON corrupto (mitigado en Phase 1, T-01-02-02). Patrón heredado por cualquier componente nuevo que use `wm_persistence`. **Sin cambio en esta fase**. |
| Inyección de código por nombre de PNG (eval/exec) | Tampering | `png_name_to_class` usa regex puro, no eval. **No se toca en esta fase**. |
| Resource exhaustion (imágenes muy grandes en memoria) | DoS | `working_image` se mantiene en memoria por imagen — limitación conocida del módulo. Patrón pre-existente, **fuera de scope** de refactor estructural. |

**Conclusión security:** Phase 2 es **redistribución de código existente**, sin introducir nuevas superficies de ataque. Las mitigaciones existentes (path safety, JSON defensive parsing) son heredadas por los componentes nuevos al llamar las mismas funciones (`load_images_cv2`, `guardar`, `wm_persistence`). No se requieren nuevas controles de seguridad. ASVS Level 1 (configurado en `.planning/config.json`) cumplido por preservación de mitigaciones existentes.

## Project Constraints (from CLAUDE.md)

> Directivas extraídas de CLAUDE.md (proyecto) y reglas globales — el planner DEBE verificar cumplimiento.

1. **Tech Stack PySide6 obligatorio** — no migrar a otro framework UI. Componentes extraídos = `QWidget`/`QObject` de PySide6.
2. **Preservar API pública de `wm_remove.py` y `auto_detector.py`** — los componentes nuevos llaman estas funciones sin cambiar firmas. Cero edits en `wm_remove.py` o `yolo/auto_detector.py`.
3. **Estilo visual consistente con `gui/stylesheet.py`** — esta fase es estructural, no cambia QSS. Phase 4 aplicará rebalanceo visual (UI-01/02/03).
4. **`WatermarkTab.get_settings()` / `apply_settings()`** — deben seguir funcionando. Esta fase **no toca** `watermark_tab.py` (excepto si surge necesidad por wiring de logging — documentar en plan).
5. **`SlideshowViewer.review_completed` signal + constructor `(folder_path, parent, watermark_tab=)` + métodos `get_approved/get_output_folder/has_processed_images`** — contrato con `gui/controller.py:321`. Preservar firmas verbatim.
6. **GSD Workflow Enforcement (global CLAUDE.md)** — todo trabajo via comando GSD; no se hacen edits directos al repo. Esta fase corre dentro de `/gsd-execute-phase` + `/gsd-plan-phase`.

## Sources

### Primary (HIGH confidence)
- `WatermarkRemove/ui/slideshow_viewer.py` (2041 lines) — lectura completa del God Class actual; mapeo de los 58 métodos
- `WatermarkRemove/ui/watermark_tab.py` — verificado: NO importa SlideshowViewer; el wiring está en `gui/controller.py`
- `WatermarkRemove/wm_remove.py` — verificadas firmas públicas de `load_images_cv2`, `align_watermark`, `find_wm`, `remove_watermark`, `quick_align_preview`, `guardar`
- `WatermarkRemove/yolo/auto_detector.py` — verificadas firmas públicas `detect_watermarks(image_bgr)`, `resolve_png_for_class(folder, class, width)`
- `WatermarkRemove/yolo/training_collector.py` — verificadas firmas `save_training_sample(...)`, `remove_training_sample(current_dir, current_file, log)`
- `WatermarkRemove/services/__init__.py` + `wm_persistence.py` — patrón establecido en Phase 1 (singleton)
- `gui/controller.py:321` — única call site externa de `SlideshowViewer`; firma del constructor confirmada
- `WatermarkRemove/ui/__init__.py` — export surface confirmado
- `.planning/REQUIREMENTS.md` §ARCH-01, Out of Scope — scope verificado
- `.planning/ROADMAP.md` §Phase 2 — éxito criteria y plans 02-01/02-02/02-03 verbatim
- `.planning/STATE.md` — bloqueo/concern de 63 edges + betweenness 0.277
- `.planning/phases/01-json-persistence/01-CONTEXT.md` + `01-02-SUMMARY.md` — pattern services/ y singleton establecidos
- `graphify-out/graph.json` (built_at_commit: snapshot) — verificado: `ui_slideshow_viewer_slideshowviewer` tiene 58 OUT edges + 5 IN edges; `watermarkremove_ui_slideshow_viewer_py` tiene 12 unique import targets
- `CLAUDE.md` — constraints verbatim
- `.planning/config.json` — `workflow.nyquist_validation: true`, `workflow.security_enforcement: true`, `workflow.security_asvs_level: 1`

### Secondary (MEDIUM confidence)
- PySide6 official docs (https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QDialog.html) — confirmación del patrón composición + signal/slot
- pythonguis.com Signal/Slot tutorial — confirmación de patrón nativo Qt
- Qt Forum thread "simplest mvc pattern in pyside6" — confirmación de la guidance "small composition tree of widgets over a giant window class"

### Tertiary (LOW confidence)
- Ninguno — todos los hallazgos críticos se verificaron en el código fuente o documentación oficial

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verificado en código + venv local
- Architecture: HIGH — patrón composición + señales es el idiom oficial de Qt, alineado con guidance de docs y consistente con el patrón services/ ya establecido en Phase 1
- Pitfalls: HIGH — extraídos por lectura directa del código (ej. `blockSignals`, `hasattr` guards, sistema de eventos atómicos)
- Métricas de edges: MEDIUM — el conteo del grafo (58 OUT del class) difiere del roadmap (63); el plan debe definir metodología clara
- Security: HIGH — fase es estructural, mitigaciones heredadas

**Research date:** 2026-05-26
**Valid until:** 2026-06-25 (30 días — stack estable, sin dependencias fast-moving)

---

*Phase: 02-slideshowviewer-decomposition*
*Research completed: 2026-05-26*
