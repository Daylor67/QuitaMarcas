---
phase: 01-json-persistence
reviewed: 2026-05-26T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - WatermarkRemove/services/__init__.py
  - WatermarkRemove/services/wm_persistence.py
  - WatermarkRemove/ui/slideshow_viewer.py
  - WatermarkRemove/ui/watermark_tab.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-05-26T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

This phase introduced `WmPersistenceService` (a thin `UtilJson` wrapper) and wired it into `SlideshowViewer`. The service itself is minimal and the integration is mostly correct, but two blockers exist: one is a write-time crash when the settings directory does not yet exist (`UtilJson.write()` has no `mkdir`), and one is a logic defect where `get_last_crop_pixels()` silently coerces `None` back to `0` while masking a falsy-value bug. Five warnings cover: a module-level singleton created at import time (side-effect on load), a double `int()` cast that can raise on bad input, an auto-save path that overwrites unmodified files unconditionally when navigating backward, `QImage` constructed from a possibly-stale data buffer, and a TODO comment left in production-path code. Four info items cover minor dead code and style issues.

---

## Critical Issues

### CR-01: `UtilJson.write()` crashes if the settings directory does not exist

**File:** `WatermarkRemove/services/wm_persistence.py:22`

`self._path` is constructed as `os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')`. `SETTINGS_REL_DIR` resolves to `<base>/__settings__/`. On a fresh install (or any environment where `__settings__/` has not been created yet) the very first `set_last_crop_pixels()` or `set_last_watermark_folder()` call will hit `UtilJson.write()` → `open(self.path, 'w', ...)`, which raises `FileNotFoundError` because `json_utils.py:61` does not call `self.path.parent.mkdir(parents=True, exist_ok=True)` before opening for write.

The `read()` path returns `{}` silently on `FileNotFoundError` (line 48 of `json_utils.py`), so reads are safe, but the first write will crash silently inside `_on_crop_pixels_changed` or `_on_watermark_folder_changed` unless the directory already exists. The error is swallowed by no caller-level try/except in those slots, so it surfaces as a silent no-op — but it will also propagate as an unhandled exception in debug environments.

**Fix:** Add directory creation to `WmPersistenceService.__init__`:
```python
def __init__(self):
    self._path = os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')
    os.makedirs(SETTINGS_REL_DIR, exist_ok=True)
```
This is the correct layer to fix it — the service owns its storage path and should guarantee the directory is ready before any caller writes.

---

### CR-02: `get_last_crop_pixels()` silently treats a stored value of `0` correctly but treats any falsy non-zero value as `0` (broken `or` guard)

**File:** `WatermarkRemove/services/wm_persistence.py:26`

```python
return UtilJson(self._path).get('last_crop_pixels', 0) or 0
```

The `or 0` guard is meant to handle `None` (when the key does not exist). However `UtilJson.get()` already returns the supplied default (`0`) when the key is missing, so the outer `or 0` is redundant. The real defect is that if the JSON file stores a truthy but semantically invalid value (e.g., a string `"10"` — possible after manual editing, or if a future refactor stores it differently), `or 0` would return the string rather than `0`, and the `int()` cast in the caller (`slideshow_viewer.py:263`) would then be the last line of defence. More importantly, if the stored value is `0` (a legitimate crop value meaning "no crop"), the expression evaluates correctly — but the redundant `or 0` makes the intent opaque and invites future breakage. The defect in the opposite direction: if somehow `None` *is* returned (e.g., the key exists with a JSON `null` value), `or 0` correctly returns `0`, so that path works. The net bug is that `UtilJson.get('last_crop_pixels', 0)` can never return `None` given a default of `0`, making the guard both misleading and masking the true expected type.

The combined effect: the type contract of the method (`-> int`) is not enforced at the boundary. If the file is corrupted with a non-numeric value the caller `int(saved_crop)` at line 263 of `slideshow_viewer.py` will raise `ValueError`/`TypeError`, crashing `__init__` and preventing the dialog from opening.

**Fix:**
```python
def get_last_crop_pixels(self) -> int:
    """Retorna el último valor de crop pixels. Default: 0."""
    raw = UtilJson(self._path).get('last_crop_pixels', 0)
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0
```
This makes the method honour its own return type annotation unconditionally and removes the misleading `or 0`.

---

## Warnings

### WR-01: Module-level singleton instantiated at import time

