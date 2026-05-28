---
phase: 03-logic-widget-separation
verified: 2026-05-27T00:00:00Z
status: human_needed
score: 8/8 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Ejecutar las 5 secciones de 03-HUMAN-UAT.md con la aplicación corriendo"
    expected: "Editor de posiciones preview en vivo; guardado al final del batch; wm_positions.json correcto; visor de imágenes con grid; menú contextual registra/desregistra; actualización muestra diálogo; SlideshowViewer abre con checkbox activo"
    why_human: "Comportamiento UI en tiempo real, interacción con registro de Windows, y flujo end-to-end no son verificables mediante grep/compile"
---

# Phase 3: Logic/Widget Separation — Verification Report

**Phase Goal:** Los widgets de WatermarkRemove solo coordinan y presentan — ninguna lógica de dominio vive dentro de un widget, y WatermarkTab es un coordinador puro
**Verified:** 2026-05-27
**Status:** human_needed
**Re-verification:** No — verificación inicial

---

## Goal Achievement

### Observable Truths (Success Criteria del ROADMAP)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | `WatermarkTab.get_settings()` y `apply_settings()` siguen funcionando — SmartStitchGUI no requiere cambios | VERIFIED | `watermark_tab.py:210` define `get_settings`, `watermark_tab.py:235` define `apply_settings = set_settings`; `git diff HEAD -- gui/controller.py` vacío; controller.py:76 instancia `WatermarkTab()` sin args |
| SC-2 | Ningún widget en `WatermarkRemove/ui/` contiene lógica de negocio inline — solo llamadas a servicios extraídos | VERIFIED | Grep canónico (`align_watermark\|remove_watermark\|load_images_cv2\|cv2.\|UtilJson`) filtrado por comentarios retorna **0** en `position_editor.py`; **0** en `image_viewer.py`; grep winreg/register_context_menu retorna **0** en `watermark_tab.py` |
| SC-3 | WatermarkTab no orquesta lógica directamente: conecta señales de UI con servicios, sin condicionales de dominio propios | VERIFIED | `_toggle_context_menu` delega a `context_menu_service.toggle()` (L158); `_update_context_menu_btn` delega a `context_menu_service.is_registered()` (L149); `_is_context_menu_registered` eliminado completamente (0 hits) |
| SC-4 | El flujo completo funciona sin regresión | UNCERTAIN — requiere human | UAT manual (Task 2 del Plan 03-03) fue aprobado por el usuario según SUMMARY, pero requiere confirmación en ejecución real de la aplicación |

**Score:** 8/8 truths de must_haves verificadas en codebase. SC-4 requiere confirmación humana.

---

### Must-Haves por Plan

#### Plan 03-01 — Servicios de Dominio (Wave 0)

| Truth | Status | Evidence |
|-------|--------|----------|
| Existe PositionEditorService con build_preview_pixmap que retorna QPixmap, sin dominio inline en el widget | VERIFIED | `position_editor_service.py:36` `class PositionEditorService`; `L67` `def build_preview_pixmap`; llama `align_watermark` L100, `remove_watermark` L108, retorna `QPixmap.fromImage` L112 |
| Existe folder_scan_service con scan_images/scan_pngs/scan_subfolders, sin Qt | VERIFIED | Tres funciones en `folder_scan_service.py:22,46,67`; grep PySide6 → 0 |
| Existe WmPositionsPersistenceService apuntando a `WatermarkRemove/wm_positions.json` | VERIFIED | `wm_positions_persistence.py:34`; path verificado con python: `watermarkremove\wm_positions.json` (destino correcto) |
| Existe ContextMenuService con is_registered/toggle, guard FileNotFoundError, sin Qt | VERIFIED | `context_menu_service.py:30`; `KEY` L42; `except FileNotFoundError` L60; grep PySide6/QMessageBox → 0 |
| Barrel `services/__init__.py` exporta nuevos servicios e instancias singleton | VERIFIED | `__init__.py` exporta 10 símbolos: 4 clases + 4 singletons + 3 funciones puras; `wm_persistence` Phase 1 preservado |

#### Plan 03-02 — Refactor position_editor + image_viewer (ARCH-02)

