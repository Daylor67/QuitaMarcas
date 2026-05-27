"""WatermarkRemove.ui.components - Componentes extraidos del SlideshowViewer.

Cada componente es un QWidget con responsabilidad unica, que se comunica con
el composer (SlideshowViewer) y sus hermanos via Signal/Slot.

Patron: barrel-export analogo a WatermarkRemove/services/__init__.py.
NO se crean singletons aqui — los widgets se construyen por-dialogo desde
el composer (SlideshowViewer.__init__).
"""
from .navigation_controller import NavigationController
from .watermark_processor import WatermarkProcessor
from .training_data_collector import TrainingDataCollector

__all__ = ['NavigationController', 'WatermarkProcessor', 'TrainingDataCollector']