**File:** `WatermarkRemove/services/__init__.py:3`

```python
wm_persistence = WmPersistenceService()
```

`WmPersistenceService.__init__` calls `os.path.join(SETTINGS_REL_DIR, ...)` which transitively imports `core.utils.constants`, resolves `sys.executable`, and joins filesystem paths. This runs at `import WatermarkRemove.services` time — i.e., before any application setup has completed. In test contexts this means every `import` of any module under `WatermarkRemove.services` creates a real filesystem side-effect (the `os.makedirs` fix from CR-01 would make that worse). It also prevents dependency injection and makes unit testing without patching hard.

**Fix:** Use a lazy accessor pattern or a module-level `None` sentinel initialised on first access, or move the singleton creation to application startup code:
```python
_wm_persistence: Optional['WmPersistenceService'] = None

def get_wm_persistence() -> 'WmPersistenceService':
    global _wm_persistence
    if _wm_persistence is None:
        _wm_persistence = WmPersistenceService()
    return _wm_persistence
```
Alternatively, if the singleton pattern must be preserved, document the import-time side-effect explicitly.

---

### WR-02: `set_last_crop_pixels` double-casts `value` but does not guard against non-int input

**File:** `WatermarkRemove/services/wm_persistence.py:30`

```python
def set_last_crop_pixels(self, value: int) -> None:
    UtilJson(self._path).set('last_crop_pixels', int(value))
```

The type hint says `int` but `int(value)` is called anyway, implying the author expects non-int input. The caller in `slideshow_viewer.py:865` passes the raw `QSpinBox` value (already an `int`), so the cast is currently harmless, but the method's contract is inconsistent — it either trusts the type hint (remove `int()`) or it doesn't (accept `Union[int, float, str]` and document it). As written, if a float like `1.9` is passed, `int(1.9)` silently truncates to `1`, which may not be the intended behaviour.

**Fix:** Remove `int()` and enforce the type hint at the call site, or use `round()` if truncation is intentional:
```python
def set_last_crop_pixels(self, value: int) -> None:
    """Persiste el valor de crop pixels."""
    UtilJson(self._path).set('last_crop_pixels', value)
```

---

### WR-03: Navigating backward unconditionally saves unmodified images

**File:** `WatermarkRemove/ui/slideshow_viewer.py:1128-1135`

`_next_image()` calls `_save_current_image_as_is()` for any image not in `self.processed_images` before advancing. This is intentional for forward navigation. However, `_previous_image()` (line 1144) does **not** perform this save, so the behaviour is asymmetric — going back and then forward again re-triggers the "save as-is" for the same image. More critically, if the user navigates forward past image N (it gets saved as-is and added to `processed_images`), then backward to N, modifies it via manual mode, accepts the preview (which updates `working_image` and adds to `processed_images`), but then navigates forward again — `_next_image()` skips the `_save_current_image_as_is()` because the index is already in `processed_images`. This part works correctly. But if the user navigates forward without accepting (mid-preview), `is_preview_active` is still `True`, `_clear_image_memory()` is called (which resets `is_preview_active`), and the unsaved preview state is silently discarded with no warning to the user.

**Fix:** Before calling `_clear_image_memory()` in both `_next_image()` and `_previous_image()`, warn the user if `is_preview_active` is `True`:
```python
def _next_image(self):
    if self.is_preview_active:
        # Warn user they have an unsaved preview
        reply = QMessageBox.question(
            self, "Preview activo",
            "Hay un preview sin confirmar. ¿Descartar y continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
    self._clear_image_memory()
    ...
```

---

### WR-04: `QImage` constructed over potentially freed numpy buffer

**File:** `WatermarkRemove/ui/slideshow_viewer.py:741, 781, 787, 793`

At multiple locations the pattern is:
```python
q_image = QImage(self.working_image.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
```

`QImage` constructed this way does **not** copy the pixel data — it holds a raw pointer to the numpy array's buffer. If the numpy array is garbage-collected or modified (e.g., by another operation running in an event callback that modifies `self.working_image`) before `QPixmap.fromImage(q_image)` completes, the `QImage` reads freed or modified memory. This is a race condition in single-threaded Qt only if something in the call chain between `QImage(...)` and `QPixmap.fromImage(...)` re-enters the event loop (e.g., via a signal connection that triggers more processing). The same pattern repeats in `_apply_zoom()` (lines 779, 786, 793).

