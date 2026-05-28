# Roadmap: SmartStitch — WatermarkRemove Refactor

## Overview

Esta refactorización transforma el módulo `WatermarkRemove/` de un monolito centrado en `SlideshowViewer` (God Class de 63 edges) hacia una arquitectura limpia con responsabilidades separadas, terminando con una interfaz visual coherente con el resto de SmartStitch. Las fases siguen el principio arquitectura-primero: se limpia la estructura interna antes de tocar la presentación visual.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: JSON Persistence** - Unificar SettingsHandler y UtilJson en un único servicio de persistencia (completed 2026-05-26)
- [ ] **Phase 2: SlideshowViewer Decomposition** - Descomponer el God Class en componentes de responsabilidad única
- [ ] **Phase 3: Logic/Widget Separation** - Separar lógica de negocio de widgets y convertir WatermarkTab en coordinador puro
- [ ] **Phase 4: Visual Polish** - Rebalancear layout, reorganizar controles y aplicar estilo consistente con SmartStitch

## Phase Details

### Phase 1: JSON Persistence
**Goal**: El módulo tiene un único servicio de persistencia JSON — no hay código duplicado entre SettingsHandler y UtilJson
**Depends on**: Nothing (first phase)
**Requirements**: ARCH-03
**Success Criteria** (what must be TRUE):
  1. Toda llamada de lectura/escritura JSON en `WatermarkRemove/` usa el servicio unificado — no hay llamadas directas a UtilJson ni a SettingsHandler por separado
  2. Los archivos `wm_positions.json` y `training_data.json` se cargan y guardan correctamente con el servicio unificado
  3. El módulo principal `SmartStitchGUI.py` sigue funcionando sin cambios — la API pública de persistencia no se rompió
  4. No hay regresión en la carga/guardado de settings cuando se abre y cierra la aplicación
**Plans**: 2 plans

Plans:

**Wave 1**
- [x] 01-01-PLAN.md — Auditar UtilJson call sites y producir contrato del servicio WmPersistenceService

**Wave 2** *(blocked on Wave 1 completion)*
- [x] 01-02-PLAN.md — Crear WmPersistenceService en services/ y migrar 4 call sites en slideshow_viewer.py

**Cross-cutting constraints:**
- D-03: wm_positions.json no se toca — solo migran last_crop_pixels y last_watermark_folder

### Phase 2: SlideshowViewer Decomposition
**Goal**: SlideshowViewer ya no es un God Class — sus responsabilidades están distribuidas en componentes con propósito único
**Depends on**: Phase 1
**Requirements**: ARCH-01
**Success Criteria** (what must be TRUE):
  1. El visor slideshow navega imágenes con Space/Backspace sin que el widget tenga lógica de procesamiento inline
  2. La detección YOLO/auto y la ejecución de `remove_watermark()` viven en componentes separados del widget de navegación
  3. La recopilación de training data (save/remove sample) opera desde su propio componente sin acoplar el visor
  4. SlideshowViewer tiene 20 o menos edges de dependencia directa (reducción desde 63 actuales)
  5. El comportamiento observable del visor es idéntico al anterior — el usuario no nota ningún cambio funcional
**Plans**: 3 plans

Plans:

**Wave 1**
- [x] 02-01-PLAN.md — Crear paquete components/ con stubs + extraer NavigationController (navegación, render, zoom, output_folder)

**Wave 2** *(blocked on Wave 1)*
- [x] 02-02-PLAN.md — Extraer WatermarkProcessor (manual + auto YOLO + posiciones guardadas + crop + máquina de eventos atómicos) y restaurar overlays via signal/slot decorate_pixmap

**Wave 3** *(blocked on Wave 2)*
- [x] 02-03-PLAN.md — Extraer TrainingDataCollector + reducir SlideshowViewer a composer puro + verificar edge count ≤20 (UAT manual + 02-EDGE-COUNT.md)

### Phase 3: Logic/Widget Separation
**Goal**: Los widgets de WatermarkRemove solo coordinan y presentan — ninguna lógica de dominio vive dentro de un widget, y WatermarkTab es un coordinador puro
**Depends on**: Phase 2
**Requirements**: ARCH-02, ARCH-04
**Success Criteria** (what must be TRUE):
  1. `WatermarkTab.get_settings()` y `apply_settings()` siguen funcionando — SmartStitchGUI no requiere cambios
  2. Ningún widget en `WatermarkRemove/ui/` contiene lógica de negocio inline — solo llamadas a servicios extraídos
  3. WatermarkTab no orquesta lógica directamente: conecta señales de UI con servicios, sin condicionales de dominio propios
  4. El flujo completo (abrir imágenes → detectar/remover watermark → guardar) sigue funcionando sin regresión
**Plans**: 3 plans

Plans:

**Wave 1**
- [x] 03-01-PLAN.md — Crear servicios de dominio (PositionEditorService, folder_scan, wm_positions persistence, ContextMenuService) + barrel + artefactos Wave 0 (UAT + grep pattern)

**Wave 2** *(blocked on Wave 1)*
- [x] 03-02-PLAN.md — Refactorizar position_editor.py e image_viewer.py para delegar dominio a servicios (ARCH-02)
- [ ] 03-03-PLAN.md — Refactorizar watermark_tab.py como coordinador puro (winreg → ContextMenuService, alias apply_settings) + UAT manual final (ARCH-04)

### Phase 4: Visual Polish
**Goal**: La interfaz de WatermarkRemove es visualmente coherente con SmartStitch y el visor de imagen domina el espacio disponible
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03
**Success Criteria** (what must be TRUE):
  1. El visor de imagen ocupa al menos el 65% del ancho de la ventana — los controles no compiten por espacio visual
  2. Los controles están agrupados en cuatro secciones con separadores visuales: Navegación / Remoción / Auto-detección / Training
  3. El tema dark, el acento `#26EE9F` y la tipografía son visualmente indistinguibles entre WatermarkRemove y el resto de SmartStitch
  4. Un usuario nuevo puede identificar correctamente qué botón usa sin leer documentación — la jerarquía visual es obvia
**Plans**: TBD

Plans:
- [ ] 04-01: Rebalancear layout (splitter/proporción visor vs panel de controles)
- [ ] 04-02: Reorganizar controles en grupos funcionales con separadores visuales
- [ ] 04-03: Aplicar QSS de gui/stylesheet.py — dark theme + acento teal consistente

**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. JSON Persistence | 2/2 | Complete    | 2026-05-26 |
| 2. SlideshowViewer Decomposition | 3/3 | Complete    | 2026-05-27 |
| 3. Logic/Widget Separation | 2/3 | In Progress|  |
| 4. Visual Polish | 0/3 | Not started | - |
