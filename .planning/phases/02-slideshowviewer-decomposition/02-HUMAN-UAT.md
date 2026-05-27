---
phase: 02-slideshowviewer-decomposition
type: uat
created: 2026-05-26
status: pending
---

# Phase 2 — UAT Checklist (Manual Verification)

> Validación humana de los 5 success criteria de ARCH-01 (ROADMAP §Phase 2 lines 48-53).
>
> El usuario debe completar este checklist sobre la app con código refactorizado **antes** de `/gsd-verify-work`.
> Patrón heredado de `01-HUMAN-UAT.md` (Phase 1).

## Pre-requisites

- [ ] `python -m py_compile WatermarkRemove/ui/slideshow_viewer.py WatermarkRemove/ui/components/*.py` — sale 0
- [ ] Carpeta de test con 3+ imágenes (PNG/JPG/WEBP) preparada en disco
- [ ] Carpeta `WatermarkRemove/marcas/<alguna>/` con al menos 1 PNG de marca
- [ ] `wm_positions.json` con al menos 1 posición guardada para esa marca (opcional pero recomendado)

## Sección 1 — Navegación (SC-1 / ARCH-01 SC-1)

> **El visor slideshow navega imágenes con Space/Backspace sin que el widget tenga lógica de procesamiento inline.**

- [ ] Abrir `python SmartStitchGUI.py`, activar "Ejecutar Quita Marcas", click "Iniciar"
- [ ] Cargar carpeta de test → se abre `SlideshowViewer`
- [ ] Presionar **Space** → avanza a la imagen siguiente
- [ ] Presionar **Backspace** → retrocede a la imagen anterior
- [ ] Contador `N / total` se actualiza correctamente
- [ ] Filename label muestra el nombre del archivo actual
- [ ] Botones "Anterior" / "Siguiente" funcionan idénticamente a Space/Backspace
- [ ] `Ctrl + rueda mouse` zoomea in/out; `Ctrl + Plus / Minus / 0` también
- [ ] Overlay flotante de zoom aparece y desaparece tras 2s
- [ ] Tras refactor: `grep -n "def _load_image_list\|def _show_current_image\|def _next_image\|def _previous_image" WatermarkRemove/ui/slideshow_viewer.py` → **0 hits** (lógica movida)

## Sección 2 — Modo Manual + Posiciones Guardadas (SC-2 / ARCH-01 SC-2)

> **La detección manual y la ejecución de `remove_watermark()` viven en componentes separados del widget de navegación.**

- [ ] Seleccionar una carpeta de marcas del combo (debe persistir entre sesiones)
- [ ] Click en la imagen sobre una posición roja guardada → marca removida, cuadro pasa a verde, avanza a siguiente imagen
- [ ] Click derecho sobre otra posición roja → marca removida acumulativamente (NO avanza)
- [ ] Activar checkbox "Modo selección manual"
- [ ] Click izquierdo sobre la marca de la imagen → preview azul aparece, botones "Aceptar" / "Revertir" visibles
- [ ] Botones prev/next y combo de marca **deshabilitados** durante preview activo
- [ ] Ajustar `Alpha adjust` → preview se recalcula en vivo
- [ ] Ajustar `H:` / `V:` (offset) → preview se recalcula en vivo
- [ ] Toggle "Preview rápida" → vectorizado funciona
- [ ] Click "Aceptar" (o Space cuando preview activo) → marca aplicada, archivo guardado en `[sin marca]`, controles re-habilitados
- [ ] Click "Revertir" (o Backspace cuando preview activo) → estado limpio, no se guarda nada
- [ ] Tras refactor: `grep -n "def _accept_preview\|def _remove_watermark_preview\|remove_watermark(" WatermarkRemove/ui/slideshow_viewer.py` → **0 hits** (lógica movida)

## Sección 3 — Modo Auto YOLO (SC-2 / ARCH-01 SC-2)

> **La detección YOLO/auto vive en componente separado.**