**Fix:** Either copy the data into the `QImage` by calling `.copy()` on the QImage after construction, or — simpler — keep a local reference to the numpy array alive for the duration:
```python
img_array = self.working_image  # local ref keeps array alive
q_image = QImage(img_array.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
pixmap = QPixmap.fromImage(q_image)
# img_array goes out of scope here, safely after pixmap is created
```
Or use `QImage.copy()`:
```python
q_image = QImage(self.working_image.data, ...).copy()
```

---

### WR-05: `_run_auto_detection` has a TODO comment blocking a user-visible loading state

**File:** `WatermarkRemove/ui/slideshow_viewer.py:1692`

```python
def _run_auto_detection(self):
    # TODO: Ventana emergente de "cargando modelo"
    """Corre YOLO sobre la imagen actual y arma la lista de detecciones."""
```

YOLO model loading (`detect_watermarks`) runs synchronously on the main thread. With no progress indicator, the UI freezes for several seconds every time auto mode is first activated or re-detection is triggered. This is a direct consequence of the unimplemented TODO. While a frozen UI is a UX issue, the actionable defect is that the TODO exists in a shipped code path — the docstring is also placed *after* the comment, which means it is not recognised as a proper docstring by Python's `__doc__` introspection.

**Fix:** At minimum, disable the re-detect button and show a status message during detection, and move the docstring before the TODO:
```python
def _run_auto_detection(self):
    """Corre YOLO sobre la imagen actual y arma la lista de detecciones."""
    # TODO: Show loading dialog/spinner while model loads
    self.auto_redetect_btn.setEnabled(False)
    try:
        ...
    finally:
        self.auto_redetect_btn.setEnabled(True)
```

---

## Info

### IN-01: `apply_settings` public API contract mentions `set_settings` but the method is named differently

**File:** `WatermarkRemove/ui/watermark_tab.py:234`

The CLAUDE.md constraint states `WatermarkTab.get_settings()` / `apply_settings()` must continue working. The file implements `set_settings()` (not `apply_settings()`). If external callers use `apply_settings()` they will get `AttributeError`. This may be a pre-existing naming inconsistency (not introduced by this phase), but it should be flagged as the phase touches this file.

**Fix:** Add an alias for backward compatibility:
```python
apply_settings = set_settings
```

---

### IN-02: `_update_counts_label` imports `json` inline on every call

**File:** `WatermarkRemove/ui/slideshow_viewer.py:117`

```python
import json as _json
```

This import runs every time the label is updated (called from `__init__`, `_accept_preview`, `_accept_auto_detections`, and `_reset_current_image`). Python caches module imports so there is no real overhead, but the inline import is a style inconsistency — `json` should be at the top of the file with the other standard library imports.

**Fix:** Move `import json` to the top-level imports section.

---

### IN-03: Hardcoded test path in `__main__` block

**File:** `WatermarkRemove/ui/slideshow_viewer.py:2028`

```python
test_folder = r"C:\Users\Felix\Downloads\Image Picka\32 urek"
```

A developer-specific absolute path is hardcoded in the `__main__` guard. This will fail silently (the SlideshowViewer will open with an empty image list) on any other machine.

**Fix:** Use a command-line argument or prompt the user for the path:
```python
import sys
test_folder = sys.argv[1] if len(sys.argv) > 1 else ""
```

---

### IN-04: `_accept_auto_detections` does not reset `auto_preview_image` to `None` symmetrically

**File:** `WatermarkRemove/ui/slideshow_viewer.py:1881-1884`

After a successful auto-accept, `detected_marks` and `detections_list` are cleared, but `self.auto_preview_image` is set to `None` and `_apply_zoom()` is called. However, `self.auto_mode_enabled` remains `True`, so `_apply_zoom()` at line 783 will enter the `elif self.auto_mode_enabled and self.auto_preview_image is not None:` branch — which is now `None`, so it falls through to `self.working_image`. This is functionally correct but fragile: a future change that checks `auto_preview_image is not None` after accept might produce unexpected behaviour. The implicit ordering dependency between `auto_preview_image = None` and the `_apply_zoom()` call is a latent hazard.

**Fix:** No immediate code change required, but add a comment explaining that `auto_preview_image` must be set to `None` before `_apply_zoom()` is called to avoid showing stale preview data.

---

_Reviewed: 2026-05-26T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
