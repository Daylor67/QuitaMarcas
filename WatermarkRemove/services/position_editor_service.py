"""
PositionEditorService - Servicio de dominio del editor de posiciones (Phase 3, Plan 03-01).

Responsabilidades:
- Cargar imagen y marca desde disco usando `load_images_cv2` (np.fromfile,
  seguro contra paths no-ASCII — NUNCA usar la API estándar de OpenCV
  para leer imágenes directamente, RESEARCH Pitfall 3).
- Construir el preview de remoción de marca: aplica `align_watermark` +
  `remove_watermark` y retorna un `QPixmap` listo para `set_image` en el
  widget (RESEARCH Open Question #1 — el servicio retorna QPixmap por
  conveniencia; no hay tests automatizados, ARCH-05 deferred a v2).

Este servicio extrae la lógica inline del widget `WatermarkRemove/ui/position_editor.py`
(_update_preview L474-507, _load_current_image L444-460, _load_current_watermark L452-460)
para satisfacer ARCH-02 (lógica de dominio fuera de los widgets UI).
"""
import os
import sys

# services/ esta UN nivel bajo WatermarkRemove/.
# os.path.dirname(__file__) -> WatermarkRemove/services
# os.path.dirname(os.path.dirname(__file__)) -> WatermarkRemove
# Para importar el package WatermarkRemove necesitamos el repo root,
# es decir DOS niveles arriba de services/.
current_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import cv2
from PySide6.QtGui import QImage, QPixmap

from WatermarkRemove import load_images_cv2, align_watermark, remove_watermark


class PositionEditorService:
    """Servicio de dominio del editor manual de posiciones.

    Encapsula las llamadas a `load_images_cv2`, `align_watermark` y
    `remove_watermark` para que el widget `PositionEditor` quede como
    capa puramente presentacional.

    El servicio es stateless (no cachea imágenes ni resultados): cada
    llamada opera sobre los arrays que recibe como argumento, igual que
    el patrón de `wm_persistence.py` de Phase 1.
    """

    def load_image(self, path):
        """Carga una imagen (o marca) desde disco usando `load_images_cv2`.

        SEGURIDAD: usa `np.fromfile` + `cv2.imdecode` internamente, lo cual
        es seguro para paths con caracteres no-ASCII en Windows. NUNCA usar
        la API estándar de OpenCV para leer imágenes directamente
        (RESEARCH Pitfall 3, Security V5).

        Args:
            path: ruta al archivo de imagen (str o Path).

        Returns:
            np.ndarray BGR/BGRA tal como lo retorna `cv2.imdecode`.

        Raises:
            ValueError: si la imagen no se pudo decodificar.
        """
        return load_images_cv2(str(path))

    def build_preview_pixmap(
        self,
        image,
        watermark,
        *,
        offset_x: int,
        offset_y: int,
        side_x: str,
        side_y: str,
    ) -> QPixmap:
        """Construye el preview de remoción de marca y lo retorna como QPixmap.

        Proceso (extracto verbatim de position_editor._update_preview L480-497,
        movido al servicio para satisfacer ARCH-02):
        1. Copia la imagen (no muta el array original).
        2. `align_watermark` calcula coordenadas (x, y) según offsets + lados.
        3. `remove_watermark` aplica la remoción en la copia.
        4. Convierte BGR -> RGB con `cv2.cvtColor`.
        5. Construye `QImage` (Format_RGB888) y retorna `QPixmap.fromImage`.

        Args:
            image: imagen base como ndarray (BGR), tal como retorna `load_image`.
            watermark: marca como ndarray, tal como retorna `load_image`.
            offset_x: desplazamiento horizontal en px.
            offset_y: desplazamiento vertical en px.
            side_x: lado horizontal de anclaje ("left" / "right" / etc., tal
                cual el widget lo pasa hoy a `align_watermark`).
            side_y: lado vertical de anclaje (idem).

        Returns:
            QPixmap listo para `QLabel.setPixmap` / `image_label.set_image`.
        """
        img_copy = image.copy()
        x, y = align_watermark(
            img_copy,
            watermark,
            offset_x=offset_x,
            offset_y=offset_y,
            side_x=side_x,
            side_y=side_y,
        )
        result_img = remove_watermark(img_copy, watermark, x, y)
        result_rgb = cv2.cvtColor(result_img, cv2.COLOR_BGR2RGB)
        h, w, _ = result_rgb.shape
        q_image = QImage(result_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(q_image)
