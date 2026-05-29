# Phase 3: Logic/Widget Separation - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 6 (3 widgets to refactor + 3 services to create)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `WatermarkRemove/services/position_editor_service.py` (NEW) | service (domain) | transform + file-I/O + CRUD | `WatermarkRemove/ui/components/watermark_processor.py` (align/remove/load + cv2→QPixmap logic) | role-match (extraction source) |
| `WatermarkRemove/services/folder_scan_service.py` (NEW) | service (domain) | file-I/O / transform | `NavigationController._load_image_list` + `ImageViewer._load_images` (scan + ext filter + natsorted) | exact (same scan pattern x2) |
| `WatermarkRemove/services/context_menu_service.py` (NEW) | service (OS integration) | event-driven (OS state toggle) | `register_context_menu.py` (register/unregister) + `WatermarkTab._is_context_menu_registered/_toggle_context_menu` | role-match (extraction source) |
| `WatermarkRemove/services/wm_positions_persistence` (NEW or extend `wm_persistence`) | service (persistence) | CRUD (nested JSON) | `WatermarkRemove/services/wm_persistence.py` (Phase 1) | role-match (different file/format) |
| `WatermarkRemove/ui/position_editor.py` (MODIFY) | component (QDialog) | request-response (UI coordination) | `WatermarkProcessor` (widget that delegates domain to imports) + `NavigationController` | exact |
| `WatermarkRemove/ui/image_viewer.py` (MODIFY) | component (QDialog) | request-response (UI coordination) | `NavigationController` (scan delegated, thumbnails/render local) | role-match |
| `WatermarkRemove/ui/watermark_tab.py` (MODIFY) | coordinator (QWidget) | request-response (signal/slot wiring) | `SlideshowViewer` (composer puro — instancia + wire, no domain) | role-match |
| `WatermarkRemove/services/__init__.py` (MODIFY) | config (barrel) | — | existing barrel (3 lines) | exact |

## Pattern Assignments

### `WatermarkRemove/services/position_editor_service.py` (NEW — service, transform + file-I/O + CRUD)

**Analog:** `WatermarkRemove/ui/components/watermark_processor.py` — extract the domain calls (`align_watermark`, `remove_watermark`, `load_images_cv2`, cv2→QPixmap) currently inline in `position_editor.py`.

**Imports pattern** — replicate `watermark_processor.py` lines 37-67 (path bootstrap + domain imports). NOTE: `services/` is ONE level under `WatermarkRemove/`, so the bootstrap differs from `components/` (TWO levels). For a service in `services/`, the package root is reached with `os.path.dirname(os.path.dirname(__file__))` (services → WatermarkRemove → repo? — see Pitfall path note below). The domain import block to copy verbatim:
```python
from WatermarkRemove import align_watermark, remove_watermark
from WatermarkRemove.wm_remove import load_images_cv2, guardar, find_wm, quick_align_preview
```
*(Source: `watermark_processor.py:65-66`)*

**Core domain pattern to EXTRACT FROM** `position_editor.py:474-507` (`_update_preview` — currently inline in the widget):
```python
# CURRENT (inline domain in widget — must move to service):
img_copy = self.current_image.copy()
x, y = align_watermark(
    img_copy, self.current_watermark,
    offset_x=self.offset_x, offset_y=self.offset_y,
    side_x=self.side_x, side_y=self.side_y
)
result_img = remove_watermark(img_copy, self.current_watermark, x, y)
result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
height, width, channel = result_rgb.shape
bytes_per_line = 3 * width
q_image = QImage(result_rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
pixmap = QPixmap.fromImage(q_image)
```

**Target shape (RESEARCH Pattern 1, lines 158-168)** — service method returns the pixmap; widget only calls `set_image`:
```python
# Service method (build_preview_pixmap):
def build_preview_pixmap(self, image, watermark, *, offset_x, offset_y, side_x, side_y) -> QPixmap:
    img_copy = image.copy()
    x, y = align_watermark(img_copy, watermark, offset_x=offset_x, offset_y=offset_y,
                           side_x=side_x, side_y=side_y)
    result_img = remove_watermark(img_copy, watermark, x, y)
    result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
    h, w, _ = result_rgb.shape
    q_image = QImage(result_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(q_image)
```
> Open Question #1 (RESEARCH lines 296-299): service may return QPixmap (convenience, recommended — no automated tests) OR return ndarray and let widget convert. Decide in plan.

