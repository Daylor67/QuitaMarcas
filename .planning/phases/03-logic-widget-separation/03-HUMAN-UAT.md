---
phase: 03-logic-widget-separation
type: uat
created: 2026-05-28
status: pending
---

# Phase 3 — UAT Checklist (Manual Verification)

> Validación humana del SC-4 de Phase 3 (ROADMAP §Phase 3): **flujo completo
> sin regresión observable** tras la extracción de lógica de dominio a servicios.
>
> El usuario debe completar este checklist sobre la app con código refactorizado
> **antes** de `/gsd-verify-work`. Patrón heredado de `02-HUMAN-UAT.md` (Phase 2).
>
> **Pre-condiciones:** Plans 03-01 (servicios), 03-02 (position_editor +
> image_viewer) y 03-03 (watermark_tab) deben estar mergeados antes de iniciar.

## Pre-requisites

- [ ] `python -m py_compile WatermarkRemove/services/*.py WatermarkRemove/ui/*.py` — sale 0
- [ ] Carpeta de test con 5+ imágenes (PNG/JPG/WEBP) preparada en disco
- [ ] Carpeta `WatermarkRemove/marcas/<alguna>/` con al menos 1 PNG de marca
- [ ] (Opcional) Carpeta con caracteres no-ASCII en el nombre o en el path
      (ej. `mañana_测试`) para validar `load_images_cv2` post-refactor
- [ ] `wm_positions.json` con al menos 1 carpeta+marca ya guardada (para validar
      preservación de claves existentes)
- [ ] Windows (necesario para Sección 3 — menú contextual)
- [ ] Acceso a internet (necesario para Sección 4 — buscar actualizaciones)

## Sección 1 — Editor de Posiciones (SC-4 / ARCH-02)

> **El editor manual de posiciones funciona idénticamente; toda la lógica de
> dominio (load, align, remove, persistir) vive en `PositionEditorService` +
> `folder_scan_service` + `WmPositionsPersistenceService`.**

- [ ] Abrir `python SmartStitchGUI.py`, ir a la pestaña **WatermarkRemove**
- [ ] Click en **"Editar posiciones de marca"** → se abre el `PositionEditor`
- [ ] Click en **"Cargar carpeta de imágenes"** → seleccionar carpeta de test;
      el label muestra el nombre y el contador `1 / N` aparece
- [ ] El combo **"Carpeta de marcas"** se puebla con las subcarpetas de
      `WatermarkRemove/marcas/` (orden reverse — más recientes primero)
- [ ] Seleccionar una carpeta de marcas → el combo **"Marca"** se puebla con
      los PNG de esa carpeta (orden `natsorted`)
- [ ] Seleccionar una marca específica → el preview aparece en el panel derecho
- [ ] Ajustar **offset X** y **offset Y** (spinboxes) → el preview se actualiza
      en cada cambio
- [ ] Cambiar los combos **lado X** y **lado Y** → el preview se actualiza
- [ ] Click en **"Guardar y Siguiente"** → avanza a la imagen 2; el contador
      se actualiza a `2 / N`; el zoom se resetea a 100%
- [ ] Repetir "Guardar y Siguiente" hasta la última imagen → al final aparece
      `QMessageBox` **"Completado"** con `Se guardaron N posiciones correctamente`
      (N debe ser el conteo correcto de imágenes)
- [ ] Cerrar el editor; reabrirlo; recargar la misma carpeta de imágenes + la
      misma carpeta/marca → confirmar que las posiciones guardadas siguen en
      `WatermarkRemove/wm_positions.json` y que claves anteriores
      (otras marcas en la misma carpeta) **NO** se perdieron
- [ ] (Edge case) Si la carpeta de imágenes tiene un nombre no-ASCII, las
      imágenes cargan correctamente (test de `load_images_cv2`)
- [ ] Tras refactor: `grep -vE '^\s*#' WatermarkRemove/ui/position_editor.py | grep -cE "align_watermark\(|remove_watermark\(|cv2\.|UtilJson\("` → **0 hits**

**PASS / FAIL:** ☐ PASS  ☐ FAIL — Detalle si FAIL: _____________________

## Sección 2 — Visor de Imágenes (SC-4 / ARCH-02)

> **El visor de carpetas de imágenes funciona idénticamente; el scan +
> filtrado de extensiones vive en `folder_scan_service.scan_images`.**

- [ ] Click en **"Ver Imágenes de Input"** (pestaña WatermarkRemove)
- [ ] Seleccionar una carpeta válida → el visor se abre
- [ ] El **grid de thumbnails** se renderiza con todas las imágenes
- [ ] El **contador de imágenes** muestra el total correcto
- [ ] Click en una thumbnail → se abre la vista completa de esa imagen
- [ ] Cerrar y reabrir el visor con una carpeta DIFERENTE → el grid se limpia
      y vuelve a poblar correctamente
- [ ] (Edge case) Carpeta con `.psd` o `.psb` → aparecen en el grid (el visor
      preserva esos formatos extendidos, distintos de los del editor)
