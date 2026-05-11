"""
Detección automática de marcas de agua usando YOLOv8.

Carga el modelo entrenado desde `WatermarkRemove/best.pt` y expone:
- detect_watermarks(image)       → lista de detecciones (clase + bbox + conf)
- resolve_png_for_class(...)     → busca el PNG correspondiente en la carpeta de marcas

El modelo se cachea entre llamadas.
"""
import re
from pathlib import Path
from typing import Optional, List, Dict

import numpy as np


MODEL_PATH = Path(__file__).parent / 'best.pt'
DEFAULT_CONF_THRESHOLD = 0.90

_model_cache = None


def load_yolo_model():
    """Carga el modelo una sola vez. Lanza FileNotFoundError si best.pt no existe."""
    global _model_cache
    if _model_cache is None:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Modelo YOLO no encontrado: {MODEL_PATH}")
        from ultralytics import YOLO
        _model_cache = YOLO(str(MODEL_PATH))
    return _model_cache


def detect_watermarks(image_bgr: np.ndarray, conf_threshold: float = DEFAULT_CONF_THRESHOLD) -> List[Dict]:
    """
    Corre YOLO sobre la imagen y devuelve detecciones ordenadas por confianza.

    Returns:
        Lista de dicts: {'class_type': str, 'confidence': float, 'bbox': (x1, y1, x2, y2)}
    """
    model = load_yolo_model()
    results = model.predict(image_bgr, conf=conf_threshold, verbose=False)
    detections = []
    if not results:
        return detections

    for box in results[0].boxes:
        cls_id = int(box.cls)
        detections.append({
            'class_type': model.names[cls_id],
            'confidence': float(box.conf),
            'bbox': tuple(box.xyxy[0].tolist()),
        })
    return detections


def _candidate_folders(primary: Path) -> List[Path]:
    """
    Carpeta primaria + hermanas que comparten el primer token del nombre.
    Ejemplo: primary "ntk01" + hermana "ntk01 banners" comparten "ntk01" → ambas candidatas.
    Carpetas como "465" o "colamanga" quedan excluidas.
    """
    primary = Path(primary)
    candidates = [primary]
    if not primary.parent.exists():
        return candidates
    primary_token = primary.name.split()[0].lower() if primary.name else ''
    if not primary_token:
        return candidates
    for sibling in primary.parent.iterdir():
        if not sibling.is_dir() or sibling == primary:
            continue
        sibling_token = sibling.name.split()[0].lower() if sibling.name else ''
        if sibling_token == primary_token:
            candidates.append(sibling)
    return candidates


def resolve_png_for_class(watermark_folder: Path, class_type: str, image_width: int) -> Optional[Path]:
    """
    Busca el PNG cuyo nombre matchea la clase y cuyo width prefix es el más cercano
    al ancho de la imagen objetivo.

    Busca en `watermark_folder` y en hermanas relacionadas (mismo primer token).
    Nombres esperados: "<width> <clase con espacios>.png"
    Ejemplo: "720 banner alto.png" → width=720, clase normalizada "banner_alto".
    """
    if watermark_folder is None or not Path(watermark_folder).exists():
        return None

    best = None
    best_diff = float('inf')
    for folder in _candidate_folders(Path(watermark_folder)):
        for png in folder.glob("*.png"):
            m = re.match(r'^(\d+\.?\d*)\s+(.+)$', png.stem)
            if not m:
                continue
            width = float(m.group(1))
            cls_name = m.group(2).strip().replace(' ', '_').lower()
            if cls_name != class_type:
                continue
            diff = abs(width - image_width)
            if diff < best_diff:
                best_diff = diff
                best = png
    return best
