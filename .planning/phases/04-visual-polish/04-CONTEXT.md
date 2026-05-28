# Phase 4: Visual Polish - Context

**Gathered:** 2026-05-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 entrega una interfaz de WatermarkRemove visualmente coherente con SmartStitch: el visor de imagen domina el espacio disponible (QSplitter 65/35), los controles están organizados en un panel lateral con un sistema de 3 modos (Selección / Recorte / Automático) + grupo de Navegación persistente + grupo de Training Data persistente, y todos los estilos inline hardcodeados son reemplazados por el dark theme de `gui/stylesheet.py` con acento `#26EE9F`.

**Fuera del scope**: watermark_tab.py, image_viewer.py, position_editor.py (esos widgets no son parte del visor slideshow y no se tocan en esta fase). No se agregan nuevas funcionalidades — solo layout, agrupación y estilos.

</domain>

<decisions>
## Implementation Decisions

### Layout — UI-01 (Plan 04-01)

- **D-01:** Usar `QSplitter` horizontal con proporción inicial **65% visor / 35% panel de controles**. El usuario puede redimensionar arrastrando el divisor.
- **D-02:** **Persistir la posición del splitter** entre sesiones usando `WmPersistenceService` (servicio creado en Phase 1, ya en `WatermarkRemove/services/`). Guardar/restaurar `splitter.sizes()` en la clave `splitter_sizes` de `wm_settings.json`.
- **D-03:** **Sin QScrollArea** en el panel de controles. Los controles se comprimen si la ventana se achica. La app ya tiene un tamaño mínimo razonable.

### Organización de controles — UI-02 (Plan 04-02)

- **D-04:** El panel de controles tiene esta estructura vertical fija:
  1. **Grupo Navegación** (QGroupBox, siempre visible, arriba) — prev/next, contador, filename
  2. **Selector de modo** — QButtonGroup horizontal estilo radio: `[Selección]  [Recorte]  [Automático]`
  3. **QStackedWidget** — muestra los controles del modo activo (una página por modo)
  4. **Grupo Training Data** (QGroupBox, siempre visible, abajo) — save/remove sample, contador

- **D-05:** El selector de modo usa **QButtonGroup con QPushButton checkable** (apariencia de tabs, no radio buttons nativos). Solo un modo activo a la vez.

- **D-06:** Cambiar modo = `stacked_widget.setCurrentIndex(N)`. Cada página del stack contiene un QGroupBox con los controles de ese modo.

- **D-07:** **Modo Selección** tiene un checkbox "Avanzado" dentro de su grupo en el QStackedWidget. Marcar el checkbox expande/muestra un subgrupo con los controles avanzados de selección manual.

- **D-08:** **Modo Automático (Auto-detección)**: el QGroupBox del modo Automático se oculta (`setVisible(False)`) si el modelo YOLO no está disponible al iniciar. El botón `[Automático]` del selector también se deshabilita o se oculta en ese caso.

- **D-09:** Títulos de los QGroupBox en **español**: "Navegación", "Training Data", "Selección", "Recorte", "Automático".

- **D-10:** Los grupos son **siempre visibles** (sin colapso). Sin subclases de QGroupBox.

- **D-11:** Tamaño de botones **estándar Qt** — sin padding explícito forzado. El tema qdarktheme define el sizing. Consistente con el resto de SmartStitch.

### QSS y colores — UI-03 (Plan 04-03)

- **D-12:** Aplicar estilos vía **`gui/stylesheet.py`** (QSS global), no mediante archivos QSS separados ni setStyleSheet() en los componentes.

- **D-13:** **Eliminar todos los `setStyleSheet()` inline** en los componentes del SlideshowViewer (`navigation_controller.py`, `watermark_processor.py`, `training_data_collector.py`). Si un widget necesita estilo específico, usar `setObjectName()` + regla en `gui/stylesheet.py`.

- **D-14:** El `SlideshowViewer` **hereda el tema del QApplication padre** — no llama a `load_stylesheet()` propio. SmartStitchGUI.py ya aplica el tema al inicio.

- **D-15:** **Scope de UI-03**: `WatermarkRemove/ui/slideshow_viewer.py` + `WatermarkRemove/ui/components/` (navigation_controller, watermark_processor, training_data_collector). No incluye watermark_tab.py, image_viewer.py ni position_editor.py.

### Claude's Discretion

