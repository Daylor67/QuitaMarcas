# SmartStitch — WatermarkRemove Refactor

## What This Is

SmartStitch es una herramienta de escritorio para unir imágenes de manhwa/manga verticalmente.
El módulo `WatermarkRemove/` permite eliminar marcas de agua de imágenes usando detección manual o automática (YOLO/ONNX), y recopilar datos de entrenamiento para mejorar el modelo.
Esta refactorización ataca la deuda técnica acumulada en la UI del módulo: un God Class (`SlideshowViewer`) que mezcla navegación, inferencia, estado y diseño en un solo archivo, y una interfaz visual desorganizada.

## Core Value

El usuario puede revisar, remover marcas de agua y navegar imágenes sin que la UI se interponga — flujo fluido, controles claros, sin sorpresas.

## Requirements

### Validated

- ✓ Remoción de marcas de agua via `remove_watermark()` — existente
- ✓ Detección automática YOLO/ONNX via `auto_detector.py` — existente
- ✓ Recopilación de training data (save/remove sample) — existente
- ✓ Editor de posiciones manual (`PositionEditor`) — existente
- ✓ Preview en vivo antes de guardar — existente
- ✓ Visor slideshow con navegación Space/Backspace — existente

### Active

- [ ] **ARCH-01**: Descomponer `SlideshowViewer` en componentes de responsabilidad única
- [ ] **ARCH-02**: Separar lógica de negocio de los widgets UI en `WatermarkRemove/`
- [x] **ARCH-03**: Unificar `SettingsHandler` y `UtilJson` (persistencia JSON duplicada) — Validated in Phase 1
- [ ] **UI-01**: Rebalancear proporción visor de imagen vs panel de controles
- [ ] **UI-02**: Reorganizar controles con jerarquía visual clara
- [ ] **UI-03**: Aplicar estilo visual consistente con SmartStitch GUI

### Out of Scope

- Rediseño del flujo completo de navegación — solo mejorar el existente
- Cambios al algoritmo `remove_watermark()` — funciona bien, no tocar
- Cambios a la lógica YOLO/ONNX en `auto_detector.py` — solo la UI encima cambia
- Cambios al formato de archivos `wm_positions.json` / `training_data.json`
- Refactorizar `SmartStitchGUI.py` o el pipeline principal — fuera del scope

## Context

- **Knowledge graph disponible**: `graphify-out/graph.json` + `graphify-out/graph.html` — mapa completo de dependencias del proyecto generado con graphify
- **God Class identificado**: `SlideshowViewer` tiene 63 edges y conecta 10 comunidades — el nodo de mayor betweenness centrality (0.277) del proyecto
- **Duplicación detectada**: `SettingsHandler` ≈ `UtilJson` (ambos persisten JSON tipado sin coordinarse)
- **Stack UI**: PySide6, estilos QSS en `gui/stylesheet.py`, acento visual `#26EE9F` (mint/verde)
- **Branching**: rama actual `refactorizacion-WatermrkRemove` — trabajo en curso
- **Tests**: `Test/test_yolo_detection.py` existe para YOLO; no hay tests de UI

## Constraints

- **Tech Stack**: PySide6 obligatorio — no migrar a otro framework
- **Compatibilidad**: Preservar API pública de `wm_remove.py` y `auto_detector.py` — otros módulos los usan
- **Estilo**: Visual consistente con `gui/stylesheet.py` existente — mismo dark theme + acento teal
- **Sin breaking changes**: `WatermarkTab.get_settings()` / `apply_settings()` deben seguir funcionando (usados por SmartStitchGUI)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Arquitectura primero, diseño después | Limpiar responsabilidades antes de cambiar el look evita rediseñar dos veces | — Pending |
| Preservar toda la lógica de negocio (YOLO, remove_watermark, training) | Funciona correctamente — el problema es la capa UI encima | — Pending |
| Estilar consistente con SmartStitch GUI | El usuario quiere WatermarkRemove integrado visualmente, no como módulo separado | — Pending |
| Conocimiento del grafo como referencia de arquitectura | graphify-out/ documenta dependencias reales — úsarlo en cada fase | — Pending |

## Evolution

Este documento evoluciona en transiciones de fase y milestones.

**Después de cada fase** (`/gsd-transition`):
1. ¿Requisitos invalidados? → Mover a Out of Scope con razón
2. ¿Requisitos validados? → Mover a Validated con referencia de fase
3. ¿Nuevos requisitos emergieron? → Agregar a Active
4. ¿Decisiones a registrar? → Agregar a Key Decisions

**Después de cada milestone** (`/gsd-complete-milestone`):
1. Revisión completa de todas las secciones
2. Check de Core Value — ¿sigue siendo la prioridad correcta?
3. Auditar Out of Scope — ¿razones siguen válidas?

---
*Last updated: 2026-05-26 after Phase 1 (JSON Persistence) completion*
