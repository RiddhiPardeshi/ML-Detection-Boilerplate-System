import io
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageDraw

_MODEL_INSTANCE = None
_WEIGHTS_INSTANCE = None
_CATEGORIES = None


def get_detection_model():
    global _MODEL_INSTANCE, _WEIGHTS_INSTANCE, _CATEGORIES
    if _MODEL_INSTANCE is None:
        import torch
        import torchvision
        from torchvision.models.detection import (
            SSDLite320_MobileNet_V3_Large_Weights,
            ssdlite320_mobilenet_v3_large,
        )

        _WEIGHTS_INSTANCE = SSDLite320_MobileNet_V3_Large_Weights.DEFAULT
        _MODEL_INSTANCE = ssdlite320_mobilenet_v3_large(weights=_WEIGHTS_INSTANCE)
        _MODEL_INSTANCE.eval()
        _CATEGORIES = _WEIGHTS_INSTANCE.meta["categories"]
    return _MODEL_INSTANCE, _WEIGHTS_INSTANCE, _CATEGORIES


def run_object_detection(
    image_bytes: bytes,
    original_filename: str,
    upload_dir: str = "uploads",
    confidence_threshold: float = 0.3,
) -> Dict[str, Any]:
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid or unreadable image file: {e}")

    orig_width, orig_height = image.size

    import torch

    model, weights, categories = get_detection_model()
    transforms = weights.transforms()

    img_tensor = transforms(image)
    with torch.no_grad():
        predictions = model([img_tensor])[0]

    boxes = predictions["boxes"].cpu().numpy()
    scores = predictions["scores"].cpu().numpy()
    labels = predictions["labels"].cpu().numpy()

    detections: List[Dict[str, Any]] = []
    annotated_image = image.copy()
    draw = ImageDraw.Draw(annotated_image)

    scale_x = orig_width / 320.0
    scale_y = orig_height / 320.0

    colors = [
        "#f59e0b", "#10b981", "#3b82f6", "#ec4899", "#8b5cf6",
        "#ef4444", "#06b6d4", "#f97316", "#84cc16", "#6366f1"
    ]

    for idx, (box, score, label_id) in enumerate(zip(boxes, scores, labels)):
        score_val = float(score)
        if score_val < confidence_threshold:
            continue

        label_id_int = int(label_id)
        class_name = categories[label_id_int] if label_id_int < len(categories) else f"class_{label_id_int}"

        x1 = round(float(box[0]) * scale_x, 2)
        y1 = round(float(box[1]) * scale_y, 2)
        x2 = round(float(box[2]) * scale_x, 2)
        y2 = round(float(box[3]) * scale_y, 2)

        detections.append({
            "class_id": label_id_int,
            "class_name": class_name,
            "confidence": round(score_val, 4),
            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        })

        color = colors[idx % len(colors)]
        draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
        label_str = f"{class_name} {round(score_val * 100, 1)}%"

        text_bbox = draw.textbbox((x1, max(0, y1 - 18)), label_str)
        draw.rectangle(text_bbox, fill=color)
        draw.text((x1, max(0, y1 - 18)), label_str, fill="#ffffff")

    os.makedirs(upload_dir, exist_ok=True)
    unique_id = str(uuid.uuid4())[:8]
    sanitized_name = Path(original_filename).stem.replace(" ", "_")[:30]

    orig_filename = f"orig_{unique_id}_{sanitized_name}.jpg"
    annotated_filename = f"annotated_{unique_id}_{sanitized_name}.jpg"

    orig_path = os.path.join(upload_dir, orig_filename)
    annotated_path = os.path.join(upload_dir, annotated_filename)

    image.save(orig_path, "JPEG", quality=90)
    annotated_image.save(annotated_path, "JPEG", quality=90)

    return {
        "model_identifier": "ssdlite320_mobilenet_v3_large",
        "model_version": "COCO-v1",
        "detection_count": len(detections),
        "detections": detections,
        "original_image_url": f"/uploads/{orig_filename}",
        "annotated_image_url": f"/uploads/{annotated_filename}",
        "image_width": orig_width,
        "image_height": orig_height,
    }
