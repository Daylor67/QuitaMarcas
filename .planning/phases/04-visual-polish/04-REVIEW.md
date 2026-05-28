---
phase: 04-visual-polish
reviewed: 2026-05-28T13:34:12Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - WatermarkRemove/services/wm_persistence.py
  - WatermarkRemove/ui/components/navigation_controller.py
  - WatermarkRemove/ui/components/training_data_collector.py
  - WatermarkRemove/ui/components/watermark_processor.py
  - WatermarkRemove/ui/slideshow_viewer.py
  - gui/stylesheet.py
findings:
  critical: 3
  warning: 7
  info: 4
  total: 14
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-05-28T13:34:12Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Se revisaron los 6 archivos de la fase de pulido visual (Phase 4). La refactorización estructural (compositor puro, separación de componentes) es sólida, pero se encontraron 3 defectos críticos que producen comportamientos incorrectos observables: datos perdidos silenciosamente al aceptar el modo manual sin output folder, navegación que avanza durante un preview activo (doble trigger), y el `wm_dir_root` nunca usado que apunta a un directorio incorrecto. Adicionalmente se detectaron 7 warnings de calidad que incluyen fugas de estado entre imágenes, lógica de auto-detección sin `request_redraw` al limpiar, y duplicidad de conexiones de señal.

---

## Critical Issues

### CR-01: `_accept_preview` guarda silenciosamente nada si `output_folder_request` es asíncrono

**File:** `WatermarkRemove/ui/components/watermark_processor.py:1210-1226`

**Issue:** En `_accept_preview`, si `self._output_folder` es `None`, se emite `output_folder_request` (una señal Qt). La creación real del folder ocurre en `NavigationController._create_output_folder`, que se conecta síncronamente como slot directo — pero la línea siguiente (`if self._output_folder is not None: guardar(...)`) se evalúa *justo después de emitir*, antes de que el slot actualice `self._output_folder` en el processor (el slot actualiza `navigation.output_folder`, y el processor actualiza su cache `_output_folder` solo cuando recibe `output_folder_ready` via `on_output_folder_ready`). Con Qt's `DirectConnection` el orden debería funcionar si todo está en el mismo thread, pero `_output_folder` en el processor solo se actualiza cuando `navigation.output_folder_ready` es emitida *desde dentro de `_create_output_folder`* — y esa señal está conectada a `processor.on_output_folder_ready` en `_wire_signals`. En la práctica, si `_output_folder` seguía siendo `None` después del emit (p.ej. si la señal fue `QueuedConnection` o si el folder ya existía sin emitir `output_folder_ready`), la imagen se procesa con `remove_watermark` pero **no se guarda a disco** y el usuario no ve ningún error — los cambios se pierden sin aviso.

**Fix:**
```python
def _accept_preview(self):
    if not self._preview_active or self.preview_image is None:
        return
    try:
        current_file = self._current_file
        if self._output_folder is None:
            self.output_folder_request.emit()
        # Abortar si aún no tenemos output_folder (la señal no lo creó sincrónicamente)
        if self._output_folder is None:
            self._log("❌ output_folder no disponible — no se puede guardar")
            return
        # ... resto del método
```

El mismo patrón faltante afecta a `_accept_auto_detections` (línea 1517-1518), que tampoco valida que `_output_folder` no sea `None` antes de llamar a `guardar` en la línea 1561.

---

### CR-02: `request_next` puede ejecutarse con un preview activo (navegación sin revert explícito)

**File:** `WatermarkRemove/ui/slideshow_viewer.py:123` + `WatermarkRemove/ui/components/navigation_controller.py:455`

**Issue:** El botón "Guardar y Siguiente" conecta `auto_accept_next_btn.clicked` a `navigation.request_next` directamente (slideshow_viewer.py línea 123). Si el usuario activa modo auto, acepta las marcas vía `_accept_auto_detections_and_next`, este método internamente llama `_accept_auto_detections()` y después el signal `.clicked` dispara `request_next()` en navigation. Hasta aquí es correcto. Sin embargo, la conexión también existe cuando el usuario está en **modo manual con preview activo**: si el usuario hace click en "Guardar y Siguiente" mientras `_preview_active = True` (p.ej. el botón no está oculto o el processor está en otro estado), `request_next()` en navigation llama `_clear_image_memory()` (que borra `working_image`) y luego llama `_save_current_image_as_is()` **sin el resultado del preview**, descartando silenciosamente la remoción parcial. El guard en `keyPressEvent` (línea 324) protege solo las teclas Space/Backspace, no los clics de botón.

