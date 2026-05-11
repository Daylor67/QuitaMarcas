"""
Recopilación de datos de entrenamiento YOLO.

Cada vez que el usuario acepta una remoción manual de marca de agua, se guarda:
- imagen original (con marca) en base64
- bounding box en formato YOLO (cx, cy, bw, bh normalizados)
- nombre/clase de la marca usada
- timestamp

El archivo resultante (`training_data.json`) puede ser exportado por el usuario
y enviado para entrenar el modelo.
"""
import os
import re
import json
import base64
from datetime import datetime
from pathlib import Path
from typing import Union

import numpy as np


# Solo se acumulan muestras de estas clases. Las clases no listadas ya están
# suficientemente entrenadas y no aportan al modelo guardar más ejemplos.
TRAINABLE_CLASS = ('alto', 'apunta', 'texto')


def is_trainable_class(class_type: str) -> bool:
    """True si la clase requiere más datos de entrenamiento."""
    return class_type in TRAINABLE_CLASS


def png_name_to_class(png_name: Union[str, Path]) -> str:
    """
    Extrae la clase del nombre del PNG.

    Ejemplos:
        "690 banner alto.png"   → "banner_alto"
        "1197.5 color.png"      → "color"
        "720 banner texto.png"  → "banner_texto"
    """
    name = Path(png_name).stem  # quitar .png
    name = re.sub(r'^\d+\.?\d*\s+', '', name)  # quitar número inicial
    return name.replace(' ', '_').lower()


def calc_yolo_bbox(x: float, y: float, watermark: np.ndarray, image: np.ndarray) -> list:
    """
    Calcula bbox normalizado [cx, cy, bw, bh] formato YOLO.

    Args:
        x, y: coordenadas (esquina superior izquierda) de la marca en la imagen
        watermark: numpy array de la marca (h, w[, c])
        image: numpy array de la imagen (h, w[, c])
    """
    h_img, w_img = image.shape[:2]
    h_wm,  w_wm  = watermark.shape[:2]

    cx = (x + w_wm / 2) / w_img
    cy = (y + h_wm / 2) / h_img
    bw = w_wm / w_img
    bh = h_wm / h_img

    return [round(cx, 6), round(cy, 6), round(bw, 6), round(bh, 6)]


def image_to_base64(image_path: Path) -> str:
    """Lee el archivo de imagen tal cual del disco y lo codifica en base64."""
    return base64.b64encode(Path(image_path).read_bytes()).decode('utf-8')


def save_training_sample(
    image_path: Union[str, Path],
    watermark_path: Union[str, Path],
    watermark_folder: str,
    x: float,
    y: float,
    watermark_array: np.ndarray,
    image_array: np.ndarray,
    output_json: Union[str, Path],
) -> None:
    """
    Construye una entrada de entrenamiento y la appendea al JSON.

    Si el archivo no existe, lo crea con una lista que contiene esta entrada.
    Si está corrupto o no es lista, lo reemplaza con [entry] (no pierde data nueva).
    """
    image_path = Path(image_path)
    watermark_path = Path(watermark_path)
    output_json = Path(output_json)

    class_type = png_name_to_class(watermark_path.name)
    if not is_trainable_class(class_type):
        return  # clase ya sobreentrenada, no acumulamos más muestras

    entry = {
        "timestamp": datetime.now().isoformat(timespec='seconds'),
        "image_name": image_path.name,
        "image_base64": image_to_base64(image_path),
        "watermark_folder": watermark_folder,
        "watermark_name": watermark_path.name,
        "class_type": class_type,
        "bbox_yolo": calc_yolo_bbox(x, y, watermark_array, image_array),
    }

    # Cargar existente
    data = []
    if output_json.exists():
        try:
            data = json.loads(output_json.read_text(encoding='utf-8'))
            if not isinstance(data, list):
                data = []
        except Exception:
            data = []

    data.append(entry)

    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def remove_training_sample(current_dir:str, current_file:Path, log) -> None:
    try:
        import json as _json
        training_json = Path(os.path.dirname(current_dir)) / 'training_data.json'
        if training_json.exists():
            data = _json.loads(training_json.read_text(encoding='utf-8'))
            if isinstance(data, list):
                filtered = [e for e in data if e.get('image_name') != current_file.name]
                removed = len(data) - len(filtered)
                if removed:
                    training_json.write_text(
                        _json.dumps(filtered, ensure_ascii=False, indent=2),
                        encoding='utf-8',
                    )
                    log(f"🧹 Eliminadas {removed} entrada(s) de entrenamiento")
    except Exception as e:
        log(f"⚠️ Error limpiando training_data.json: {e}")