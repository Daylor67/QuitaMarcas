from ultralytics import YOLO
from pathlib import Path

MODEL_PATH = Path(__file__).parent / 'best.pt'
model = YOLO(MODEL_PATH)

model.export(
    format="onnx",
    simplify=True,
    dynamic=True
)