Adicionalmente, `request_next` llama `_clear_image_memory()` **antes** de `_save_current_image_as_is()`, lo que borra `self.working_image` pero `_save_current_image_as_is` usa `load_images_cv2(current_file)` (carga desde disco), por lo que no lee la versión en memoria. Esto significa que si `working_image` tenía cambios en memoria aún no guardados, esos cambios se pierden — se guarda la versión de disco, no la de memoria.

**Fix:**
```python
# En slideshow_viewer._wire_signals, reemplazar la conexión directa por un slot guard:
# self.processor.auto_accept_next_btn.clicked.connect(self.navigation.request_next)
# por:
self.processor.auto_accept_next_btn.clicked.connect(self._on_save_and_next)

def _on_save_and_next(self):
    """Guard: solo avanza si no hay preview manual activo."""
    if self.processor.is_preview_active():
        self._log("⚠️ Acepta o revierte el preview antes de avanzar")
        return
    self.navigation.request_next()
```

---

### CR-03: Variable de módulo `wm_dir_root` incorrecta y nunca usada

**File:** `WatermarkRemove/ui/components/navigation_controller.py:36`

**Issue:** La variable de módulo `wm_dir_root` se define como:
```python
wm_dir_root = os.path.dirname(os.path.dirname(__file__))
```
El comentario dice `# WatermarkRemove/ui — usar dirname extra para WatermarkRemove/`, lo que **admite explícitamente** que el valor calculado es `WatermarkRemove/ui/` (le falta un `dirname` más para llegar a `WatermarkRemove/`). La variable nunca se usa en el módulo (ninguna referencia posterior). Aunque actualmente no causa un crash porque no se usa, es una variable de módulo con nombre engañoso que apunta al directorio equivocado y podría ser usada en el futuro causando errores de path difíciles de trazar.

**Fix:**
```python
# Eliminar la línea o corregir si se planea usar:
# wm_dir_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))  # WatermarkRemove/
# Si no se va a usar, eliminar completamente.
```

---

## Warnings

### WR-01: `_save_current_image_as_is` guarda la imagen desde disco, no desde memoria

**File:** `WatermarkRemove/ui/components/navigation_controller.py:483-504`

**Issue:** Al avanzar con `request_next`, si la imagen no fue procesada se llama `_save_current_image_as_is`. Este método carga la imagen con `load_images_cv2(current_file)` en lugar de usar `self.working_image`. Si el processor había aplicado cambios a `working_image` en memoria (p.ej. vía `on_image_processed`) pero el processor no actualizó el navigation antes del avance, se guarda la versión de disco en vez de la versión modificada.

**Fix:**
```python
def _save_current_image_as_is(self):
    if not self.output_folder or not self.image_files:
        return
    try:
        current_file = self.image_files[self.current_index]
        # Preferir working_image en memoria; solo ir a disco como fallback
        image = self.working_image if self.working_image is not None else load_images_cv2(current_file)
        if image is None:
            self._log(f"⚠️ Error cargando imagen: {current_file.name}")
            return
        guardar(current_file, image, self.output_folder)
        self.processed_images.add(self.current_index)
    except Exception as e:
        self._log(f"❌ Error guardando imagen: {e}")
```

---

### WR-02: `set_mode(0)` (desactivar auto) no limpia `detected_marks` ni `preview_changed`

**File:** `WatermarkRemove/ui/components/watermark_processor.py:1621-1627`

**Issue:** `set_mode(0)` (modo Selección) solo pone `auto_mode_enabled = False` pero no limpia `detected_marks`, `auto_preview_image`, ni emite `preview_changed(None)`. Esto difiere de `_toggle_auto_mode` (líneas 1368-1375) que sí limpia todo. Cuando el usuario alterna de Automático a Selección via el QButtonGroup, el preview del auto-mode queda visible en la imagen y `detected_marks` conserva el estado anterior.