- [ ] Activar checkbox "🤖 Modo detección automática"
- [ ] Panel "Selección" se oculta; aparece panel "🤖 Detección automática"
- [ ] Lista de detecciones se puebla con clases detectadas (al menos 1 si la imagen tiene marca)
- [ ] Seleccionar una detección de la lista → highlight amarillo aparece sobre la marca
- [ ] Modificar `H:` / `V:` → highlight se mueve
- [ ] Toggle "Preview rápida (cancelación)" → preview vectorizado se aplica/quita
- [ ] Click "🗑 Eliminar" → la marca seleccionada desaparece de la lista
- [ ] Click "↻ Re-detectar" → vuelve a correr YOLO sobre la imagen actual
- [ ] Click "✓ Guardar" → todas las marcas aplicadas, archivo guardado, lista limpiada
- [ ] Click "✓ Guardar y Siguiente" → guarda y avanza a la imagen siguiente
- [ ] Tras refactor: `grep -n "detect_watermarks\|resolve_png_for_class" WatermarkRemove/ui/slideshow_viewer.py` → **0 hits** (lógica movida)

## Sección 4 — Training Data Collection (SC-3 / ARCH-01 SC-3)

> **La recopilación de training data opera desde su propio componente sin acoplar el visor.**

- [ ] Box "📊 Datos recopilados" visible en el panel de controles
- [ ] Tras aceptar una remoción manual de marca con clase entrenable (alto/apunta/texto): conteo se incrementa
- [ ] Tras aceptar auto-detección con clase entrenable: conteo se incrementa
- [ ] Click "↺ Resetear imagen" → conteo decrece en N (entradas asociadas a esa imagen eliminadas)
- [ ] Tras refactor: `grep -n "save_training_sample\|remove_training_sample" WatermarkRemove/ui/slideshow_viewer.py` → **0 hits** (lógica movida)

## Sección 5 — Edge Count Goal (SC-4 / ARCH-01 SC-4)

> **SlideshowViewer tiene 20 o menos edges de dependencia directa.**

- [ ] Regenerar grafo: `node bin/graphify.js` (o el script equivalente del repo)
- [ ] Inspeccionar `graphify-out/graph.json` — buscar nodo `ui_slideshow_viewer_slideshowviewer`
- [ ] Contar OUT edges del nodo del **class** `SlideshowViewer` (no del archivo completo)
- [ ] Resultado: ≤ 20 (línea baseline 58 antes del refactor) — anotar el conteo final aquí: __________
- [ ] Si > 20: documentar qué edges quedan y por qué (puede ser legítimo si son a `QWidget`/`QSignal`/los 3 componentes hijos + API pública)

## Sección 6 — Comportamiento Observable Idéntico (SC-5 / ARCH-01 SC-5)

> **El usuario no nota ningún cambio funcional.**

- [ ] Modo recorte: checkbox aparece, spinbox de pixels persiste valor entre sesiones (vía `wm_persistence.set_last_crop_pixels`)
- [ ] Modo recorte: toggle "De abajo hacia arriba" funciona
- [ ] Modo recorte: click "Aplicar recorte" recorta y guarda
- [ ] Botones "Finalizar y Procesar" → diálogo de confirmación → cierra el visor → SmartStitchGUI continúa con la carpeta `[sin marca]`
- [ ] Botón "Cancelar" → diálogo de confirmación → cierra sin procesar; SmartStitchGUI muestra "Proceso cancelado"
- [ ] Filtro de marcas (`Filtrar marcas...`) limita lista del combo de marcas
- [ ] `wm_settings.json` se actualiza con `last_watermark_folder` al cambiar de carpeta
- [ ] Console del watermark_tab muestra los mismos logs (emoji + mensaje) que antes
- [ ] `gui/controller.py:321` sigue funcionando sin cambios: `viewer = SlideshowViewer(input_path, MainWindow, watermark_tab=watermark_tab); viewer.exec(); viewer.get_approved(); viewer.has_processed_images(); viewer.get_output_folder()`

## Final Sign-Off

- [ ] Las 6 secciones marcadas
- [ ] Ningún regresión visual o funcional observada
- [ ] Edge count documentado (sección 5)
- [ ] Listo para `/gsd-verify-work`

**UAT completed by:** ___________
**Date:** ___________
