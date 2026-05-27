---
phase: 2
slug: slideshowviewer-decomposition
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-26
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Ninguno automatizado para UI (pytest no instalado; ARCH-05 deferred). UAT manual via `02-HUMAN-UAT.md` |
| **Config file** | none — Wave 0 no instala framework (fuera de scope esta fase) |
| **Quick run command** | `python -m py_compile WatermarkRemove/ui/slideshow_viewer.py WatermarkRemove/ui/components/*.py` |
| **Full suite command** | `python SmartStitchGUI.py` (smoke manual end-to-end) |
| **Estimated runtime** | ~5 seconds (compile check) / ~30 seconds (smoke manual) |

---

## Sampling Rate

- **After every task commit:** Run `python -m py_compile WatermarkRemove/ui/slideshow_viewer.py WatermarkRemove/ui/components/*.py`
- **After every plan wave:** Smoke manual abriendo `python SmartStitchGUI.py` con carpeta de imágenes de test
- **Before `/gsd-verify-work`:** UAT completo siguiendo `02-HUMAN-UAT.md` — todos los checkboxes marcados

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ARCH-01 | — | path safety heredado de load_images_cv2 | compile + grep | `python -m py_compile WatermarkRemove/ui/components/navigation_controller.py` | ❌ Wave 0 | ⬜ pending |
| 02-01-02 | 01 | 1 | ARCH-01 | — | N/A estructural | compile + manual | `python -m py_compile WatermarkRemove/ui/slideshow_viewer.py` | ⬜ pending | ⬜ pending |
| 02-02-01 | 02 | 2 | ARCH-01 | — | remove_watermark API preservada | grep + compile | `grep -n "def remove_watermark\|def detect_watermarks" WatermarkRemove/wm_remove.py WatermarkRemove/yolo/auto_detector.py` (firmas sin cambio) | ✅ | ⬜ pending |
| 02-02-02 | 02 | 2 | ARCH-01 | — | N/A estructural | grep | `grep -rn "remove_watermark\|detect_watermarks" WatermarkRemove/ui/slideshow_viewer.py` (esperado: 0 hits directos) | ✅ | ⬜ pending |
| 02-03-01 | 03 | 3 | ARCH-01 | — | N/A estructural | grep + compile | `grep -n "save_training_sample\|remove_training_sample" WatermarkRemove/ui/slideshow_viewer.py` (esperado: 0 hits directos) | ✅ | ⬜ pending |
| 02-03-02 | 03 | 3 | ARCH-01 | — | API pública SlideshowViewer preservada | grep + manual | `grep -n "def get_approved\|def get_output_folder\|def has_processed_images\|review_completed" WatermarkRemove/ui/slideshow_viewer.py` (esperado: presentes) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `WatermarkRemove/ui/components/__init__.py` — paquete vacío para los componentes extraídos
- [ ] `WatermarkRemove/ui/components/navigation_controller.py` — stub mínimo con clase `NavigationController(QWidget)`
- [ ] `WatermarkRemove/ui/components/watermark_processor.py` — stub mínimo con clase `WatermarkProcessor(QWidget)`
- [ ] `WatermarkRemove/ui/components/training_data_collector.py` — stub mínimo con clase `TrainingDataCollector(QWidget)`
- [ ] `.planning/phases/02-slideshowviewer-decomposition/02-HUMAN-UAT.md` — checklist UAT con los 5 success criteria del roadmap

*Si Wave 0 se crea inline en el primer plan: marcar `wave_0_complete: true` antes de ejecutar Wave 1.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visor navega con Space/Backspace sin lógica inline | ARCH-01 SC-1 | pytest no instalado; comportamiento UI | Abrir `python SmartStitchGUI.py`, cargar carpeta con 3+ imágenes, presionar Space/Backspace — verificar navegación fluida |
| Detección YOLO funciona desde componente separado | ARCH-01 SC-2 | Requiere modelo ONNX cargado + imágenes de test reales | Activar auto-detect en SlideshowViewer, verificar detección y remoción sin errores |
| Training data collection funciona | ARCH-01 SC-3 | Requiere carpeta de imágenes activa | Presionar save/remove sample, verificar que `training_data.json` se actualiza correctamente |
| SlideshowViewer ≤20 edges tras refactor | ARCH-01 SC-4 | Requiere correr graphify sobre el código refactorizado | `node bin/graphify.js` → verificar `ui_slideshow_viewer_slideshowviewer` OUT edges ≤20 en graph.json |
| Comportamiento observable idéntico al anterior | ARCH-01 SC-5 | Regresión visual | Abrir el visor antes y después — flujo completo (navegar, remover watermark manualmente, auto-detect, guardar sample) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (compile check: ~5s; smoke manual: ~30s)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
