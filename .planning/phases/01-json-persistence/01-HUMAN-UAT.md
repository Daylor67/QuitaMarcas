---
status: partial
phase: 01-json-persistence
source: [01-VERIFICATION.md]
started: 2026-05-26T22:00:00Z
updated: 2026-05-26T22:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Round-trip de last_watermark_folder
expected: Abrir la app, seleccionar una carpeta de marcas de agua, cerrar, reabrir — la carpeta queda pre-seleccionada (persiste en wm_settings.json)
result: [pending]

### 2. Round-trip de last_crop_pixels
expected: Abrir la app, cambiar crop pixels a un valor no-cero, cerrar, reabrir — el spinbox restaura ese valor (persiste en wm_settings.json)
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
