# Phase 4: Visual Polish - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-28
**Phase:** 04-visual-polish
**Areas discussed:** Mecanismo de layout, Agrupación visual de controles (incl. modos UI), Estrategia QSS / colores, Scope de aplicación del tema

---

## Mecanismo de layout

| Option | Description | Selected |
|--------|-------------|----------|
| QSplitter | Proporción inicial 65/35, posición persistida, redimensionable por el usuario | ✓ |
| Proporciones fijas con setStretch | Layout fijo 65/35 sin splitter | |
| Tú decides | Claude elige | |

**User's choice:** QSplitter

---

### Persistir posición del splitter

| Option | Description | Selected |
|--------|-------------|----------|
| Sí, con WmPersistenceService | Guardar sizes() en wm_settings.json | ✓ |
| No, siempre 65/35 inicial | Más simple, predecible | |

**User's choice:** Sí, guardar con WmPersistenceService

---

### Panel de controles con scroll

| Option | Description | Selected |
|--------|-------------|----------|
| QScrollArea en el panel | Siempre visible aunque la ventana se achique | |
| Sin scroll, se comprime | Más simple | ✓ |

**User's choice:** Sin scroll

---

## Agrupación visual de controles

### Separación visual de grupos

| Option | Description | Selected |
|--------|-------------|----------|
| QGroupBox con título | Rectángulo con título visible por grupo. Claro y estándar | ✓ |
| QFrame separadores + header en negrita | Más plano/moderno | |
| Solo espaciado | Sin títulos | |

**User's choice:** QGroupBox con título

---

### Idioma de los títulos

| Option | Description | Selected |
|--------|-------------|----------|
| Español | Navegación / Remoción / Auto-detección / Training Data | ✓ |
| Inglés | Navigation / Removal / Auto-detect / Training | |

**User's choice:** Español

---

### Grupos colapsables

| Option | Description | Selected |
|--------|-------------|----------|
| Siempre visibles | Más simple, QGroupBox estándar | ✓ |
| Colapsables al hacer click | Requiere subclase o checkbox trick | |

**User's choice:** Siempre visibles

---

### Grupo Auto-detección sin modelo YOLO

| Option | Description | Selected |
|--------|-------------|----------|
| Siempre visible, deshabilitado | setEnabled(False) si no hay modelo | |
| Oculto si no hay modelo | setVisible(False) | ✓ |

**User's choice:** Oculto si no hay modelo

---

### Tamaño de botones

| Option | Description | Selected |
|--------|-------------|----------|
| Estándar Qt | Sin padding forzado, qdarktheme define el sizing | ✓ |
| Grandes con padding explícito | padding: 8px 16px | |

**User's choice:** Estándar Qt

---

## Modos UI (descubierto durante discusión de agrupación)

El usuario reveló que los controles del SlideshowViewer tienen 3 modos: Selección (con Avanzado), Recorte, Automático.

### Selector de modo

| Option | Description | Selected |
|--------|-------------|----------|
| QButtonGroup horizontal (radio buttons estilo tab) | Tres QPushButton checkable: [Selección][Recorte][Automático] | ✓ |
| QTabWidget | Tabs reales de Qt | |
| QComboBox desplegable | Lista desplegable | |

**User's choice:** QButtonGroup horizontal

---

### Training Data: posición

| Option | Description | Selected |
|--------|-------------|----------|
| Grupo separado siempre visible abajo | Independiente del modo activo | ✓ |
| Solo visible en modo Selección | Solo durante selección manual | |

**User's choice:** Grupo separado siempre visible abajo

---

### Navegación: posición

| Option | Description | Selected |
|--------|-------------|----------|
| Navegación arriba (persistente, fuera de modos) | Estructura: Nav | Selector | Stack | Training | ✓ |
| Dentro de cada modo | Repetitivo | |

**User's choice:** Navegación arriba, persistente

---

### QStackedWidget vs show/hide

| Option | Description | Selected |
|--------|-------------|----------|
| QStackedWidget | Una página por modo, setCurrentIndex(). Limpio | ✓ |
| show() / hide() de QGroupBox | Más simple pero layout puede saltar | |

**User's choice:** QStackedWidget

---

## Estrategia QSS / colores

### Colores semánticos

| Option | Description | Selected |
|--------|-------------|----------|
| Eliminar colores semánticos, todo teal | UI más limpia y coherente | |
| Mantener rojo/verde para destructivas/confirmación | Mezcla coherente + usabilidad | |
| Tú decides | Claude elige | ✓ |

**User's choice:** Tú decides — Claude decidió mantener rojo (Revert) y verde (Accept) por seguridad en flujo rápido

---

### Aplicación de estilos

| Option | Description | Selected |
|--------|-------------|----------|
| QSS global en stylesheet.py | Un solo lugar para todos los estilos | ✓ |
| Archivo QSS separado WatermarkRemove/ui/style.qss | Modular pero dos lugares | |

**User's choice:** QSS global en stylesheet.py

---

### setStyleSheet() inline

| Option | Description | Selected |
|--------|-------------|----------|
| Eliminar todos los inline | Limpio, tema controla todo | ✓ |
| Mantener algunos como override | Solo eliminar los que chocan | |

**User's choice:** Eliminar todos los setStyleSheet() inline

---

## Scope de aplicación del tema

### load_stylesheet propio vs herencia

| Option | Description | Selected |
|--------|-------------|----------|
| Hereda del QApplication padre | SmartStitchGUI.py ya aplica el tema | ✓ |
| Aplica su propio load_stylesheet | Permite standalone, pero duplica | |

**User's choice:** Hereda del QApplication

---

### Archivos en scope de UI-03

| Option | Description | Selected |
|--------|-------------|----------|
| Solo SlideshowViewer + components/ | Scope más directo | ✓ |
| Todos los widgets de WatermarkRemove/ui/ | Scope total, más riesgo | |

**User's choice:** Solo SlideshowViewer + sus componentes

---

## Claude's Discretion

- **Colores semánticos**: mantener rojo para Revert y verde para Accept. Señales de seguridad importantes en flujo rápido de procesamiento de imágenes. El resto usa teal o tema neutro.
- **Training Data counter style**: hereda el tema sin estilo especial (podría usarse teal si el planner lo considera, Claude tiene flexibilidad).

## Deferred Ideas

- Tooltips y ayuda contextual (UI-05, v2)
- Feedback visual en tiempo real — spinner, indicador "guardado" (UI-04, v2)
- Tests unitarios para componentes UI (ARCH-05, v2)