**Fix:**
```python
elif mode_index == 0:
    if self.crop_mode_enabled:
        self.crop_mode_enabled = False
        self.request_redraw.emit()
    if self.auto_mode_enabled:
        self.auto_mode_enabled = False
        # Limpiar estado de auto-detección (réplica de _toggle_auto_mode)
        self.detected_marks = []
        self.selected_mark_index = -1
        self.auto_preview_image = None
        self.detections_list.clear()
        self.preview_changed.emit(None)
        self.request_redraw.emit()
```

---

### WR-03: Doble disparo de `request_redraw` al navegar en modo crop

**File:** `WatermarkRemove/ui/components/watermark_processor.py:1628-1633`

**Issue:** `set_mode(1)` (Recorte) llama `self.request_redraw.emit()` siempre (línea 1633), incluso si el modo recorte ya estaba activo. Esto provoca un re-render redundante en cada click accidental del botón "Recorte". Menor impacto de rendimiento, pero también podría causar parpadeo en imágenes grandes.

**Fix:** Solo emitir cuando el estado cambia:
```python
elif mode_index == 1:
    if self.auto_mode_enabled:
        self.auto_mode_enabled = False
    if not self.crop_mode_enabled:
        self.crop_mode_enabled = True
        self.request_redraw.emit()
```

---

### WR-04: `on_image_processed` en navigation actualiza `working_image` con cualquier emit de `image_processed`

**File:** `WatermarkRemove/ui/components/navigation_controller.py:525-530`

**Issue:** El slot `on_image_processed` en `NavigationController` actualiza incondicionalmente `self.working_image` con el argumento recibido. `image_processed` se emite también por `_apply_crop` con `working_image = new_working` (resultado del crop) y por `_process_watermark_at_position` (result_image). Esto es correcto. Sin embargo, `_accept_auto_detections` emite `image_processed` **dentro del bucle**, una vez por cada marca detectada, pasando el `result` acumulativo en cada iteración. Esto hace que `navigation.on_image_processed` se llame N veces, actualizando `working_image` N veces y llamando `_apply_zoom()` N veces — N renders por cada guardado. No es incorrecto per se, pero si hay 5 marcas, hay 5 re-renders completos incluyendo conversión BGR→RGB, pixmap scaling y decoración. El resultado final es el mismo pero el re-render intermedio debería omitirse.

**Fix:** En `_accept_auto_detections`, emitir `image_processed` solo una vez al final, fuera del bucle:
```python
# Después del bucle, emitir una sola vez con el resultado final
if applied > 0 and last_emitted is not None:
    # Actualizar el último result emitido con el resultado final acumulado
    last_emitted = (current_file, result, ..., base)
    self.image_processed.emit(*last_emitted)
```

---

### WR-05: `fake_current_dir` en `on_image_reset` es frágil — acoplamiento implícito con `training_collector.py`

**File:** `WatermarkRemove/ui/components/training_data_collector.py:181-185`

**Issue:** El método `on_image_reset` construye `fake_current_dir = <WatermarkRemove>/ui` deliberadamente para engañar a `remove_training_sample` que internamente hace `Path(os.path.dirname(current_dir))` para encontrar `training_data.json`. Esta es una dependencia implícita frágil: si `remove_training_sample` en `training_collector.py` cambia su lógica de resolución de path (algo probable dado que está marcado como out-of-scope), el `fake_current_dir` dejará de apuntar al archivo correcto sin ningún error de compilación. El componente ya conoce `self._training_json` (calculado correctamente). La función `remove_training_sample` debería aceptar el path directamente, o el componente debería replicar la lógica mínima.

**Fix:** Alternativa sin modificar `training_collector.py`:
```python
def on_image_reset(self, file_path):
    try:
        import json as _json
        if self._training_json.exists():
            data = _json.loads(self._training_json.read_text(encoding='utf-8'))
            if isinstance(data, list):
                filtered = [e for e in data if e.get('image_name') != Path(file_path).name]
                removed = len(data) - len(filtered)
                if removed:
                    self._training_json.write_text(
                        _json.dumps(filtered, ensure_ascii=False, indent=2),
                        encoding='utf-8',
                    )
                    self._log(f"🧹 Eliminadas {removed} entrada(s) de entrenamiento")
    except Exception as e:
        self._log(f"⚠️ Error en remove_training_sample: {e}")
    finally:
        self._update_counts_label()
```

---