| Truth | Status | Evidence |
|-------|--------|----------|
| position_editor.py no calcula align/remove/cv2→QPixmap inline | VERIFIED | `_update_preview` llama `self.service.build_preview_pixmap(...)` L484-491; grep dominio → 0 |
| position_editor.py no escanea carpetas inline | VERIFIED | `_load_images` usa `scan_images` L411; `_load_watermarks_into_combo` usa `scan_pngs` L425; `_load_watermark_folders` usa `scan_subfolders` L387 |
| position_editor.py no escribe wm_positions.json inline | VERIFIED | `_save_to_json` delega a `wm_positions_persistence.save_positions(...)` L572; imports muertos (cv2, numpy, natsort, UtilJson, load_images_cv2, align_watermark, remove_watermark, QImage) eliminados — grep → 0 |
| image_viewer.py no escanea la carpeta inline | VERIFIED | `_load_images` usa `scan_images(self.folder_path, self.SUPPORTED_FORMATS)` L102; `from WatermarkRemove.services import scan_images` L19 |
| Comportamiento observable preservado | VERIFIED (parcial — runtime necesita human) | `_save_and_next` acumula en `saved_positions` L546 y solo llama `_save_to_json()` L556 al llegar a la última imagen (comportamiento "guardar al final del batch" preservado); `if self.folder_path.is_file(): self.folder_path = self.folder_path.parent` L97-98 preservado en image_viewer; `SUPPORTED_FORMATS` con `.psd/.psb` NO unificado L27 |

#### Plan 03-03 — WatermarkTab coordinador puro (ARCH-04)

| Truth | Status | Evidence |
|-------|--------|----------|
| watermark_tab.py no contiene lógica winreg inline | VERIFIED | Grep `winreg.\|register_context_menu` filtrado → 0; `_is_context_menu_registered` eliminado (0 hits); import `context_menu_service` en L21 |
| watermark_tab.py preserva el contrato externo | VERIFIED | `def __init__(self, parent=None)` L32; `self.run_quita_marcas = QCheckBox(...)` L50; `def log(self, message)` L206; `def get_settings` L210; `def set_settings` L222; `apply_settings = set_settings` L235; controller.py L76/L317 intactos |
| WatermarkTab conecta señales con servicios sin condicionales de dominio propios | VERIFIED | `_toggle_context_menu` = `context_menu_service.toggle()` + QMessageBox (presentación); `_update_context_menu_btn` = `context_menu_service.is_registered()` + setText (presentación); `_check_for_updates` delega a `UpdateChecker` — decisión documentada: try/except + setEnabled es feedback de UI, no dominio |
| Flujo completo sin regresión | UNCERTAIN — requiere human | Ver sección de Human Verification |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `WatermarkRemove/services/position_editor_service.py` | Lógica de dominio del editor (load/align/remove/preview QPixmap) | VERIFIED | Existe, sustancial (113 líneas), importada por position_editor.py L21 |
| `WatermarkRemove/services/folder_scan_service.py` | Escaneo de carpetas + filtro extensiones (funciones puras) | VERIFIED | Existe, sustancial (83 líneas), importada por position_editor.py L21 e image_viewer.py L19 |
| `WatermarkRemove/services/wm_positions_persistence.py` | Persistencia anidada de wm_positions.json | VERIFIED | Existe, sustancial (137 líneas), importada por position_editor.py L22 |
| `WatermarkRemove/services/context_menu_service.py` | Detección + toggle menú contextual Windows | VERIFIED | Existe, sustancial (87 líneas), importada por watermark_tab.py L21 |
| `WatermarkRemove/services/__init__.py` | Barrel con 10 exportaciones (4 clases + 4 singletons + 3 funciones) | VERIFIED | Exporta todos los símbolos requeridos incluyendo `wm_persistence` Phase 1 |
| `WatermarkRemove/ui/position_editor.py` | Widget coordinador que delega dominio a servicios | VERIFIED | Importa servicios L21-27; 0 hits dominio inline |
| `WatermarkRemove/ui/image_viewer.py` | Widget visor que delega escaneo al servicio | VERIFIED | Importa `scan_images` L19; 0 hits dominio inline |
| `WatermarkRemove/ui/watermark_tab.py` | Coordinador puro con alias apply_settings | VERIFIED | Importa `context_menu_service` L21; 0 hits winreg inline; alias L235 |
| `.planning/phases/03-logic-widget-separation/03-DOMAIN-GREP.md` | Patrón grep canónico de dominio (gate ARCH-02) | VERIFIED | Existe; contiene `align_watermark` (5 hits del símbolo) |
| `.planning/phases/03-logic-widget-separation/03-HUMAN-UAT.md` | Guion UAT manual 5 secciones (SC-4) | VERIFIED | Existe; contiene las 5 secciones esperadas |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `position_editor_service.py` | `WatermarkRemove` (wm_remove) | `from WatermarkRemove import load_images_cv2, align_watermark, remove_watermark` | WIRED | L33 — importa y usa en `load_image` L65 y `build_preview_pixmap` L100/L108 |
| `services/__init__.py` | 4 servicios nuevos | barrel export | WIRED | Importa las 4 clases + 3 funciones puras; crea 4 singletons; `__all__` actualizado |
| `position_editor.py` | `WatermarkRemove.services` | `from WatermarkRemove.services import position_editor_service, wm_positions_persistence, scan_images, scan_pngs, scan_subfolders` | WIRED | L21-27; singletons usados en `_update_preview`, `_save_to_json`, `_load_images`, `_load_watermarks_into_combo`, `_load_watermark_folders` |
| `image_viewer.py` | `WatermarkRemove.services.folder_scan_service` | `from WatermarkRemove.services import scan_images` | WIRED | L19; usado en `_load_images` L102 |
| `watermark_tab.py` | `WatermarkRemove.services.context_menu_service` | `from WatermarkRemove.services import context_menu_service` | WIRED | L21; usado en `_update_context_menu_btn` L149 y `_toggle_context_menu` L158 |
| `gui/controller.py` | `WatermarkTab.run_quita_marcas` | acceso directo al atributo | WIRED | `controller.py:317` — `watermark_tab.run_quita_marcas.isChecked()` sin cambios |

