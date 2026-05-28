---
phase: 03-logic-widget-separation
fixed_at: 2026-05-28T03:53:25Z
review_path: .planning/phases/03-logic-widget-separation/03-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-05-28T03:53:25Z
**Source review:** .planning/phases/03-logic-widget-separation/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (2 Critical + 5 Warning)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: `context_menu_service.py` — `sys.path` injection apunta al directorio PADRE del repo

**Files modified:** `WatermarkRemove/services/context_menu_service.py`
**Commit:** af8481e
**Applied fix:** Reducido el calculo de `_repo_root` de tres `os.path.dirname` a dos. Antes aplicaba `dirname` tres veces sobre `_current_dir` (services/ -> WatermarkRemove/ -> repo_root/ -> parent_of_repo_root/). Ahora aplica solo dos niveles como corresponde (services/ -> WatermarkRemove/ -> repo_root/).

---

### CR-02: `wm_positions_persistence.py` — `__file__` no canonicalizado puede resolver a CWD

**Files modified:** `WatermarkRemove/services/wm_positions_persistence.py`
**Commit:** d40ae24
**Applied fix:** Envuelto `os.path.dirname(os.path.dirname(__file__))` con `os.path.abspath()` en la construccion de `_json_path`. Esto garantiza que el path al JSON siempre sea absoluto, independientemente de si `__file__` es relativo (e.g., al ejecutar con `python -m` desde otro directorio).

---

### WR-01: `position_editor_service.py` — `build_preview_pixmap` asume imagen BGR de 3 canales; falla silencioso con BGRA

**Files modified:** `WatermarkRemove/services/position_editor_service.py`
**Commit:** 7ee6331
**Applied fix:** Agregado guard antes de `cvtColor`: si `result_img.ndim == 3 and result_img.shape[2] == 4`, se convierte BGRA a BGR primero. Cambiado desempaquetado `h, w, _` a `h, w, ch` para usar `ch * w` como bytes_per_line en `QImage`. Agregado `.copy()` al retornar el `QPixmap` para forzar copia del buffer numpy y desacoplar la imagen Qt del array temporal.

---

### WR-02: `position_editor.py` — `_check_ready` dispara carga de imagen sin verificar exito; error de `load_image` queda silenciado

**Files modified:** `WatermarkRemove/ui/position_editor.py`
**Commit:** 3a7c5e5
**Applied fix:** Envuelto `self.service.load_image(image_path)` en `_load_current_image` con `try/except (ValueError, OSError)`: en caso de error se pone `self.current_image = None` y se muestra el mensaje en `self.image_label`. Aplicado el mismo patron en `_load_current_watermark`: en caso de error se ponen `current_watermark = None` y `watermark_path = None` con mensaje en label.

---

### WR-03: `watermark_tab.py` — `_update_context_menu_btn` se llama durante `__init__` sin guard de plataforma; crash en non-Windows

**Files modified:** `WatermarkRemove/ui/watermark_tab.py`
**Commit:** ca09667
**Applied fix:** Agregado `import sys as _sys` y guard `if _sys.platform != 'win32'` al inicio de `_update_context_menu_btn` (oculta el boton y retorna) y en `_toggle_context_menu` (muestra QMessageBox.warning y retorna). Esto evita que `winreg` sea importado en plataformas no-Windows al construir el widget.

---

### WR-04: `position_editor.py` — `ZoomableImageLabel` crea un `QWidget()` temporal para acceder a `SizePolicy`

**Files modified:** `WatermarkRemove/ui/position_editor.py`
**Commit:** 56fe433
**Applied fix:** Agregado `QSizePolicy` al bloque de imports de `PySide6.QtWidgets`. Reemplazado `QWidget().sizePolicy().Policy.Expanding` por `QSizePolicy.Policy.Expanding` en la llamada a `self.setSizePolicy`, eliminando los dos objetos `QWidget` temporales.

---

### WR-05: `folder_scan_service.py` — `scan_subfolders` puede lanzar `PermissionError` no manejada

**Files modified:** `WatermarkRemove/services/folder_scan_service.py`, `WatermarkRemove/ui/position_editor.py`
**Commit:** 4d96370
**Applied fix:** Agregada seccion `Raises` al docstring de `scan_subfolders` documentando `PermissionError` y `OSError`. En `PositionEditor._load_watermark_folders`, la llamada a `scan_subfolders` ahora esta envuelta en `try/except OSError`: en caso de error se agrega un item descriptivo al combo y se retorna temprano, en lugar de propagar silenciosamente al slot Qt.

---

_Fixed: 2026-05-28T03:53:25Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
