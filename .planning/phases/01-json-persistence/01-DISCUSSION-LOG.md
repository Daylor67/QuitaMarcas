# Phase 1: JSON Persistence - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 1-JSON Persistence
**Areas discussed:** ¿Dónde viven los settings de WM?, ¿Dónde vive el nuevo servicio?

---

## ¿Dónde viven los settings de WM?

| Option | Description | Selected |
|--------|-------------|----------|
| Archivo separado wm_settings.json | WatermarkRemove tiene su propio archivo limpio. Sin riesgo de pisar la estructura de perfiles de SmartStitch. | ✓ |
| Dentro del perfil de SmartStitch | last_crop_pixels y last_watermark_folder se guardan como claves dentro del perfil actual en SettingsHandler. | |
| Mantener en settings.json pero con namespace | settings.json sigue siendo el archivo, pero WM escribe bajo una clave 'watermark'. | |

**User's choice:** Archivo separado wm_settings.json
**Notes:** Preferencia por aislamiento — evitar que WatermarkRemove y SmartStitch compartan el mismo archivo de settings y se pisen mutuamente.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Solo las 2 actuales (last_crop_pixels, last_watermark_folder) | Migrar exactamente lo que existe hoy. No ampliar scope. | ✓ |
| También incluir wm_positions.json | Las posiciones de watermarks son también settings de WM. | |
| Yo decido — lo que el planner considere natural | El planner identifica todas las keys. | |

**User's choice:** Solo las 2 actuales
**Notes:** Scope mínimo — no cambiar wm_positions.json ni training_data.json.

---

## ¿Dónde vive el nuevo servicio?

| Option | Description | Selected |
|--------|-------------|----------|
| WatermarkRemove/services/ | Nuevo directorio dentro del módulo. El servicio es específico de WatermarkRemove. | ✓ |
| core/services/ (junto a SettingsHandler) | Queda como servicio global de SmartStitch. | |
| utils/ (junto a UtilJson) | Mezcla utilidades genéricas con lógica de dominio específica. | |

**User's choice:** WatermarkRemove/services/
**Notes:** El servicio es específico de WatermarkRemove, no tiene sentido en core/.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Instancia de módulo (singleton simple) | El servicio se instancia una vez y se importa donde se necesita. Sin inyección, sin complejidad. | ✓ |
| Pasado en constructor (inyección) | Más testeable pero agrega complejidad a constructores. | |
| Yo decido | El planner elige el patrón más simple. | |

**User's choice:** Instancia de módulo (singleton simple)
**Notes:** Preferencia por simplicidad — mismo patrón que el resto del módulo usa con imports directos.

---

## Claude's Discretion

- Nombre del archivo y clase del servicio
- Si el servicio expone API tipada (get_last_folder) o genérica (get/set)
- Manejo de migración de claves existentes en settings.json

## Deferred Ideas

- Unificar training_collector.py (usa json crudo) — fuera de scope, training_data.json tiene formato fijo
- Inyección de dependencias para servicios de WatermarkRemove — over-engineering para esta fase
