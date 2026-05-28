---
phase: 03-logic-widget-separation
type: gate-pattern
created: 2026-05-28
purpose: ARCH-02 enforcement — canonical grep pattern for "domain logic in a widget"
---

# Phase 3 — Canonical Domain Grep Pattern

> Patrón grep canónico que los gates de **ARCH-02** (Plans 03-02 y 03-03) usan
> para verificar que los widgets `position_editor.py`, `image_viewer.py` y
> `watermark_tab.py` quedaron sin lógica de dominio inline tras el refactor.
>
> **Definición operacional de "lógica de dominio en un widget"**: cualquier llamada
> a una función/clase de dominio (procesamiento de imagen, persistencia, OS) que
> NO esté detrás de un servicio. Importar un servicio (o el módulo `services`
> entero) es coordinación legítima — invocar `align_watermark(...)`,
> `cv2.cvtColor(...)`, `UtilJson(...)`, `winreg.OpenKey(...)`, etc., desde el
> widget NO lo es.

## Símbolos de dominio que cuentan

Los 8 símbolos siguientes son los marcadores canónicos de lógica de dominio en
los widgets del módulo `WatermarkRemove/ui/`:

| Símbolo                       | Categoría                  | Servicio destino                                              |
|-------------------------------|----------------------------|---------------------------------------------------------------|
| `align_watermark(`            | Procesamiento de imagen    | `PositionEditorService.build_preview_pixmap`                  |
| `remove_watermark(`           | Procesamiento de imagen    | `PositionEditorService.build_preview_pixmap`                  |
| `load_images_cv2(`            | I/O imagen (safe non-ASCII)| `PositionEditorService.load_image` (o NavigationController)   |
| `cv2.`                        | OpenCV directo             | `PositionEditorService` (build_preview_pixmap usa cvtColor)   |
| `UtilJson(`                   | Persistencia JSON          | `WmPositionsPersistenceService` / `WmPersistenceService`      |
| `winreg.`                     | Registro de Windows        | `ContextMenuService`                                          |
| `register_context_menu`       | Toggle menú contextual     | `ContextMenuService.toggle`                                   |
| `UpdateChecker(`              | Update checker             | (decisión de rigor en Plan 03-03 — RESEARCH Open Q #2)        |

## Comando canónico (gate filter)

**Importante:** el grep DEBE filtrar líneas que empiezan con `#` para evitar
self-invalidation (gate hygiene — un comentario `# llamamos a align_watermark`
no es lógica de dominio).

```bash
grep -vE '^\s*#' <archivo> | grep -cE "align_watermark\(|remove_watermark\(|load_images_cv2\(|cv2\.|UtilJson\(|winreg\.|register_context_menu|UpdateChecker\("
```

### Variante con conteo cero esperado (verificación pass/fail)

```bash
COUNT=$(grep -vE '^\s*#' "$ARCHIVO" | grep -cE "align_watermark\(|remove_watermark\(|load_images_cv2\(|cv2\.|UtilJson\(|winreg\.|register_context_menu|UpdateChecker\(")
[ "$COUNT" -eq 0 ] && echo "GATE PASS: $ARCHIVO" || echo "GATE FAIL: $ARCHIVO ($COUNT hits)"
```

## Target post-refactor

Los tres widgets refactorizados deben tender a **0 hits** tras Plans 03-02 / 03-03:

| Widget                                          | Target | Notas                                                |
|-------------------------------------------------|--------|------------------------------------------------------|
| `WatermarkRemove/ui/position_editor.py`         | 0      | Toda la lógica movida a `PositionEditorService`      |
| `WatermarkRemove/ui/image_viewer.py`            | 0      | Scan movido a `folder_scan_service`                  |
| `WatermarkRemove/ui/watermark_tab.py`           | 0      | Context menu movido a `ContextMenuService`           |

### Excepciones permitidas

- **`cv2.` en widgets**: 0 esperado. Toda conversión BGR→RGB / construcción de
  `QImage` debe ocurrir dentro de `PositionEditorService.build_preview_pixmap`
  (el widget recibe un `QPixmap` ya hecho).
- **`UpdateChecker(`**: depende de la decisión de rigor en Plan 03-03 (RESEARCH
  Open Question #2). Si se decide extraer → 0 hits en `watermark_tab.py`. Si
  se mantiene la coordinación inline (mínima, ya delega al `UpdateChecker`)
  → puede quedar 1 import + 1 instanciación; documentar en el SUMMARY del plan
  que tomó la decisión.
- **`UtilJson(`**: 0 esperado — todas las llamadas pasan por los servicios de
  persistencia. Una excepción aceptable sería un script ad-hoc, NUNCA un widget.

## Uso recomendado por los planes

- **Plan 03-02 (position_editor + image_viewer)**: ejecutar el comando sobre
  `position_editor.py` y `image_viewer.py` al final del plan. Esperar 0 hits
  en ambos.
- **Plan 03-03 (watermark_tab coordinator)**: ejecutar el comando sobre
  `watermark_tab.py`. Esperar 0 hits (o 1-2 hits documentados si se difiere
  la extracción de `UpdateChecker`).

## Source / Referencias

- RESEARCH §Validation Architecture L332-361 (Wave 0 Gaps L356-359).
- PATTERNS §"Logic/Widget Separation - Pattern Map" L1-269 (símbolos extraídos).
- Plan 03-01 acceptance criteria (el patrón sale 0 en los servicios de Wave 0
  también — los servicios PUEDEN contener los símbolos; lo prohibido es en los
  widgets `WatermarkRemove/ui/`).