- **Colores semánticos**: Claude decidió mantener **rojo** (`#f44336` o similar muted) para el botón Revert (acción destructiva/irreversible) y **verde** (`#4CAF50` o similar) para Accept/Confirm. El resto de botones usan el acento teal `#26EE9F` o los colores neutros del dark theme. Justificación: en un flujo rápido de revisión de imágenes, las señales visuales de color para acciones destructivas reducen errores.
- **Label Training Data counter**: hereda el tema sin estilo especial (el color teal u otro acento podría usarse si el planner lo considera apropiado).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Tema visual SmartStitch
- `gui/stylesheet.py` — Define `DARK_STYLE_SHEET` (QSS custom con acento `#26EE9F`) y `load_stylesheet('dark')` via qdarktheme. Todo el styling de Phase 4 debe ser coherente con este archivo.

### Arquitectura UI actual (pre-Phase 4)
- `WatermarkRemove/ui/slideshow_viewer.py` — Widget principal a rebalancear. Layout actual: QHBoxLayout fijo sin QSplitter.
- `WatermarkRemove/ui/components/navigation_controller.py` — Controles de navegación + visor de imagen con estilos inline hardcodeados a limpiar.
- `WatermarkRemove/ui/components/watermark_processor.py` — Controles de Selección/Recorte/Automático con colores hardcodeados (#9C27B0, #FF9800, #4CAF50, #f44336).
- `WatermarkRemove/ui/components/training_data_collector.py` — Grupo Training Data con estilos inline a limpiar.

### Servicio de persistencia (para splitter)
- `WatermarkRemove/services/__init__.py` — Barrel de servicios. Usar `wm_persistence` singleton para persistir splitter_sizes.
- `WatermarkRemove/services/wm_persistence.py` — WmPersistenceService. Patrón: `get(key, default)` / `set(key, value)`.

### Requisitos
- `.planning/REQUIREMENTS.md` — UI-01, UI-02, UI-03 son los requisitos de esta fase.
- `.planning/ROADMAP.md` — Phase 4 success criteria (65% visor, 4 secciones, indistinguible del tema SmartStitch).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WmPersistenceService` (`WatermarkRemove/services/wm_persistence.py`) — Para persistir `splitter_sizes`. Patrón: `wm_persistence.set('splitter_sizes', splitter.sizes())` y `wm_persistence.get('splitter_sizes', [650, 350])`.
- `gui/stylesheet.py` `DARK_STYLE_SHEET` — QSS existente que define el dark theme. Extender con reglas específicas de WatermarkRemove (QGroupBox border-color, QButtonGroup checked state, etc.).

### Established Patterns
- **Sin QSplitter actualmente**: `slideshow_viewer.py:129` usa `main_layout = QHBoxLayout(self)` con proporciones implícitas. Reemplazar por `QSplitter(Qt.Horizontal)` + `addWidget()` + `setSizes([650, 350])`.
- **Herencia de tema**: El QApplication de SmartStitchGUI ya aplica `load_stylesheet('dark') + DARK_STYLE_SHEET`. Los QDialog hijos heredan automáticamente.
- **setStyleSheet() inline a eliminar**: `navigation_controller.py:144-196`, `watermark_processor.py:214-370` — todos estos deben ir a `gui/stylesheet.py` vía objectName.

### Integration Points
- `gui/controller.py:317` usa `watermark_tab.run_quita_marcas.isChecked()` para abrir SlideshowViewer — ese contrato NO cambia.
- `WatermarkTab.__init__` instancia los componentes. Phase 4 no toca `watermark_tab.py` — solo el interior del SlideshowViewer y sus componentes.
- El `QSplitter` persiste sus sizes con `wm_persistence` en `closeEvent` o `splitterMoved` signal.

</code_context>

<specifics>
## Specific Ideas

- El selector de modo `[Selección][Recorte][Automático]` son QPushButton con `setCheckable(True)` agrupados en `QButtonGroup(exclusive=True)`. El botón activo se estila con `:checked` en el QSS (acento teal, fondo más visible).
- Estructura esperada del QStackedWidget: página 0 = controles Selección (con checkbox Avanzado), página 1 = controles Recorte, página 2 = controles Automático.
- Si YOLO no está disponible: el botón `[Automático]` del QButtonGroup se deshabilita (`setEnabled(False)`) y la página 2 del stack se puede ocultar o mostrar un label "Modelo no disponible".

</specifics>

<deferred>
## Deferred Ideas

- **Tooltips y ayuda contextual** en controles menos obvios — UI-05 (v2 requirement, deferred por diseño del ROADMAP).
- **Feedback visual en tiempo real** (spinner de carga de modelo, indicador "guardado", conteo de training samples en tiempo real) — UI-04 (v2 requirement, deferred).
- **Tests unitarios para componentes de UI** — ARCH-05 (v2 requirement, deferred).

</deferred>

---

*Phase: 4-visual-polish*
*Context gathered: 2026-05-28*
