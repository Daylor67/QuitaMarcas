"""
Detección automática de marcas de agua usando ONNX Runtime (sin ultralytics).
"""
import re
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import numpy as np
import cv2

MODEL_PATH = Path(__file__).parent / 'best.onnx'
DEFAULT_CONF_THRESHOLD = 0.90
NMS_IOU_THRESHOLD = 0.45

_model_cache = None
_model_meta = None  # guarda input shape y class names


def _load_model():
    global _model_cache, _model_meta
    if _model_cache is not None:
        return _model_cache, _model_meta

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Modelo ONNX no encontrado: {MODEL_PATH}")

    import onnxruntime as ort

    sess = ort.InferenceSession(
        str(MODEL_PATH),
        providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
    )

    # Input shape: [1, 3, H, W]  (típicamente 640x640)
    input_shape = sess.get_inputs()[0].shape  # e.g. [1, 3, 640, 640]
    model_h = input_shape[2] if isinstance(input_shape[2], int) else 640
    model_w = input_shape[3] if isinstance(input_shape[3], int) else 640

    # Leer nombres de clases desde los metadatos del modelo (exportados por ultralytics)
    meta = sess.get_modelmeta().custom_metadata_map
    import ast
    names_raw = meta.get("names", "{}")
    names_dict = ast.literal_eval(names_raw)          # {0: 'banner', 1: 'logo', ...}
    class_names = {int(k): v for k, v in names_dict.items()}

    _model_meta = {"h": model_h, "w": model_w, "names": class_names}
    _model_cache = sess
    return _model_cache, _model_meta


# ---------------------------------------------------------------------------
# Preprocesamiento: letterbox (igual que ultralytics internamente)
# ---------------------------------------------------------------------------

def _letterbox(
    image: np.ndarray,
    new_shape: Tuple[int, int] = (640, 640),
    color: Tuple[int, int, int] = (114, 114, 114),
) -> Tuple[np.ndarray, float, Tuple[int, int]]:
    """
    Redimensiona manteniendo aspect ratio y rellena con gris.
    Devuelve (imagen_resized, scale, (pad_w, pad_h)).
    """
    h, w = image.shape[:2]
    new_h, new_w = new_shape

    scale = min(new_w / w, new_h / h)
    unpad_w = round(w * scale)
    unpad_h = round(h * scale)

    resized = cv2.resize(image, (unpad_w, unpad_h), interpolation=cv2.INTER_LINEAR)

    pad_w = (new_w - unpad_w) / 2
    pad_h = (new_h - unpad_h) / 2
    top, bottom = round(pad_h - 0.1), round(pad_h + 0.1)
    left, right  = round(pad_w - 0.1), round(pad_w + 0.1)

    padded = cv2.copyMakeBorder(resized, top, bottom, left, right,
                                cv2.BORDER_CONSTANT, value=color)
    return padded, scale, (left, top)


def _preprocess(image_bgr: np.ndarray, model_h: int, model_w: int):
    padded, scale, pad = _letterbox(image_bgr, (model_h, model_w))
    rgb = cv2.cvtColor(padded, cv2.COLOR_BGR2RGB)
    tensor = rgb.astype(np.float32) / 255.0          # [H, W, 3]
    tensor = np.transpose(tensor, (2, 0, 1))          # [3, H, W]
    tensor = np.expand_dims(tensor, axis=0)           # [1, 3, H, W]
    return tensor, scale, pad


# ---------------------------------------------------------------------------
# Postprocesamiento: NMS manual
# ---------------------------------------------------------------------------

def _xywh_to_xyxy(boxes: np.ndarray) -> np.ndarray:
    """Convierte cx,cy,w,h → x1,y1,x2,y2."""
    out = np.empty_like(boxes)
    out[:, 0] = boxes[:, 0] - boxes[:, 2] / 2
    out[:, 1] = boxes[:, 1] - boxes[:, 3] / 2
    out[:, 2] = boxes[:, 0] + boxes[:, 2] / 2
    out[:, 3] = boxes[:, 1] + boxes[:, 3] / 2
    return out


def _nms(boxes_xyxy: np.ndarray, scores: np.ndarray, iou_thr: float) -> List[int]:
    x1, y1, x2, y2 = boxes_xyxy[:, 0], boxes_xyxy[:, 1], boxes_xyxy[:, 2], boxes_xyxy[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter + 1e-9)
        order = order[1:][iou <= iou_thr]
    return keep


def _postprocess(
    raw_output: np.ndarray,
    scale: float,
    pad: Tuple[int, int],
    orig_shape: Tuple[int, int],
    conf_thr: float,
    iou_thr: float,
    class_names: Dict[int, str],
) -> List[Dict]:
    """
    raw_output: [1, 4+num_classes, num_anchors]  → shape (1, 9, anchors)
    """
    pred = raw_output[0]          # [9, num_anchors]
    pred = pred.T                 # [num_anchors, 9]  ← ahora cada fila es una detección

    boxes_xywh  = pred[:, :4]     # cx, cy, w, h
    class_scores = pred[:, 4:]    # [num_anchors, 5]

    cls_ids = class_scores.argmax(axis=1)
    confs   = class_scores[np.arange(len(cls_ids)), cls_ids]

    mask = confs >= conf_thr
    if not mask.any():
        return []

    boxes_xywh = boxes_xywh[mask]
    confs = confs[mask]
    cls_ids = cls_ids[mask]

    boxes_xyxy = _xywh_to_xyxy(boxes_xywh)
    keep = _nms(boxes_xyxy, confs, iou_thr)

    pad_w, pad_h = pad
    orig_h, orig_w = orig_shape
    detections = []
    for idx in keep:
        x1, y1, x2, y2 = boxes_xyxy[idx]
        # Revertir padding y escala
        x1 = (x1 - pad_w) / scale
        y1 = (y1 - pad_h) / scale
        x2 = (x2 - pad_w) / scale
        y2 = (y2 - pad_h) / scale
        # Clampear al tamaño original
        x1, x2 = np.clip([x1, x2], 0, orig_w)
        y1, y2 = np.clip([y1, y2], 0, orig_h)

        detections.append({
            "class_type": class_names.get(int(cls_ids[idx]), str(cls_ids[idx])),
            "confidence": float(confs[idx]),
            "bbox": (float(x1), float(y1), float(x2), float(y2)),
        })

    detections.sort(key=lambda d: d["confidence"], reverse=True)
    return detections


# ---------------------------------------------------------------------------
# API pública (misma interfaz que antes)
# ---------------------------------------------------------------------------

def detect_watermarks(image_bgr: np.ndarray, conf_threshold: float = DEFAULT_CONF_THRESHOLD) -> List[Dict]:
    sess, meta = _load_model()
    model_h, model_w = meta["h"], meta["w"]

    tensor, scale, pad = _preprocess(image_bgr, model_h, model_w)

    input_name = sess.get_inputs()[0].name
    raw = sess.run(None, {input_name: tensor})[0]

    return _postprocess(
        raw, scale, pad,
        orig_shape=image_bgr.shape[:2],
        conf_thr=conf_threshold,
        iou_thr=NMS_IOU_THRESHOLD,
        class_names=meta["names"],
    )


# ---------------------------------------------------------------------------
# Helpers sin cambios (resolve_png_for_class, _candidate_folders)
# ---------------------------------------------------------------------------

def _candidate_folders(primary: Path) -> List[Path]:
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