- [ ] Tras refactor: `grep -vE '^\s*#' WatermarkRemove/ui/image_viewer.py | grep -cE "natsorted\("` → **0 hits**
      (el scan vive en el servicio; el widget solo consume la lista)

**PASS / FAIL:** ☐ PASS  ☐ FAIL — Detalle si FAIL: _____________________

## Sección 3 — Menú Contextual de Windows (SC-4 / ARCH-04)

> **El registro/desregistro del menú contextual de Windows funciona
> idénticamente; toda la lógica `winreg` + `register_context_menu` vive en
> `ContextMenuService`.**

- [ ] Click en el botón **"📂 Registrar menú contextual"** (estado inicial:
      no registrado)
- [ ] Aparece `QMessageBox` confirmando el registro
- [ ] El texto del botón cambia a **"📂 Desregistrar menú contextual"**
- [ ] Abrir el explorador de Windows, click derecho sobre una carpeta cualquiera
      → la entrada **"Abrir con SmartStitch WR"** aparece en el menú contextual
- [ ] Click esa entrada → se lanza SmartStitch con la carpeta como argumento
- [ ] Volver a la pestaña WatermarkRemove; click en **"📂 Desregistrar menú contextual"**
- [ ] Aparece `QMessageBox` confirmando la eliminación
- [ ] El texto del botón vuelve a **"📂 Registrar menú contextual"**
- [ ] Click derecho en el explorador → la entrada **YA NO** aparece
- [ ] (Edge case) Click en "Desregistrar" cuando ya está desregistrado (manual
      cleanup vía regedit, por ejemplo) → el botón se mantiene consistente,
      no crashea (guard `FileNotFoundError` preservado)
- [ ] Tras refactor: `grep -vE '^\s*#' WatermarkRemove/ui/watermark_tab.py | grep -cE "winreg\.|register_context_menu"` → **0 hits**

**PASS / FAIL:** ☐ PASS  ☐ FAIL — Detalle si FAIL: _____________________

## Sección 4 — Buscar Actualizaciones (SC-4)

> **El botón "Buscar Actualizaciones" funciona idénticamente; comportamiento
> conservado independientemente de si Plan 03-03 extrae o no `UpdateChecker`
> a un servicio (RESEARCH Open Q #2).**

- [ ] Click en el botón **"🔄 Buscar Actualizaciones"**
- [ ] El botón se deshabilita y muestra texto **"🔄 Buscando..."**
- [ ] Tras la respuesta:
      - Si HAY actualización → se abre el `UpdateDialog` con la nueva versión
        y release notes
      - Si NO hay actualización → aparece `QMessageBox` **"Sin actualizaciones"**
        con el texto `"Ya tienes la última versión disponible."`
- [ ] El botón vuelve a estar habilitado y muestra **"🔄 Buscar Actualizaciones"**
- [ ] (Edge case) Si no hay internet → el `try/except` se activa, el botón
      vuelve a estar habilitado y aparece un mensaje en el log

**PASS / FAIL:** ☐ PASS  ☐ FAIL — Detalle si FAIL: _____________________

## Sección 5 — Contrato externo (SC-4 / Pitfall 1-2)

> **`WatermarkTab.run_quita_marcas` (QCheckBox público) sigue siendo accedido
> directamente por `gui/controller.py:317`. `WatermarkTab.get_settings()` /
> `set_settings()` / `apply_settings` siguen funcionando.**

- [ ] En `SmartStitchGUI.py`, marcar el checkbox **"Ejecutar Quita Marcas"**
      (que vive en la pestaña WatermarkRemove)
- [ ] Cargar imágenes en el panel principal y click en **"Iniciar"**
- [ ] Tras el pipeline → el **slideshow** se abre automáticamente
      (`controller.py:317` consulta `run_quita_marcas.isChecked()` directamente)
- [ ] Confirmar que NO hay errores en consola del tipo
      `AttributeError: 'WatermarkTab' object has no attribute 'run_quita_marcas'`
- [ ] (Settings) Cerrar SmartStitch y reabrir → los settings de la pestaña
      WatermarkRemove (carpeta de marcas seleccionada, crop pixels, etc.)
      persisten correctamente (esto confirma que `get_settings` / `set_settings`
      siguen operativos tras el refactor)
- [ ] Tras refactor: `git diff --stat gui/controller.py` → **vacío** (Phase 3
      no debe tocar este archivo)

**PASS / FAIL:** ☐ PASS  ☐ FAIL — Detalle si FAIL: _____________________

## Firma final

- **Tester:** ______________________________
- **Fecha:** ______________________________
- **Resultado global:** ☐ APPROVED  ☐ REGRESSION FOUND
- **Descripción de regresión (si aplica):**

```
_________________________________________________________________________
_________________________________________________________________________
_________________________________________________________________________
```

- **Approved → proceder a `/gsd-verify-work` Phase 3**
- **Regression → reabrir el plan responsable de la sección que falló**