### WR-06: `_accept_preview` puede calcular posición desde `current_event_position` que es `None`

**File:** `WatermarkRemove/ui/components/watermark_processor.py:1205-1213`

**Issue:** La guardia inicial es `if not self._preview_active or self.preview_image is None`. Sin embargo, en teoría `_preview_active` puede ser `True` mientras `current_event_position` es `None` si la máquina de estados queda en un estado inconsistente (p.ej. excepción parcial en `_remove_watermark_preview` entre la línea 1183 y 1167). La línea 1213 hace `best_x, best_y = self.current_event_position` sin verificar que no sea `None`, causando `TypeError: cannot unpack non-iterable NoneType object` dentro del `try/except` que lo registraría silenciosamente.

**Fix:**
```python
if self.current_event_position is None or self.current_event_watermark is None:
    self._log("❌ Estado de evento inconsistente — revirtiendo")
    self._revert_preview()
    return
best_x, best_y = self.current_event_position
```

---

### WR-07: `wm_persistence` importado en `navigation_controller.py` pero nunca usado

**File:** `WatermarkRemove/ui/components/navigation_controller.py:42`

**Issue:** La línea `from WatermarkRemove.services import wm_persistence  # noqa: F401` importa el módulo con `noqa` para suprimir el warning de "unused import". El comentario dice `(Plan 02 lo usará desde el processor)`. El processor (ya implementado) usa `wm_persistence` directamente desde sus propias importaciones — no a través del navigation. La importación en navigation_controller es código muerto que añade acoplamiento innecesario y ejecuta la inicialización del servicio de persistencia en el contexto del navigation.

**Fix:** Eliminar la línea 42 del navigation_controller.py.

---

## Info

### IN-01: Hardcoded test path en el bloque `__main__` de `slideshow_viewer.py`

**File:** `WatermarkRemove/ui/slideshow_viewer.py:368`

**Issue:** El bloque `if __name__ == "__main__"` contiene una ruta absoluta hardcodeada `r"C:\Users\Felix\Downloads\Image Picka\32 urek"`. Funciona solo en la máquina del desarrollador.

**Fix:** Usar `sys.argv[1]` con fallback o un directorio relativo de ejemplo:
```python
test_folder = sys.argv[1] if len(sys.argv) > 1 else "."
```

---

### IN-02: `_update_counts_label` importa `json` de forma lazy en cada llamada

**File:** `WatermarkRemove/ui/components/training_data_collector.py:103`

**Issue:** `import json as _json` dentro del cuerpo del método se ejecuta en cada refresh de counts. Python cachea los módulos importados, por lo que no es un error funcional, pero es un patrón inconsistente con el resto del codebase (que usa imports a nivel de módulo). El alias `_json` intenta evitar colisión con el nombre `json` del scope, pero no existe tal variable en el scope.

**Fix:** Mover a imports de nivel de módulo al tope del archivo.

---

### IN-03: `gui/stylesheet.py` mezcla `WM_STYLE_SHEET` específico de `WatermarkRemove` con estilos globales

**File:** `gui/stylesheet.py:181-303`

**Issue:** `WM_STYLE_SHEET` está definido en `gui/stylesheet.py` (módulo global de la app) pero contiene estilos muy específicos del módulo `WatermarkRemove` (object names `wm-*`). `load_styling()` los concatena siempre, aplicando reglas WM a toda la aplicación aunque el `SlideshowViewer` no esté abierto. Esto no causa un error visible hoy (los selectors `#wm-*` son suficientemente específicos), pero contamina el espacio de nombres del stylesheet global.

**Fix:** Definir `WM_STYLE_SHEET` en `WatermarkRemove/ui/stylesheet.py` y aplicarlo solo en `SlideshowViewer.__init__` vía `self.setStyleSheet(WM_STYLE_SHEET)`.

---

### IN-04: `_check_yolo_availability` usa `import os` redundante dentro de un método

**File:** `WatermarkRemove/ui/slideshow_viewer.py:255`

**Issue:** `_check_yolo_availability` hace `import os` y `from pathlib import Path` dentro del cuerpo del método, pero `os` y `Path` ya están importados a nivel de módulo en las líneas 19-20.

**Fix:** Eliminar los imports inline del método (líneas 255-256).

---

_Reviewed: 2026-05-28T13:34:12Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