---

### Data-Flow Trace (Level 4)

Aplica a los servicios que producen datos consumidos por los widgets.

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|--------------------|--------|
| `position_editor.py._update_preview` | `pixmap` | `position_editor_service.build_preview_pixmap(image, watermark, ...)` | Sí — `align_watermark` + `remove_watermark` + `cv2.cvtColor` + `QImage` | FLOWING |
| `position_editor.py._save_to_json` | `target_label` | `wm_positions_persistence.save_positions(...)` → `UtilJson.set(...)` | Sí — escribe al archivo `wm_positions.json` en disco | FLOWING |
| `image_viewer.py._load_images` | `image_files` | `scan_images(self.folder_path, self.SUPPORTED_FORMATS)` → `natsorted(folder.iterdir())` | Sí — lista real de archivos del filesystem | FLOWING |
| `watermark_tab.py._update_context_menu_btn` | estado del botón | `context_menu_service.is_registered()` → `winreg.OpenKey(...)` | Sí — consulta al registro de Windows en runtime | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Todos los archivos compilan | `python -m py_compile` sobre 8 archivos (4 servicios + barrel + 3 widgets) | COMPILE_OK | PASS |
| Grep dominio en position_editor | filtrado por comentarios sobre `align_watermark\|remove_watermark\|load_images_cv2\|cv2.\|UtilJson` | 0 | PASS |
| Grep dominio en image_viewer | ídem | 0 | PASS |
| Grep winreg en watermark_tab | filtrado por comentarios sobre `winreg.\|register_context_menu` | 0 | PASS |
| Path JSON correcto | `python -c "... print(str(s._json_path))"` | `watermarkremove\wm_positions.json` | PASS |
| controller.py intacto | `git diff HEAD -- gui/controller.py` | vacío | PASS |
| Commits de Phase 3 existen | `git log --oneline` | `20d2d5e`, `556705b`, `75e844b`, `f1cca33`, `254f36f`, `45b3d88` confirmados | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ARCH-02 | 03-01, 03-02 | Lógica de negocio separada de widgets UI | SATISFIED | Grep de dominio retorna 0 en los 3 widgets; 4 servicios de dominio creados y usados; imports muertos eliminados |
| ARCH-04 | 03-03 | WatermarkTab como coordinador puro | SATISFIED | `_is_context_menu_registered` eliminado; winreg/register_context_menu en 0 hits; `context_menu_service.toggle()` es el único call-site del dominio OS; `apply_settings` alias presente |

