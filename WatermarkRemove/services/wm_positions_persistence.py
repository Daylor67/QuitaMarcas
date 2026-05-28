"""
WmPositionsPersistenceService - Persistencia anidada de wm_positions.json
(Phase 3, Plan 03-01).

Extrae `position_editor._save_to_json` L569-600 a un servicio que wrappea
`UtilJson`, preservando:
- La estructura anidada `carpeta -> marca -> pos_N` (modo "por marca",
  default) o `carpeta -> pos_N` directo (modo legacy "por carpeta").
- La preservación de claves existentes en la misma carpeta
  (`folder_data = json_file.get(name, {}) or {}` — RESEARCH Pitfall, parse
  defensivo).
- El destino físico `WatermarkRemove/wm_positions.json` (mismo archivo que
  hoy escribe el widget).

Sigue el patrón de `wm_persistence.py` (Phase 1): wrap UtilJson, sin cache
en memoria, cada llamada lee y escribe el archivo.
"""
import os
from pathlib import Path
from typing import Optional

# services/ esta UN nivel bajo WatermarkRemove/.
# Para importar `utils` (módulo top-level del repo) necesitamos el repo root,
# DOS niveles arriba de services/.
import sys
_current_dir = os.path.abspath(os.path.dirname(__file__))
_repo_root = os.path.dirname(os.path.dirname(_current_dir))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from utils import UtilJson


class WmPositionsPersistenceService:
    """Servicio de persistencia para `WatermarkRemove/wm_positions.json`.

    Encapsula el acceso al JSON anidado de posiciones para que el widget
    `PositionEditor` quede como capa puramente presentacional (ARCH-02).

    El servicio NO cachea datos en memoria — cada llamada crea una instancia
    nueva de UtilJson y lee/escribe el archivo, consistente con el patrón
    de `WmPersistenceService` (Phase 1).

    Estructura del JSON (NO se modifica — RESEARCH Out of Scope, Pitfall 4):
        {
            "<watermark_folder_name>": {
                # modo "por marca" (default):
                "<watermark_filename.png>": {
                    "pos_1": { offset_x, offset_y, side_x, side_y },
                    "pos_2": { ... },
                    ...
                },
                # modo "por carpeta" (legacy):
                "pos_1": { ... },
                "pos_2": { ... },
            },
            ...
        }
    """

    def __init__(self):
        # services/ -> WatermarkRemove/ con un solo dirname (services es UN
        # nivel bajo WatermarkRemove/). El destino debe ser exactamente
        # `WatermarkRemove/wm_positions.json` — mismo path que hoy usa
        # `position_editor.py:576` desde `ui/` con `os.path.dirname(current_dir)`.
        # En services/ es análogo: dirname una sola vez para llegar a
        # WatermarkRemove/. RESEARCH PATTERNS L170 confirmó "doble dirname"
        # razonando desde el archivo source en ui/ (un dirname para
        # services/__file__ → services/, segundo para → WatermarkRemove/),
        # pero la forma idiomática es os.path.dirname(__file__) → services/,
        # y otro dirname → WatermarkRemove/. Se preserva el patrón de doble
        # dirname desde __file__ para mantener simetría con el plan.
        self._json_path = (
            Path(os.path.abspath(os.path.dirname(os.path.dirname(__file__)))) / 'wm_positions.json'
        )

    def save_positions(
        self,
        watermark_folder_name: str,
        saved_positions: list,
        *,
        save_by_watermark: bool,
        watermark_filename: Optional[str],
    ) -> str:
        """Persiste posiciones a `wm_positions.json` preservando claves existentes.

        Extracto verbatim de `position_editor._save_to_json` L580-596, movido
        al servicio para satisfacer ARCH-02.

        Args:
            watermark_folder_name: nombre de la carpeta de marcas (clave nivel 1
                del JSON, ej. "newtoki").
            saved_positions: lista de dicts {offset_x, offset_y, side_x, side_y}
                acumulados durante la sesión del editor. Se renumeran a
                `pos_1`, `pos_2`, ... empezando en 1.
            save_by_watermark: si True, anida las posiciones bajo
                `watermark_filename` (modo "por marca", default del widget);
                si False, escribe `pos_X` directamente bajo la carpeta (modo
                legacy "por carpeta").
            watermark_filename: nombre del archivo PNG de la marca (ej.
                "marca_01.png"). Requerido cuando `save_by_watermark=True`.

        Returns:
            Label descriptivo del destino guardado para feedback al usuario,
            con el mismo formato que hoy imprime el widget:
            - modo por marca: `"<folder> / <filename>"`
            - modo por carpeta: `"<folder>"`

        Raises:
            ValueError: si `save_by_watermark=True` y `watermark_filename` es
                None (preserva el guard L587 del widget original).
        """
        positions_dict = {
            f'pos_{i}': p for i, p in enumerate(saved_positions, start=1)
        }

        json_file = UtilJson(self._json_path)
        # Preservar otras marcas/posiciones ya guardadas en la misma carpeta
        # (defensive get: `.get(key, {}) or {}` — RESEARCH Defensive JSON access).
        folder_data = json_file.get(watermark_folder_name, {}) or {}

        if save_by_watermark:
            if not watermark_filename:
                raise ValueError(
                    "No hay marca seleccionada para asociar las posiciones"
                )
            folder_data[watermark_filename] = positions_dict
            target_label = f"{watermark_folder_name} / {watermark_filename}"
        else:
            # Modo carpeta (legacy): pos_X directos al folder
            for k, v in positions_dict.items():
                folder_data[k] = v
            target_label = watermark_folder_name

        json_file.set(watermark_folder_name, folder_data)
        return target_label
