"""
Servicio de persistencia de estado UI del módulo WatermarkRemove.
"""
import os
from typing import Optional

from core.utils.constants import SETTINGS_REL_DIR
from utils import UtilJson


class WmPersistenceService:
    """Servicio de persistencia de estado UI del módulo WatermarkRemove.

    Wrappea UtilJson con nombres de dominio para desacoplar slideshow_viewer
    de la implementación concreta de persistencia JSON.

    El servicio NO cachea datos en memoria — cada llamada crea una instancia
    de UtilJson y lee/escribe el archivo, consistente con el patrón original.
    """

    def __init__(self):
        self._path = os.path.join(SETTINGS_REL_DIR, 'wm_settings.json')

    def get_last_crop_pixels(self) -> int:
        """Retorna el último valor de crop pixels. Default: 0."""
        return UtilJson(self._path).get('last_crop_pixels', 0) or 0

    def set_last_crop_pixels(self, value: int) -> None:
        """Persiste el valor de crop pixels."""
        UtilJson(self._path).set('last_crop_pixels', int(value))

    def get_last_watermark_folder(self) -> Optional[str]:
        """Retorna el nombre de la ultima carpeta de marcas usada. Default: None."""
        return UtilJson(self._path).get('last_watermark_folder', None)

    def set_last_watermark_folder(self, folder_name: str) -> None:
        """Persiste el nombre de la carpeta de marcas seleccionada."""
        UtilJson(self._path).set('last_watermark_folder', folder_name)

    def get_splitter_sizes(self, default: list) -> list:
        """Retorna los tamaños del splitter desde wm_settings.json. Default si no existe."""
        value = UtilJson(self._path).get('splitter_sizes', default)
        if isinstance(value, list) and len(value) > 0:
            return [int(v) for v in value]
        return list(default)

    def set_splitter_sizes(self, sizes: list) -> None:
        """Persiste los tamaños del splitter en wm_settings.json."""
        UtilJson(self._path).set('splitter_sizes', [int(v) for v in sizes])

    def get_conf_threshold(self) -> int:
        """Retorna el umbral de confianza YOLO guardado (1-100). Default: 90."""
        value = UtilJson(self._path).get('conf_threshold', 90)
        return max(1, min(100, int(value)))

    def set_conf_threshold(self, value: int) -> None:
        """Persiste el umbral de confianza YOLO (1-100)."""
        UtilJson(self._path).set('conf_threshold', max(1, min(100, int(value))))
