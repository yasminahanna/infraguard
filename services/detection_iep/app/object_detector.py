from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from ultralytics import YOLO


VEHICLE_CLASS_NAMES = {
    "car",
    "motorcycle",
    "bus",
    "truck",
}


@dataclass
class VehicleDetection:
    class_name: str
    confidence: float
    bbox: dict[str, int]
    frame_index: int


@lru_cache(maxsize=1)
def get_yolo_model() -> YOLO:
    return YOLO("yolov8n.pt")


def detect_vehicles_in_frame(
    image: np.ndarray,
    frame_index: int,
    confidence_threshold: float = 0.35,
) -> list[VehicleDetection]:
    model = get_yolo_model()

    results = model.predict(
        source=image,
        conf=confidence_threshold,
        verbose=False,
    )

    detections: list[VehicleDetection] = []

    if not results:
        return detections

    result = results[0]
    names: dict[int, str] = result.names

    for box in result.boxes:
        class_id = int(box.cls[0].item())
        class_name = names[class_id]

        if class_name not in VEHICLE_CLASS_NAMES:
            continue

        confidence = float(box.conf[0].item())
        x_min, y_min, x_max, y_max = box.xyxy[0].tolist()

        detections.append(
            VehicleDetection(
                class_name=class_name,
                confidence=round(confidence, 3),
                frame_index=frame_index,
                bbox={
                    "x_min": int(x_min),
                    "y_min": int(y_min),
                    "x_max": int(x_max),
                    "y_max": int(y_max),
                },
            )
        )

    return detections