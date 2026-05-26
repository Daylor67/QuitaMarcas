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
