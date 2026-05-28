---
phase: 03-logic-widget-separation
reviewed: 2026-05-27T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - WatermarkRemove/services/__init__.py
  - WatermarkRemove/services/context_menu_service.py
  - WatermarkRemove/services/folder_scan_service.py
  - WatermarkRemove/services/position_editor_service.py
  - WatermarkRemove/services/wm_positions_persistence.py
  - WatermarkRemove/ui/image_viewer.py
  - WatermarkRemove/ui/position_editor.py
  - WatermarkRemove/ui/watermark_tab.py
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-05-27
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

Revisión de los 8 archivos producidos en la Wave 0 de la Phase 3. La separación lógica servicios/widgets es estructuralmente correcta y las delegaciones ARCH-02 están bien aplicadas. Sin embargo se encontraron dos blockers: un cálculo de `sys.path` incorrecto en `context_menu_service.py` que añade el directorio equivocado (el padre del repo en vez del repo root) y un path relativo no canonicalizado en `wm_positions_persistence.py` que puede dirigir el JSON a un directorio incorrecto. Además hay cinco warnings relacionados con manejo de errores incompleto, un anti-patrón Qt en `ZoomableImageLabel`, y rutas de prueba hardcodeadas que deben eliminarse.

---

## Critical Issues

### CR-01: `context_menu_service.py` — `sys.path` injection apunta al directorio PADRE del repo

**File:** `WatermarkRemove/services/context_menu_service.py:24-27`

**Issue:**
El cálculo de `_repo_root` aplica `os.path.dirname` tres veces sobre `_current_dir`:

```python
_current_dir = os.path.abspath(os.path.dirname(__file__))
# _current_dir = <repo_root>/WatermarkRemove/services/

_repo_root = os.path.dirname(os.path.dirname(os.path.dirname(_current_dir)))
# dirname 1: <repo_root>/WatermarkRemove/
# dirname 2: <repo_root>/
# dirname 3: <parent_of_repo_root>/   ← WRONG
```

El directorio inyectado es el *padre* del repositorio, no el repo root. `import register_context_menu` (línea 80) funciona en la práctica solo porque otros módulos (`image_viewer.py`, `position_editor.py`, `watermark_tab.py`) ya añadieron `<repo_root>` a `sys.path` antes de que se ejecute `toggle()`. Si `ContextMenuService.toggle()` se invoca en un contexto donde esos módulos aún no se importaron (tests unitarios, contexto de consola, etc.), el import falla con `ModuleNotFoundError`.

**Fix:**
Usar dos niveles de `dirname` (igual que todos los demás servicios del mismo paquete):

```python
_current_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.dirname(os.path.dirname(_current_dir))
# dirname 1: <repo_root>/WatermarkRemove/
# dirname 2: <repo_root>/   ← correcto
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)
```

---

### CR-02: `wm_positions_persistence.py` — `__file__` no canonicalizado puede resolver a CWD

**File:** `WatermarkRemove/services/wm_positions_persistence.py:74`

**Issue:**
La ruta al JSON se construye directamente sobre `__file__` sin `os.path.abspath()`:

```python
self._json_path = (
    Path(os.path.dirname(os.path.dirname(__file__))) / 'wm_positions.json'
)
```

Cuando Python importa un módulo con un path relativo (e.g., `python -m` desde un directorio distinto o en ciertos setups de packaging), `__file__` puede ser una cadena relativa como `WatermarkRemove/services/wm_positions_persistence.py`. En ese caso `os.path.dirname(os.path.dirname(__file__))` devuelve `''` o un path relativo, y `Path('') / 'wm_positions.json'` resuelve contra el CWD del proceso, no contra `WatermarkRemove/`. El JSON de posiciones se crea en el directorio incorrecto sin advertencia.

Contraste con `position_editor_service.py` línea 25 y `context_menu_service.py` línea 24, que ambos usan `os.path.abspath(os.path.dirname(__file__))` correctamente.

**Fix:**
```python
self._json_path = (
    Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__)))) / 'wm_positions.json'
)
```

---

## Warnings

### WR-01: `position_editor_service.py` — `build_preview_pixmap` asume imagen BGR de 3 canales; falla silencioso con BGRA

**File:** `WatermarkRemove/services/position_editor_service.py:109-110`

