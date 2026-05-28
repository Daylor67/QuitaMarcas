---
phase: 03-logic-widget-separation
plan: 02
subsystem: ui
wave: 2

tags: [pyside6, watermark-remove, arch-02, position-editor, image-viewer, services-delegation]

# Dependency graph
requires:
  - phase: 03-logic-widget-separation
    plan: 01
    provides: position_editor_service, wm_positions_persistence, scan_images/scan_pngs/scan_subfolders

provides:
  - WatermarkRemove/ui/position_editor.py refactored — 0 inline domain calls (ARCH-02)
  - WatermarkRemove/ui/image_viewer.py refactored — 0 inline domain calls (ARCH-02)
  - Pattern: widget coordinates presentation only; domain delegated to services barrel

affects: [03-03-watermark-tab-coordinator]

# Tech tracking
tech-stack:
  added: []   # No new packages — solo delegación a servicios ya creados en 03-01
  patterns:
    - "Widget como coordinador de presentación: importa servicios desde el barrel, llama métodos, no construye lógica de dominio inline"
    - "Error-handling se queda en el widget (setText / QMessageBox) — el servicio levanta excepciones; el widget las traduce a UI feedback"
    - "Side-effects de UI se preservan ANTES de llamar al servicio (ej. reasignar self.folder_path = parent para que path_label refleje la carpeta real)"
    - "SUPPORTED_FORMATS se pasa como parámetro al servicio — cada widget mantiene su propia tupla (image_viewer incluye .psd/.psb)"

key-files:
  created: []
  modified:
    - WatermarkRemove/ui/position_editor.py
    - WatermarkRemove/ui/image_viewer.py

key-decisions:
  - "Reasignación de self.folder_path = parent en image_viewer se mantiene ANTES de llamar scan_images (no se quita aunque el servicio también baje a parent internamente) — porque el side-effect del path_label depende de que la variable de instancia quede actualizada"
  - "self.service = position_editor_service se asigna en __init__ — fija el contrato del singleton del barrel a una atributo del widget, facilita testing futuro (ARCH-05 deferred) y hace explícita la dependencia"
  - "scan_pngs llena self.watermark_files una sola vez (lista del servicio) y luego itera para .addItem — preserva la semántica original 'cargar y registrar a la vez' sin duplicar el for"
  - "Imports muertos eliminados verbatim: cv2, numpy, natsort, UtilJson, load_images_cv2, align_watermark, remove_watermark, QImage — todos verificados con grep antes de borrar; no quedaron usos residuales"

patterns-established:
  - "Widget refactor recipe: 1) import singletons del barrel en __init__, 2) reemplazar dominio inline por llamadas al servicio, 3) preservar guards / try-except / QMessageBox del widget original, 4) eliminar imports muertos solo tras grep, 5) verificar ARCH-02 grep gate"

requirements-completed: [ARCH-02]

# Metrics
duration: ~6min
completed: 2026-05-28
---

# Phase 3 Plan 02: Position Editor + Image Viewer Refactor Summary

**position_editor.py e image_viewer.py refactorizados como coordinadores de presentación que delegan TODO el dominio (preview, load, scan, persist) a los servicios de Plan 03-01 — 0 hits del grep ARCH-02 en ambos widgets, compilación OK, smoke runtime OK, comportamiento observable preservado (save-on-last, path_label, error handling).**

## Performance

- **Duration:** ~6 min
- **Tasks:** 2 / 2 completed atomically
- **Files modified:** 2 (`position_editor.py`, `image_viewer.py`)
- **Files created:** 0 (delegación pura — los servicios ya existían desde 03-01)
- **Lines net:** -17 (51 inserciones, 68 eliminaciones) — el widget queda más liviano

## Accomplishments

