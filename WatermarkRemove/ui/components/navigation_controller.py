"""
NavigationController - Stub minimo. Implementacion completa en Task 2 del Plan 02-01.

Componente responsable de:
- Lista de imagenes y current_index
- working_image / output_folder / processed_images / processed_positions
- Zoom y render del pixmap (panel derecho del visor)
- Botones prev/next y contador

# NOTA: components/ esta dos niveles bajo el package root — usar
# os.path.dirname(os.path.dirname(__file__)) para alcanzar WatermarkRemove/.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class NavigationController(QWidget):
    def __init__(self, folder_path: str, parent=None, watermark_tab=None):
        super().__init__(parent)
