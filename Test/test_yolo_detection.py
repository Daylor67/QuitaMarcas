"""
Visor de pruebas para el modelo YOLOv8 entrenado en detección de marcas de agua.

Uso:
    1. Editá MODEL_PATH y IMAGES_FOLDER abajo (o dejá None para que pida con un dialog).
    2. python Test/test_yolo_detection.py

Controles:
    - Click "Siguiente" / Space  → próxima imagen
    - Click "Anterior" / Backspace → imagen previa
    - Ctrl + rueda                 → zoom
"""
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from natsort import natsorted

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QWidget, QScrollArea, QFileDialog, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QPixmap, QImage, QPainter, QPen, QColor, QKeyEvent, QWheelEvent, QFont
)

from ultralytics import YOLO


# === Editá estos paths o dejá None para que abra un selector ===
MODEL_PATH = r"c:\Users\Felix\Downloads\best (1).pt"
IMAGES_FOLDER = r"c:\Users\Felix\Downloads\test ntk"

CONF_THRESHOLD = 0.25  # Confianza mínima para mostrar detecciones
SUPPORTED_FORMATS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.jfif')

# Colores por class_type (BGR/RGB no aplica acá: son QColor)
CLASS_COLORS = {
    'color':         QColor(33, 150, 243),    # azul
    'gris':          QColor(76, 175, 80),     # verde
    'banner_alto':   QColor(255, 152, 0),     # naranja
    'banner_texto':  QColor(233, 30, 99),     # rosa/magenta
    'banner_apunta': QColor(0, 188, 212),     # cyan
}
FALLBACK_PALETTE = [
    QColor(156, 39, 176),    # púrpura
    QColor(255, 235, 59),    # amarillo
    QColor(96, 125, 139),    # gris azulado
    QColor(121, 85, 72),     # marrón
    QColor(244, 67, 54),     # rojo
]


def color_for_class(class_name: str, fallback_index: int) -> QColor:
    """Devuelve el color asignado a la clase, o uno de la paleta de fallback."""
    if class_name in CLASS_COLORS:
        return CLASS_COLORS[class_name]
    return FALLBACK_PALETTE[fallback_index % len(FALLBACK_PALETTE)]


def load_image_cv2(path: Path) -> np.ndarray:
    """Lee una imagen con soporte de paths Unicode."""
    arr = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


