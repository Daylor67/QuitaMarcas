<!-- GSD:project-start source:PROJECT.md -->
## Project

**SmartStitch — WatermarkRemove Refactor**

SmartStitch es una herramienta de escritorio para unir imágenes de manhwa/manga verticalmente.
El módulo `WatermarkRemove/` permite eliminar marcas de agua de imágenes usando detección manual o automática (YOLO/ONNX), y recopilar datos de entrenamiento para mejorar el modelo.
Esta refactorización ataca la deuda técnica acumulada en la UI del módulo: un God Class (`SlideshowViewer`) que mezcla navegación, inferencia, estado y diseño en un solo archivo, y una interfaz visual desorganizada.

**Core Value:** El usuario puede revisar, remover marcas de agua y navegar imágenes sin que la UI se interponga — flujo fluido, controles claros, sin sorpresas.

### Constraints

- **Tech Stack**: PySide6 obligatorio — no migrar a otro framework
- **Compatibilidad**: Preservar API pública de `wm_remove.py` y `auto_detector.py` — otros módulos los usan
- **Estilo**: Visual consistente con `gui/stylesheet.py` existente — mismo dark theme + acento teal
- **Sin breaking changes**: `WatermarkTab.get_settings()` / `apply_settings()` deben seguir funcionando (usados por SmartStitchGUI)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