**Image-load pattern (cv2→array)** — `position_editor.py:444-460` (`_load_current_image`, `_load_current_watermark`). Move to service; **MUST use `load_images_cv2`, NEVER `cv2.imread`** (RESEARCH Pitfall 3 — non-ASCII path safety):
```python
self.current_image = load_images_cv2(str(image_path))   # position_editor.py:450 — preserve verbatim
```

**Error-handling pattern** — service raises/returns; widget wraps in try/except + shows error in label, exactly as `position_editor.py:479-506` does today (`except Exception as e: self.image_label.setText(f"❌ Error: {str(e)}")`). The processor analog uses `self._log(...)` for service-level errors (`watermark_processor.py:942-943`).

---

### `WatermarkRemove/services/folder_scan_service.py` (NEW — service, file-I/O)

**Analog:** Two identical scan+filter implementations exist — consolidate them.

**Source A** — `NavigationController._load_image_list` (`navigation_controller.py:234-247`):
```python
if self.folder_path.is_file():
    self.folder_path = self.folder_path.parent
for file in natsorted(self.folder_path.iterdir()):
    if file.is_file() and file.suffix.lower() in self.SUPPORTED_FORMATS:
        self.image_files.append(file)
```

**Source B** — `ImageViewer._load_images` (`image_viewer.py:94-101`) — same logic, slightly different `SUPPORTED_FORMATS` (includes `.psd`, `.psb`).

**Source C** — `PositionEditor._load_images` (`position_editor.py:401-412`) and `_load_watermark_folders` (`position_editor.py:374-387`, dir scan) and `_load_watermarks_into_combo` (`position_editor.py:414-427`, `.png` filter).

**Target shape** — pure functions taking a folder + extension tuple, returning a `natsorted` list:
```python
def scan_images(folder: Path, formats: tuple) -> list[Path]:
    if folder.is_file():
        folder = folder.parent
    return [f for f in natsorted(folder.iterdir())
            if f.is_file() and f.suffix.lower() in formats]

def scan_subfolders(base: Path) -> list[Path]:   # for marcas/ dir scan
    folders = [f for f in base.iterdir() if f.is_dir()]
    folders.sort(reverse=True)
    return folders
```
**Constraint:** preserve each widget's existing `SUPPORTED_FORMATS` tuple (they differ — viewer has `.psd/.psb`, editor/nav do not). Pass formats as a param; do NOT unify the tuples.

---

### `WatermarkRemove/services/context_menu_service.py` (NEW — service, OS integration)

**Analog:** `register_context_menu.py` (top-level module, `register()` / `unregister()` at lines 21, 35) + the detection logic currently in `watermark_tab.py:146-153`.

**Detection pattern to EXTRACT FROM** `watermark_tab.py:146-153`:
```python
def _is_context_menu_registered(self):
    try:
        import winreg
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\Directory\shell\SmartStitchWR")
        return True
    except FileNotFoundError:
        return False
```

**Toggle pattern to EXTRACT FROM** `watermark_tab.py:162-180` (the `winreg`/`register_context_menu` calls — but the `QMessageBox` UI feedback stays in the widget):
```python
import register_context_menu
if self._is_context_menu_registered():
    register_context_menu.unregister()
else:
    register_context_menu.register()
```

**Target shape (RESEARCH Pattern 3, lines 177-179)** — service exposes `is_registered() -> bool` and `toggle() -> bool` (returns new state); widget refreshes button text + shows QMessageBox:
```python
class ContextMenuService:
    KEY = r"Software\Classes\Directory\shell\SmartStitchWR"
    def is_registered(self) -> bool: ...   # winreg.OpenKey + FileNotFoundError guard
    def toggle(self) -> bool: ...          # register/unregister, returns new state
```
**Constraint (RESEARCH Runtime State line 208):** the registry key `HKEY_CURRENT_USER\Software\Classes\Directory\shell\SmartStitchWR` does NOT change — only the call-site moves. Preserve the `FileNotFoundError` guard verbatim.

---

### `WatermarkRemove/services/` wm_positions persistence (NEW or extend — service, CRUD nested JSON)

**Analog:** `WatermarkRemove/services/wm_persistence.py` (Phase 1, full file, 39 lines).

**Pattern to follow** (`wm_persistence.py:11-38`) — wrap `UtilJson` with domain method names, NO in-memory cache (each call reads/writes):
```python
class WmPersistenceService:
    def __init__(self):
        self._path = os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')
    def get_last_crop_pixels(self) -> int:
        return UtilJson(self._path).get('last_crop_pixels', 0) or 0
    def set_last_crop_pixels(self, value: int) -> None:
        UtilJson(self._path).set('last_crop_pixels', int(value))
```