**Issue:**
La línea:
```python
result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
h, w, _ = result_rgb.shape
```
usa `COLOR_BGR2RGB` (conversión de 3 canales) y desempaqueta `h, w, _` asumiendo exactamente 3 canales. Si la imagen de entrada tiene canal alfa (BGRA, lo que `load_images_cv2` puede devolver al usar `cv2.IMREAD_UNCHANGED`), `cv2.cvtColor` con `COLOR_BGR2RGB` lanzará un error de OpenCV en tiempo de ejecución. El desempaquetado `h, w, _` tampoco fallaría porque `result_img` puede ser BGRA (4 canales), pero `QImage.Format_RGB888` esperaría exactamente 3 bytes por pixel.

Además, `QImage` recibe `result_rgb.data` que es un buffer memory-view; si `result_rgb` es un array temporal que se libera antes de que `QPixmap.fromImage` complete la copia, hay un posible use-after-free del buffer (aunque en la práctica CPython lo mantiene vivo por el GC, no está garantizado).

**Fix:**
Normalizar a BGR antes de convertir:
```python
# Asegurar 3 canales antes de convertir
if result_img.shape[2] == 4:
    result_img = cv2.cvtColor(result_img, cv2.COLOR_BGRA2BGR)
result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
h, w, ch = result_rgb.shape
q_image = QImage(result_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
# Forzar copia del buffer para evitar dependencia del array numpy
return QPixmap.fromImage(q_image.copy())
```

---

### WR-02: `position_editor.py` — `_check_ready` dispara carga de imagen sin verificar éxito; error de `load_image` queda silenciado

**File:** `WatermarkRemove/ui/position_editor.py:430-443`

**Issue:**
```python
def _check_ready(self):
    ready = (...)
    if ready:
        self.btn_save.setEnabled(ready)
        self._load_current_image()      # puede fallar con ValueError
        self._load_current_watermark()  # puede fallar con ValueError
        self._update_preview()
```
`_load_current_image` y `_load_current_watermark` llaman a `self.service.load_image(path)` sin ningún `try/except`. Si la imagen está corrupta o es inaccesible, el `ValueError` propagado por `load_images_cv2` no es capturado. La excepción sube hasta el slot Qt que la llama (un `QComboBox.currentIndexChanged` o `QFileDialog` callback), donde Qt la suprime silenciosamente. El resultado: `self.current_image` y `self.current_watermark` permanecen en su valor anterior (o `None`), el botón "Guardar y Siguiente" queda habilitado, y la siguiente llamada a `_update_preview` muestra datos stale sin que el usuario sepa que hubo un error.

**Fix:**
```python
def _load_current_image(self):
    if not self.image_files or self.current_image_index >= len(self.image_files):
        return
    image_path = self.image_files[self.current_image_index]
    try:
        self.current_image = self.service.load_image(image_path)
    except (ValueError, OSError) as e:
        self.current_image = None
        self.image_label.setText(f"Error cargando imagen: {e}")
```
Aplicar el mismo patrón en `_load_current_watermark`.

---

### WR-03: `watermark_tab.py` — `_update_context_menu_btn` se llama durante `__init__` sin guard de plataforma; crash en non-Windows

**File:** `WatermarkRemove/ui/watermark_tab.py:71`

**Issue:**
`_setup_ui` llama a `self._update_context_menu_btn()` incondicionalmente en la construcción del widget. Ese método invoca `context_menu_service.is_registered()`, que importa `winreg` en tiempo de ejecución. En cualquier sistema que no sea Windows (Linux, macOS) o en entornos de CI/test que ejecuten el código en plataformas Unix, el widget falla con `ModuleNotFoundError: No module named 'winreg'` al construirse, impidiendo cualquier prueba del tab.

**Fix:**
```python
def _update_context_menu_btn(self):
    import sys
    if sys.platform != 'win32':
        self.context_menu_btn.setVisible(False)
        return
    if context_menu_service.is_registered():
        self.context_menu_btn.setText("📂 Desregistrar menú contextual")
    else:
        self.context_menu_btn.setText("📂 Registrar menú contextual")
```
Aplicar el mismo guard en `_toggle_context_menu`.

---

### WR-04: `position_editor.py` — `ZoomableImageLabel` crea un `QWidget()` temporal para acceder a `SizePolicy`

**File:** `WatermarkRemove/ui/position_editor.py:38-41`