**Nota sobre estado en REQUIREMENTS.md:** Los checkboxes de ARCH-02 y ARCH-04 siguen marcados como `[ ]` en `REQUIREMENTS.md` (Pendientes), aunque el ROADMAP.md los marca como completados. La implementación en el codebase satisface ambos requisitos. Esta inconsistencia documental no bloquea el goal — es seguimiento administrativo.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `WatermarkRemove/ui/watermark_tab.py` | 100 | `TODO:` sin referencia a issue/PR | INFO | No es blocker — el TODO existía antes de Phase 3 (commit `ddc70b8`, Phase 1 o anterior); Phase 3 no lo introdujo (verificado con `git show 45b3d88 | grep "^+.*TODO"` → sin resultados) |

---

### Human Verification Required

#### 1. Flujo completo del Editor de Posiciones (SC-4, ARCH-02)

**Test:** Desde SmartStitchGUI.py, abrir la pestaña Quita Marcas, click "Editor de Posiciones". Seleccionar carpeta de imágenes + carpeta de marcas + marca específica. Ajustar offset X/Y y los combos de posición.
**Expected:** El preview se actualiza en vivo en el panel derecho. Pulsar "Guardar y Siguiente" hasta la última imagen — debe aparecer QMessageBox "Completado" con el conteo correcto. Cerrar, reabrir el editor, recargar la misma carpeta+marca y confirmar que `WatermarkRemove/wm_positions.json` contiene la estructura `carpeta → marca → pos_N` intacta.
**Why human:** Preview de imagen en tiempo real y persistencia JSON requieren ejecución real de la aplicación con datos de prueba reales.

#### 2. Visor de Imágenes (SC-4, ARCH-02)

**Test:** Click en "Ver Imágenes de Input" con una carpeta válida en el inputField.
**Expected:** Se abre el visor con un grid de thumbnails y el contador muestra la cantidad correcta de imágenes.
**Why human:** Renderizado de thumbnails y conteo correcto requieren carpeta real con imágenes.

#### 3. Menú Contextual Windows (SC-4, ARCH-04)

**Test:** Click en "Registrar menú contextual" → confirmar el QMessageBox → hacer click derecho en una carpeta del explorador de Windows → click en "Desregistrar menú contextual".
**Expected:** El texto del botón alterna entre "Registrar" y "Desregistrar"; la entrada "Abrir con SmartStitch WR" aparece/desaparece en el menú contextual del explorador.
**Why human:** Interacción con el registro de Windows y confirmación visual en el explorador no son automatizables.

#### 4. Buscar Actualizaciones (SC-4)

**Test:** Click en "Buscar Actualizaciones".
**Expected:** Se muestra el diálogo de actualización o el QMessageBox "Ya tienes la última versión disponible". El botón queda habilitado de nuevo al terminar.
**Why human:** Requiere conexión a red real y verificación del estado del botón durante la espera.

#### 5. Contrato externo — flujo end-to-end (SC-1, SC-4)

**Test:** En SmartStitchGUI.py, marcar el checkbox "Ejecutar Quita Marcas" y click en "Iniciar Proceso".
**Expected:** Se abre el `SlideshowViewer` antes del pipeline de stitching. El flujo completo de Phase 2 sigue intacto.
**Why human:** Requiere el pipeline completo de la aplicación corriendo con datos reales.

---

### Gaps Summary

Sin gaps en la implementación. Todos los must-haves del plan (truths, artifacts, key_links) están verificados en el codebase con evidencia directa. El estado `human_needed` se debe exclusivamente a los 5 items de verificación de comportamiento runtime (SC-4) que no pueden verificarse mediante análisis estático.

---

## Notas del Verificador

**Decisión de rigor documentada (ARCH-04):** El método `_check_for_updates` en `watermark_tab.py` contiene `UpdateChecker(` (1 hit). Esta es una excepción aceptada documentada en 03-03-SUMMARY.md y en el commit `45b3d88`: `UpdateChecker` es un servicio externo de `core.services`; el código inline restante (`try/except` + `setEnabled/setText`) es feedback de presentación legítimo de un coordinador. ARCH-04 exige eliminar la lógica de dominio OS (winreg), que sí se eliminó. El hit de `UpdateChecker` no contradice ARCH-04.

**REQUIREMENTS.md desactualizado:** Los checkboxes `[ ]` de ARCH-02 y ARCH-04 en `.planning/REQUIREMENTS.md` no fueron actualizados a `[x]` durante la fase. Recomendación: actualizar el tracking tras el sign-off de UAT.

---

_Verified: 2026-05-27_
_Verifier: Claude (gsd-verifier)_