- **`position_editor.py` refactored (Task 1, commit `f1cca33`):**
  - `_update_preview` ya no calcula `align_watermark` / `remove_watermark` / `cv2.cvtColor` / `QImage` inline — una sola llamada a `self.service.build_preview_pixmap(...)` retorna el `QPixmap` listo. El try/except con `setText("❌ Error: ...")` permanece en el widget.
  - `_load_current_image` y `_load_current_watermark` delegan a `self.service.load_image(path)` (preserva `np.fromfile` y paths non-ASCII).
  - `_load_images` usa `scan_images(folder, SUPPORTED_FORMATS)`.
  - `_load_watermark_folders` usa `scan_subfolders(marcas_base_path)` (orden reverse preservado).
  - `_load_watermarks_into_combo` usa `scan_pngs(folder)`.
  - `_save_to_json` delega a `wm_positions_persistence.save_positions(...)` — preserva la estructura `folder -> mark -> pos_N` (o `folder -> pos_N` modo legacy), el parseo defensivo de claves existentes (`.get(name, {}) or {}`), y el `ValueError` guard cuando `save_by_watermark=True` sin marca seleccionada. El `QMessageBox.critical` permanece en el widget.
  - `_save_and_next` **intacto**: sigue acumulando en `self.saved_positions` y solo llama `_save_to_json()` cuando llega a la última imagen — comportamiento "guardar al final del batch" + diálogo con conteo preservado (Pitfall 5).
  - Imports muertos eliminados: `cv2`, `numpy`, `natsort.natsorted`, `utils.UtilJson`, `WatermarkRemove.load_images_cv2`, `WatermarkRemove.align_watermark`, `WatermarkRemove.remove_watermark`, `PySide6.QtGui.QImage`. `QPixmap` se conserva (lo usa `ZoomableImageLabel.set_image` como type hint).

- **`image_viewer.py` refactored (Task 2, commit `254f36f`):**
  - `_load_images` ya no escanea inline — usa `scan_images(self.folder_path, self.SUPPORTED_FORMATS)`.
  - `if self.folder_path.is_file(): self.folder_path = self.folder_path.parent` **preservado** ANTES de la llamada al servicio: el widget DEBE reasignar la variable de instancia para que `path_label` refleje la carpeta real, no el archivo (side-effect documentado en el plan).
  - `SUPPORTED_FORMATS` con `.psd/.psb` **NO unificado** — se pasa como parámetro al servicio (`folder_scan_service` es paramétrico precisamente por esto).
  - Import `from natsort import natsorted` eliminado (sin más usos).
  - `_create_image_widget` / `_show_full_image` siguen usando `QPixmap(str(image_path))` para thumbnails — es presentación nativa de Qt, **NO** carga cv2 de dominio (PATTERNS L118 confirma que esto se queda).

- **ARCH-02 gate verified on both widgets** — el grep canónico (`align_watermark(|remove_watermark(|load_images_cv2(|cv2.|UtilJson(`, filtrado por comentarios) retorna **0** en `position_editor.py` y **0** en `image_viewer.py`.

- **Contrato externo intacto** — `git diff 0538d8f..HEAD -- gui/controller.py` vacío. Ningún archivo fuera de los dos targets cambió (verificado con `git diff --stat`).

## Task Commits

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Refactorizar position_editor.py — delegar align/remove/load/scan/persist a los servicios | `f1cca33` (refactor) | `WatermarkRemove/ui/position_editor.py` |
| 2 | Refactorizar image_viewer.py — delegar el escaneo de carpeta a `scan_images` | `254f36f` (refactor) | `WatermarkRemove/ui/image_viewer.py` |

## Files Modified

- `WatermarkRemove/ui/position_editor.py` — refactor: -61 / +42 líneas. Imports limpios, 6 métodos delegando a servicios, `_save_and_next` y `_adjust_window_size` intactos.
- `WatermarkRemove/ui/image_viewer.py` — refactor: -7 / +9 líneas. Import `natsort` eliminado, `_load_images` delega scan, side-effect del path_label preservado.

## Decisions Made

- **`self.service = position_editor_service` en `__init__`** (en lugar de importar y llamar como módulo): hace explícita la dependencia del widget al servicio, simplifica el patch en tests futuros (ARCH-05 está deferred a v2 pero el patrón ya queda listo), y mantiene simetría con cómo `WatermarkProcessor` instancia sus componentes.
- **Reasignación de `self.folder_path` SE QUEDA en image_viewer**: aunque `scan_images` también baja a `parent` cuando recibe un archivo, el widget necesita actualizar la variable de instancia para que el `path_label` muestre la carpeta correcta. No es duplicación de dominio — es un side-effect de presentación legítimo.
- **`scan_pngs` reemplaza el loop pero NO el `.addItem`**: el servicio retorna la lista filtrada; el widget la asigna a `self.watermark_files` y luego itera para registrar cada uno en el combo. La presentación (combo population) se queda en el widget; el escaneo se va al servicio.
- **`QImage` import eliminado de QtGui**: tras mover la construcción de QImage al servicio, no quedaron usos en el widget. `QPixmap` se preserva porque `ZoomableImageLabel.set_image(pixmap: QPixmap)` lo usa como type hint y `self.image_label.set_image(pixmap)` lo pasa.