**Issue:**
```python
self.setSizePolicy(
    QWidget().sizePolicy().Policy.Expanding,
    QWidget().sizePolicy().Policy.Expanding
)
```
Se instancian dos objetos `QWidget` temporales solo para navegar hasta `QSizePolicy.Policy.Expanding`. Los objetos temporales de Qt sin padre en el heap pueden causar advertencias de acceso después de liberación en algunas versiones de PySide6 si el GC los destruye antes de que Qt termine de procesarlos. Es además un anti-patrón que confunde al lector.

**Fix:**
```python
from PySide6.QtWidgets import QSizePolicy
self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
```

---

### WR-05: `folder_scan_service.py` — `scan_subfolders` puede lanzar `PermissionError` no manejada

**File:** `WatermarkRemove/services/folder_scan_service.py:80`

**Issue:**
```python
def scan_subfolders(base: Path) -> list[Path]:
    folders = [f for f in base.iterdir() if f.is_dir()]
```
`base.iterdir()` puede lanzar `PermissionError` o `OSError` si el usuario no tiene permisos de lectura sobre `base`. A diferencia de `scan_images`, la docstring no documenta qué excepciones pueden propagarse. El caller (`PositionEditor._load_watermark_folders`) tampoco tiene try/except, por lo que el error se pierde en el slot Qt. El combo de carpetas queda vacío sin feedback al usuario.

**Fix:**
```python
def scan_subfolders(base: Path) -> list[Path]:
    """...
    Raises:
        PermissionError: si el sistema no permite listar el directorio.
        OSError: si el path no es accesible.
    """
    folders = [f for f in base.iterdir() if f.is_dir()]
    folders.sort(reverse=True)
    return folders
```
Y en `PositionEditor._load_watermark_folders`:
```python
try:
    folders = scan_subfolders(self.marcas_base_path)
except OSError as e:
    self.watermark_folder_combo.addItem(f"Error: {e}")
    return
```

---

## Info

### IN-01: `image_viewer.py` — Ruta de prueba hardcodeada en bloque `__main__`

**File:** `WatermarkRemove/ui/image_viewer.py:247`

**Issue:**
```python
test_folder = r"C:\Users\Felix\Downloads\Image Picka\32 urek"
```
Ruta absoluta personal hardcodeada. No bloquea producción (bloque `__main__`), pero debe eliminarse o reemplazarse por un selector de carpeta antes de cualquier entrega o revisión pública.

**Fix:** Usar `QFileDialog.getExistingDirectory(None, "Seleccionar carpeta de prueba")` o eliminar el bloque `__main__` por completo.

---

### IN-02: `watermark_tab.py` — TODO inline en código de producción

**File:** `WatermarkRemove/ui/watermark_tab.py:100-102`

**Issue:**
```python
def _open_image_viewer(self):
    # TODO: En lugar de mostrar todas las imagenes, activar 
    # unicamente cuando hay imagenes que puedan generar errores
```
Comentario TODO sin issue tracker asociado. Además está ubicado *antes* del docstring del método, lo que invierte el orden convencional.

**Fix:** Crear issue en el backlog, eliminar el comentario inline o moverlo al docstring con formato `:todo:` / nota explícita.

---

### IN-03: `services/__init__.py` — Singletons creados en tiempo de importación pueden fallar silenciosamente en non-Windows

**File:** `WatermarkRemove/services/__init__.py:18`

**Issue:**
```python
context_menu_service = ContextMenuService()
```
La instancia se crea en tiempo de importación del paquete `services`. `ContextMenuService.__init__` no ejecuta código de plataforma, por lo que esto es seguro — pero cualquier consumidor que importe `from WatermarkRemove.services import context_menu_service` obtiene un objeto que explotará en `is_registered()` / `toggle()` en non-Windows sin advertencia. El patrón es aceptable para una app exclusivamente Windows, pero merece una nota.

**Fix:** Añadir un comentario de advertencia o una propiedad lazy que retorne `None` en non-Windows, evitando confusión en entornos CI.

---

### IN-04: `position_editor.py` — `_connect_signals` vacío heredado en `WatermarkTab`

**File:** `WatermarkRemove/ui/watermark_tab.py:95-97`

**Issue:**
```python
def _connect_signals(self):
    """Conecta las señales de los widgets"""
    pass
```
Método vacío (`pass`) llamado desde `_setup_ui`. Si no hay señales que conectar, el método no aporta nada y constituye dead code. Si es un hook intencional para subclases, debe documentarse como tal.

**Fix:** Eliminar el método y su llamada en `_setup_ui`, o añadir un docstring que explique que es un extension point.

---

_Reviewed: 2026-05-27_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
