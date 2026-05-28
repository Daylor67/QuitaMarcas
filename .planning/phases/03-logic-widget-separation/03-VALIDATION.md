---
phase: 3
slug: logic-widget-separation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual (py_compile + import checks) — ARCH-05 (unit tests) deferred to v2 |
| **Config file** | none |
| **Quick run command** | `python -c "import WatermarkRemove.ui.watermark_tab"` |
| **Full suite command** | `python -c "import WatermarkRemove.ui.watermark_tab; import WatermarkRemove.ui.position_editor; import WatermarkRemove.ui.image_viewer"` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick import check
- **After every plan wave:** Run full import suite + manual UAT of watermark remove flow
- **Before `/gsd-verify-work`:** Full suite must be green + manual UAT complete
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 3-01-01 | 01 | 1 | ARCH-02 | — | N/A | import | `python -c "import WatermarkRemove.ui.position_editor"` | ✅ | ⬜ pending |
| 3-01-02 | 01 | 1 | ARCH-02 | — | N/A | import | `python -c "from WatermarkRemove.ui.services import PositionEditorService"` | ❌ W0 | ⬜ pending |
| 3-01-03 | 01 | 1 | ARCH-02 | — | N/A | import | `python -c "import WatermarkRemove.ui.image_viewer"` | ✅ | ⬜ pending |
| 3-02-01 | 02 | 2 | ARCH-04 | — | N/A | import | `python -c "import WatermarkRemove.ui.watermark_tab"` | ✅ | ⬜ pending |
| 3-02-02 | 02 | 2 | ARCH-04 | — | N/A | manual | WatermarkTab.get_settings() returns dict with expected keys | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `WatermarkRemove/ui/services/` directory with `__init__.py` — created in 03-01

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Flujo completo abre → detecta → remueve → guarda sin regresión | ARCH-02, ARCH-04 | No hay test suite automatizada (ARCH-05 deferred) | Correr `python SmartStitchGUI.py`, abrir WatermarkRemove tab, abrir carpeta de imágenes, verificar detección y remoción |
| `WatermarkTab.get_settings()` / `set_settings()` preservan contrato | ARCH-04 | Tests de integración no existen | Verificar que `gui/controller.py` línea 317 sigue funcionando con `run_quita_marcas.isChecked()` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
