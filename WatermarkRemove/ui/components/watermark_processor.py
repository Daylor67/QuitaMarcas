"""
WatermarkProcessor - Placeholder — implementacion en Plan 02-02.

Componente que encapsulara el modo manual + modo auto YOLO + position-grid
handlers actualmente inline en SlideshowViewer. En Plan 01 solo existe como
stub para que el composer pueda instanciarlo sin error.

# NOTA: components/ esta dos niveles bajo el package root — usar
# os.path.dirname(os.path.dirname(__file__)) para alcanzar WatermarkRemove/.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class WatermarkProcessor(QWidget):
    def __init__(self, parent=None, watermark_tab=None):
        super().__init__(parent)