**Domain logic to EXTRACT FROM** `position_editor.py:569-600` (`_save_to_json` — nested folder→marca→pos_N structure). The read-side analog is in `watermark_processor.py:601-632` (`_load_watermark_positions` — per-PNG + folder-level fallback). Move both behind the service:
```python
# WRITE (position_editor.py:580-596 — preserve nesting + key preservation verbatim):
positions_dict = {f'pos_{i}': p for i, p in enumerate(self.saved_positions, start=1)}
folder_data = json_file.get(watermark_folder_name, {}) or {}   # preserve existing keys
if save_by_watermark:
    folder_data[watermark_path.name] = positions_dict
else:
    for k, v in positions_dict.items():
        folder_data[k] = v
json_file.set(watermark_folder_name, folder_data)
```
**Constraint (RESEARCH Pitfall 4, Out of Scope):** do NOT change the `wm_positions.json` structure — only encapsulate access. The service must compute the path to `WatermarkRemove/wm_positions.json` from ITS OWN location: `services/` is one level under `WatermarkRemove/`, so `os.path.dirname(os.path.dirname(__file__))` reaches the repo root — verify the file lands at `WatermarkRemove/wm_positions.json` (same as today's `position_editor.py:576` which uses `os.path.dirname(current_dir)` from `ui/`).

---

### `WatermarkRemove/ui/position_editor.py` (MODIFY — component, request-response)

**Analog:** `WatermarkProcessor` (widget that imports + calls domain, keeps UI state) and `NavigationController` (widget that delegates scan/load, keeps render/zoom).

**What STAYS in the widget (presentation — RESEARCH Responsibility Map lines 31-32):**
- `ZoomableImageLabel` class (`position_editor.py:27-70`) — pure presentation
- All `_create_controls_panel` / `_create_image_panel` UI building (`position_editor.py:130-330`)
- `keyPressEvent`, `_on_zoom_changed`, spinbox/combo callbacks (UI state: `offset_x`, `side_x`, `current_image_index`)
- `_adjust_window_size` (`position_editor.py:508-535`) — window geometry is presentation
- `_save_and_next` navigation/index/zoom-reset/QMessageBox (`position_editor.py:544-567`) — BUT the accumulation + persist call moves to service (RESEARCH Pitfall 5)

**What MOVES to service:** `_update_preview` domain (lines 480-497), `_load_current_image`/`_load_current_watermark` (lines 444-460), `_load_images`/`_load_watermark_folders`/`_load_watermarks_into_combo` scan (lines 374-427), `_save_to_json` (lines 569-600).

**Target coordination pattern** — copy how `WatermarkProcessor` instantiates and calls (e.g. `_process_watermark_at_position` lines 896-905 calls `align_watermark`/`remove_watermark` then delegates persistence). The widget after refactor calls `self.service.build_preview_pixmap(...)` then `self.image_label.set_image(pixmap)` (RESEARCH lines 159-167).

**Pitfall 5 (lines 240-244):** `_save_and_next` mixes accumulation + nav + persist + feedback. Separate cleanly: service accumulates + persists at batch end; widget controls index/zoom/QMessageBox. Preserve "save only on last image" behavior + sample count in dialog.

---

### `WatermarkRemove/ui/image_viewer.py` (MODIFY — component, request-response)

**Analog:** `NavigationController` — scan delegated to a helper, render/thumbnails kept local.

**What MOVES to service:** only `_load_images` scan+filter (`image_viewer.py:93-101`) → `folder_scan_service.scan_images(folder, SUPPORTED_FORMATS)`.

**What STAYS (presentation — the bulk of the file):** `_setup_ui`, `_create_image_widget` thumbnail construction (lines 120-175), `_show_full_image` (lines 177-218), `_clear_grid`, the grid layout + counter label update. Per RESEARCH line 30: "construir thumbnails es presentación legítima."

**Counter update** stays in widget (`image_viewer.py:103`) — it reads `len(image_files)` returned by the service.

---

### `WatermarkRemove/ui/watermark_tab.py` (MODIFY — coordinator)

**Analog:** `SlideshowViewer` (`slideshow_viewer.py` — composer puro: instantiate components/services, wire, no domain inline). See `_wire_signals` (line 86) and the docstring (lines 1-15) describing the "instancia + cablea, no decide lógica" contract.

**What MOVES to services:**
- `_is_context_menu_registered` + `_update_context_menu_btn` + `_toggle_context_menu` winreg logic (`watermark_tab.py:146-180`) → `ContextMenuService`. The widget keeps the button + text refresh + `QMessageBox` (presentation).
- `_check_for_updates` (`watermark_tab.py:182-206`) — already delegates to `UpdateChecker`; per RESEARCH Open Question #2 (lines 301-304) + A5, extract the `try/except` + button-state orchestration only if strict ARCH-04 is desired. Confirm rigor in discuss.

**What STAYS (legitimate coordination):** `_open_image_viewer` / `_open_position_editor` (lines 98-144) just instantiate dialogs — legitimate coordination. `_get_main_window`, `log`.

**CRITICAL contract to preserve (RESEARCH Pitfalls 1-2, VERIFIED `gui/controller.py:16,76,317`):**
1. Constructor `WatermarkTab()` with no args (`controller.py:76`)
2. Public attribute `run_quita_marcas` (QCheckBox) accessed directly at `controller.py:317` — do NOT wrap in property or rename
3. Method `log(message)` (`watermark_tab.py:218-220`) — consumed by all 3 Phase 2 components via `watermark_tab.log`
4. `get_settings` / `set_settings` (`watermark_tab.py:222-242`) preserved; ADD alias `apply_settings = set_settings` (Pitfall 1 — constraint says `apply_settings`, real method is `set_settings`)

Verify `git diff gui/controller.py` is empty at phase end.

---

## Shared Patterns

### Logging toward the coordinator (`WatermarkTab.log`)
**Source:** `navigation_controller.py:120-125`, `watermark_processor.py:142-147`, `training_data_collector.py:89-94` (identical `_log` fallback).
**Apply to:** any new service/component that needs to log; the widget passes `watermark_tab` and the helper calls `watermark_tab.log` with `print` fallback.
```python
def _log(self, message: str):
    if self.watermark_tab and hasattr(self.watermark_tab, 'log'):
        self.watermark_tab.log(message)
    else:
        print(message)
```
> NOTE: `WatermarkTab.log()` MUST be preserved — the 3 Phase 2 components depend on it (RESEARCH line 270).

### Service barrel registration
**Source:** `WatermarkRemove/services/__init__.py` (full file):
```python
from .wm_persistence import WmPersistenceService
wm_persistence = WmPersistenceService()
__all__ = ['wm_persistence', 'WmPersistenceService']
```
**Apply to:** every new service — export the class and (if stateless-singleton like `wm_persistence`) a module-level instance. Consumers import via `from WatermarkRemove.services import wm_persistence` (see `watermark_processor.py:64`).

### Non-ASCII-safe image load
**Source:** `wm_remove.load_images_cv2` (used at `position_editor.py:450,459`, `navigation_controller.py:263`, `watermark_processor.py:776,891` etc.).
**Apply to:** ALL extracted image-load code — use `load_images_cv2`, NEVER `cv2.imread` (RESEARCH Pitfall 3, Security V5 line 374). `cv2.imread` returns None silently on non-ASCII paths.

### Defensive JSON access
**Source:** `wm_persistence.py:26` (`.get(key, default) or default`), `watermark_processor.py:614-629` (defensive `UtilJson(path).read()` + `.get(..., {}) or {}` + try/except), `training_data_collector.py:108-129` (try/except → "Sin datos aún" fallback).
**Apply to:** the wm_positions persistence service — preserve the defensive parse + existing-key preservation (`folder_data = json_file.get(name, {}) or {}`).

### blockSignals bracket during combo population
**Source:** `watermark_processor.py:495-523` (`_load_watermark_folders` — `blockSignals(True)` … populate … `blockSignals(False)` then manual fire).
**Apply to:** if `position_editor.py` combo population is touched during refactor, preserve any signal-suppression behavior (RESEARCH Pitfall 3). Note: current `position_editor.py:374-387` does NOT use blockSignals — do not introduce a behavior change.

## No Analog Found

None. Every file has a strong analog — Phase 2 established the exact Signal/Slot + service patterns this phase replicates, and Phase 1 established the persistence-service pattern.

## Metadata

**Analog search scope:** `WatermarkRemove/services/`, `WatermarkRemove/ui/`, `WatermarkRemove/ui/components/`, `WatermarkRemove/wm_remove.py`, repo-root `register_context_menu.py`, `gui/controller.py`.
**Files scanned:** 10 (3 targets + wm_persistence + 3 Phase-2 components + slideshow_viewer + register_context_menu + controller).
**Pattern extraction date:** 2026-05-27