class DetectionViewer(QDialog):
    def __init__(self, model_path: Path, images_folder: Path):
        super().__init__()
        self.setWindowTitle("Test YOLO — Detector de marcas")
        self.resize(1100, 750)

        self.model = YOLO(str(model_path))
        self.image_files = [
            f for f in natsorted(images_folder.iterdir())
            if f.is_file() and f.suffix.lower() in SUPPORTED_FORMATS
        ]
        if not self.image_files:
            raise ValueError(f"No hay imágenes en {images_folder}")

        self.current_index = 0
        self.zoom_level = 100
        self.original_pixmap = None

        # Mapeo dinámico de clase → índice de fallback (para colores estables aunque no estén en CLASS_COLORS)
        self._fallback_index = {}
        for i, name in enumerate(sorted(self.model.names.values())):
            if name not in CLASS_COLORS:
                self._fallback_index[name] = len(self._fallback_index)

        self._setup_ui()
        self._show_current()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # === Panel superior: info ===
        info_group = QGroupBox("ℹ️ Info")
        info_layout = QVBoxLayout(info_group)
        self.counter_label = QLabel("0 / 0")
        self.counter_label.setStyleSheet("font-size: 13px; font-weight: bold;")
        info_layout.addWidget(self.counter_label)

        self.filename_label = QLabel("")
        self.filename_label.setStyleSheet("font-size: 11px; color: #888;")
        self.filename_label.setWordWrap(True)
        info_layout.addWidget(self.filename_label)

        self.detections_label = QLabel("Detecciones: 0")
        self.detections_label.setStyleSheet("font-size: 11px; color: #ccc;")
        info_layout.addWidget(self.detections_label)

        layout.addWidget(info_group)

        # === Imagen con scroll y zoom ===
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setStyleSheet("background-color: #2b2b2b; border: 1px solid #444;")
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

        # === Botonera ===
        btns = QHBoxLayout()
        self.prev_btn = QPushButton("◀ Anterior")
        self.prev_btn.clicked.connect(self._prev)
        btns.addWidget(self.prev_btn)

        self.next_btn = QPushButton("Siguiente ▶")
        self.next_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.next_btn.clicked.connect(self._next)
        btns.addWidget(self.next_btn)

        layout.addLayout(btns)

        # === Leyenda de colores ===
        legend_group = QGroupBox("🎨 Leyenda de clases")
        legend_layout = QHBoxLayout(legend_group)
        legend_layout.setSpacing(15)
        for cls_name in sorted(self.model.names.values()):
            color = self._color_for_class(cls_name)
            chip = QLabel(f"  {cls_name}  ")
            chip.setStyleSheet(
                f"background-color: rgba({color.red()},{color.green()},{color.blue()},80);"
                f"border: 2px solid rgba({color.red()},{color.green()},{color.blue()},220);"
                f"padding: 3px 6px; border-radius: 4px; font-size: 11px;"
            )
            legend_layout.addWidget(chip)
        legend_layout.addStretch()
        layout.addWidget(legend_group)

    def _color_for_class(self, class_name: str) -> QColor:
        return color_for_class(class_name, self._fallback_index.get(class_name, 0))

    def _show_current(self):
        path = self.image_files[self.current_index]
        img = load_image_cv2(path)
        if img is None:
            QMessageBox.warning(self, "Error", f"No se pudo cargar: {path.name}")
            return

        # Inferencia
        results = self.model.predict(img, conf=CONF_THRESHOLD, verbose=False)
        boxes = results[0].boxes if results else None

        # Convertir cv2 BGR → QPixmap
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg.copy())

        # Dibujar overlays
        n_detections = 0
        if boxes is not None and len(boxes) > 0:
            n_detections = len(boxes)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)

            for box in boxes:
                cls_id = int(box.cls)
                cls_name = self.model.names[cls_id]
                conf = float(box.conf)
                x1, y1, x2, y2 = box.xyxy[0].tolist()

                color = self._color_for_class(cls_name)
                fill = QColor(color.red(), color.green(), color.blue(), 60)

                pen = QPen(color)
                pen.setWidth(3)
                painter.setPen(pen)
                painter.setBrush(fill)
                painter.drawRect(int(x1), int(y1), int(x2 - x1), int(y2 - y1))

                # Label con fondo opaco
                label = f"{cls_name} {conf:.2f}"
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                fm = painter.fontMetrics()
                label_w = fm.horizontalAdvance(label) + 8
                label_h = fm.height() + 4
                painter.drawRect(int(x1), int(y1) - label_h, label_w, label_h)
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(int(x1) + 4, int(y1) - 4, label)

            painter.end()

        self.original_pixmap = pixmap
        self._apply_zoom()

        # Actualizar UI
        self.counter_label.setText(f"{self.current_index + 1} / {len(self.image_files)}")
        self.filename_label.setText(path.name)
        self.detections_label.setText(f"Detecciones: {n_detections}")
        self.prev_btn.setEnabled(self.current_index > 0)
        self.next_btn.setEnabled(self.current_index < len(self.image_files) - 1)

    def _apply_zoom(self):
        if self.original_pixmap is None:
            return
        scale = self.zoom_level / 100.0
        scaled = self.original_pixmap.scaled(
            self.original_pixmap.size() * scale,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def _next(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self._show_current()

    def _prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._show_current()

    # === Atajos de teclado ===
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._next()
        elif key == Qt.Key.Key_Backspace:
            self._prev()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_level = min(300, self.zoom_level + 10)
            self._apply_zoom()
        elif key == Qt.Key.Key_Minus:
            self.zoom_level = max(10, self.zoom_level - 10)
            self._apply_zoom()
        elif key == Qt.Key.Key_0:
            self.zoom_level = 100
            self._apply_zoom()
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = 10 if event.angleDelta().y() > 0 else -10
            self.zoom_level = max(10, min(300, self.zoom_level + delta))
            self._apply_zoom()
            event.accept()
        else:
            super().wheelEvent(event)


def main():
    app = QApplication(sys.argv)

    # Resolver MODEL_PATH
    model_path = MODEL_PATH
    if not model_path or not Path(model_path).exists():
        path, _ = QFileDialog.getOpenFileName(
            None, "Seleccioná best.pt (modelo YOLO entrenado)", "",
            "Modelo PyTorch (*.pt)"
        )
        if not path:
            print("Cancelado."); sys.exit(0)
        model_path = path
    model_path = Path(model_path)

    # Resolver IMAGES_FOLDER
    images_folder = IMAGES_FOLDER
    if not images_folder or not Path(images_folder).is_dir():
        folder = QFileDialog.getExistingDirectory(
            None, "Seleccioná carpeta con imágenes a probar"
        )
        if not folder:
            print("Cancelado."); sys.exit(0)
        images_folder = folder
    images_folder = Path(images_folder)

    try:
        viewer = DetectionViewer(model_path, images_folder)
        viewer.show()
        sys.exit(app.exec())
    except Exception as e:
        QMessageBox.critical(None, "Error", str(e))
        raise


if __name__ == "__main__":
    main()
