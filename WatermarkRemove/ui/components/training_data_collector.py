"""
TrainingDataCollector - Placeholder — implementacion en Plan 02-03.

Componente que encapsulara el conteo de muestras de entrenamiento
(training_data.json) actualmente inline en SlideshowViewer. En Plan 01
solo existe como stub.

# NOTA: components/ esta dos niveles bajo el package root — usar
# os.path.dirname(os.path.dirname(__file__)) para alcanzar WatermarkRemove/.
"""
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal


class TrainingDataCollector(QWidget):
    def __init__(self, parent=None, watermark_tab=None):
        super().__init__(parent)
