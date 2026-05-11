"""
Convierte training_data.json (recopilado por slideshow_viewer) a un dataset YOLOv8.

Uso:
    python -m WatermarkRemove.training.convert_to_yolo

Genera:
    WatermarkRemove/training/dataset/
        images/train/   ← 80% imágenes (jpg/png decodificadas)
        images/val/     ← 20%
        labels/train/   ← .txt YOLO (una línea por bbox)
        labels/val/
        dataset.yaml    ← config para Ultralytics
"""
import os
import sys
import json
import base64
import random
from pathlib import Path
from collections import defaultdict


HERE = Path(__file__).resolve().parent
TRAINING_JSON = HERE.parent / 'training_data.json'
DATASET_DIR = HERE / 'dataset'
TRAIN_RATIO = 0.8


def main():
    if not TRAINING_JSON.exists():
        print(f"ERROR: no existe {TRAINING_JSON}")
        sys.exit(1)

    data = json.loads(TRAINING_JSON.read_text(encoding='utf-8'))
    if not data:
        print("ERROR: training_data.json vacío")
        sys.exit(1)

    print(f"Total muestras: {len(data)}")

    # Indexar clases (alfabético = orden estable)
    classes = sorted({entry['class_type'] for entry in data})
    cls_to_id = {c: i for i, c in enumerate(classes)}
    print(f"Clases ({len(classes)}): {classes}")

    # Conteo por clase
    counts = defaultdict(int)
    for entry in data:
        counts[entry['class_type']] += 1
    for c in classes:
        print(f"  {c}: {counts[c]}")

    # Agrupar muestras por imagen (puede haber múltiples bboxes en la misma img)
    by_image = defaultdict(list)
    for entry in data:
        by_image[entry['image_name']].append(entry)

    # Shuffle determinístico para split reproducible
    image_names = sorted(by_image.keys())
    random.seed(42)
    random.shuffle(image_names)

    n_train = int(len(image_names) * TRAIN_RATIO)
    train_set = set(image_names[:n_train])
    val_set = set(image_names[n_train:])

    print(f"Split: {len(train_set)} train / {len(val_set)} val (imágenes únicas)")

    # Limpiar/crear directorios
    for sub in ('images/train', 'images/val', 'labels/train', 'labels/val'):
        d = DATASET_DIR / sub
        d.mkdir(parents=True, exist_ok=True)

    # Procesar
    written = 0
    for img_name, entries in by_image.items():
        split = 'train' if img_name in train_set else 'val'

        # Decodificar y guardar imagen (todas las entries del mismo img comparten base64)
        img_bytes = base64.b64decode(entries[0]['image_base64'])
        img_path = DATASET_DIR / 'images' / split / img_name
        img_path.write_bytes(img_bytes)

        # Label: una línea por bbox
        label_lines = []
        for entry in entries:
            cls_id = cls_to_id[entry['class_type']]
            cx, cy, bw, bh = entry['bbox_yolo']
            label_lines.append(f"{cls_id} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")

        label_path = DATASET_DIR / 'labels' / split / f"{Path(img_name).stem}.txt"
        label_path.write_text("\n".join(label_lines) + "\n", encoding='utf-8')
        written += 1

    print(f"Imágenes escritas: {written}")

    # dataset.yaml
    yaml_content = (
        f"# Generado por convert_to_yolo.py\n"
        f"path: {DATASET_DIR.as_posix()}\n"
        f"train: images/train\n"
        f"val: images/val\n\n"
        f"names:\n"
    )
    for i, c in enumerate(classes):
        yaml_content += f"  {i}: {c}\n"

    yaml_path = DATASET_DIR / 'dataset.yaml'
    yaml_path.write_text(yaml_content, encoding='utf-8')
    print(f"\n✅ Dataset listo en: {DATASET_DIR}")
    print(f"📄 Config: {yaml_path}")


if __name__ == "__main__":
    main()