## Deviations from Plan

None — plan ejecutado exactamente como fue escrito.

El único momento de fricción fue durante la primera iteración de Task 1: usé el path absoluto de la herramienta `Edit` apuntando al checkout principal (`C:\Users\Felix\Desktop\Python\manhwa_ocr\SmartStitch\...`) en lugar del worktree (`C:\Users\Felix\Desktop\Python\manhwa_ocr\SmartStitch\.claude\worktrees\agent-ab7b78d88ac4ef1bf\...`). Detectado vía `git status --short` que mostró el diff en el repo principal y un worktree limpio. Revertido inmediatamente con `git checkout --` en el repo principal y re-aplicado en el worktree. Cero contaminación cruzada hacia la rama principal (`refactorizacion-WatermrkRemove` quedó sin cambios). Lección: las edits dentro de un worktree DEBEN usar el path absoluto del worktree (o relativo desde la cwd del worktree); el path absoluto del checkout principal resuelve al repo equivocado aunque el archivo existe en ambos.

## Issues Encountered

- **Cross-checkout edit bug (detectado y resuelto):** la primera tanda de 7 edits en `position_editor.py` aterrizó en `C:\Users\Felix\Desktop\Python\manhwa_ocr\SmartStitch\WatermarkRemove\ui\position_editor.py` (checkout principal) en lugar del worktree, porque usé el path absoluto fuera del worktree. Resuelto con `git checkout -- WatermarkRemove/ui/position_editor.py` en el checkout principal y re-aplicación de las mismas 7 edits con el path absoluto del worktree. El contenido final del worktree es idéntico a lo planeado; el repo principal quedó intacto.

## User Setup Required

None — no se instalaron paquetes, no se cambiaron configs, no se requieren env vars.

## Threat Model Verification

| Threat ID | Disposition | Verification |
|-----------|-------------|--------------|
| T-03-02-01 | mitigate | `self.service.load_image` usa `load_images_cv2` (np.fromfile) — verificado en `position_editor_service.py:65`. Cero `cv2.imread` en el grep. |
| T-03-02-02 | mitigate | `wm_positions_persistence.save_positions` preserva la estructura anidada + el parseo defensivo + el ValueError guard. Sin tocar el formato del JSON. |
| T-03-02-03 | mitigate | `SUPPORTED_FORMATS` se pasa como parámetro a `scan_images` en ambos widgets (no se unifica). Filtro de extensiones preservado. |
| T-03-SC | accept | 0 paquetes instalados (verificado: no se ejecutó pip/npm/cargo install). |

## Next Phase Readiness

- **Plan 03-03 (watermark_tab coordinator)** puede proceder sin bloqueos: los servicios ya están consumidos por dos de tres widgets, y `context_menu_service` está listo en el barrel desde 03-01 para que `watermark_tab.py` lo use.
- **ARCH-02 progreso**: 2/3 widgets ya cumplen (position_editor + image_viewer). Falta `watermark_tab.py` (Plan 03-03).
- **UAT manual**: secciones 1 (Editor de Posiciones) y 2 (Visor de Imágenes) de `03-HUMAN-UAT.md` quedan listas para ejecutar en el wave merge / phase gate.
- **No blockers, no concerns.**

## Self-Check: PASSED

Verified before returning:

- `[ -f WatermarkRemove/ui/position_editor.py ]` → FOUND (modified)
- `[ -f WatermarkRemove/ui/image_viewer.py ]` → FOUND (modified)
- `git log --oneline | grep -q f1cca33` → FOUND (Task 1)
- `git log --oneline | grep -q 254f36f` → FOUND (Task 2)
- `python -m py_compile WatermarkRemove/ui/position_editor.py` → COMPILE_OK
- `python -m py_compile WatermarkRemove/ui/image_viewer.py` → COMPILE_OK
- ARCH-02 grep `position_editor.py` → DOMAIN_HITS: 0
- ARCH-02 grep `image_viewer.py` → DOMAIN_HITS: 0
- Smoke `PositionEditor()` → PE_OK
- Smoke `ImageViewer('.')` → IV_OK
- `git diff 0538d8f..HEAD -- gui/controller.py` → empty (contrato externo intacto)
- Solo 2 archivos cambiados en el rango del plan (verificado con `git diff --stat`)

---
*Phase: 03-logic-widget-separation*
*Plan: 02 of 3 (Wave 2 — position_editor + image_viewer refactor)*
*Completed: 2026-05-28*
