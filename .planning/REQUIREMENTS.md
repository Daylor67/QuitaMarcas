# Requirements: SmartStitch — WatermarkRemove Refactor

**Defined:** 2026-05-26
**Core Value:** El usuario puede revisar, remover marcas de agua y navegar imágenes sin que la UI se interponga — flujo fluido, controles claros, sin sorpresas.

## v1 Requirements

### Architecture

- [ ] **ARCH-01**: El módulo `WatermarkRemove/` no tiene un God Class — `SlideshowViewer` se descompone en componentes con responsabilidad única (navegación, procesamiento de watermarks, colección de training data)
- [ ] **ARCH-02**: La lógica de negocio de `WatermarkRemove` está separada de los widgets UI — los widgets solo coordinan y presentan, no ejecutan lógica de dominio
- [ ] **ARCH-03**: `SettingsHandler` y `UtilJson` están unificados en un único servicio de persistencia JSON — no hay duplicación de responsabilidad
- [ ] **ARCH-04**: `WatermarkTab` actúa como coordinador puro — no contiene lógica de negocio inline, solo conecta UI con servicios

### UI/UX

- [ ] **UI-01**: La proporción entre el visor de imagen y el panel de controles está balanceada — el visor ocupa el espacio dominante y los controles no compiten por espacio
- [ ] **UI-02**: Los controles tienen jerarquía visual clara — agrupados por función (navegación / remoción / auto-detección / training), con separación visual entre grupos
- [ ] **UI-03**: El estilo visual de `WatermarkRemove/` es consistente con `gui/stylesheet.py` — mismo dark theme, acento `#26EE9F`, tipografía y espaciado coherente

## v2 Requirements

### UI/UX (deferred)

- **UI-04**: Feedback visual de estado en tiempo real (spinner de carga de modelo, indicador "guardado", conteo de training samples)
- **UI-05**: Tooltips y ayuda contextual en los controles menos obvios

### Architecture (deferred)

- **ARCH-05**: Tests unitarios para los servicios extraídos de SlideshowViewer
- **ARCH-06**: Refactorizar `PositionEditor` con el mismo patrón de separación UI/lógica

## Out of Scope

| Feature | Reason |
|---------|--------|
| Cambios a `remove_watermark()` en `wm_remove.py` | Funciona correctamente — el problema es la capa UI encima |
| Cambios a `auto_detector.py` (lógica YOLO/ONNX) | Solo la UI que lo llama cambia |
| Cambios al formato `wm_positions.json` / `training_data.json` | Romperían compatibilidad con datos existentes |
| Refactorizar `SmartStitchGUI.py` o pipeline principal | Fuera del scope de esta refactorización |
| Rediseño del flujo completo de navegación | Mejorar el existente, no repensar desde cero |
| Migración a otro framework UI (Qt Quick/QML, tkinter, etc.) | PySide6 es obligatorio |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ARCH-03 | Phase 1 | Pending |
| ARCH-01 | Phase 2 | Pending |
| ARCH-02 | Phase 2 | Pending |
| ARCH-04 | Phase 3 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |

**Coverage:**
- v1 requirements: 7 total
- Mapped to phases: 7
- Unmapped: 0 ✓

---
*Requirements defined: 2026-05-26*
*Last updated: 2026-05-26 after initial definition*
