from typing import Any

from app.event_classifier import EventClassification
from app.object_detector import VehicleDetection


def bbox_center(bbox: dict[str, int]) -> tuple[float, float]:
    return (
        (bbox["x_min"] + bbox["x_max"]) / 2,
        (bbox["y_min"] + bbox["y_max"]) / 2,
    )


def bbox_area(bbox: dict[str, int]) -> float:
    width = max(0, bbox["x_max"] - bbox["x_min"])
    height = max(0, bbox["y_max"] - bbox["y_min"])
    return float(width * height)


def severity_from_confidence(confidence: float) -> str:
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.45:
        return "medium"
    return "low"


def object_detection_events(
    detections: list[VehicleDetection],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    detections_by_frame: dict[int, list[VehicleDetection]] = {}

    for detection in detections:
        detections_by_frame.setdefault(detection.frame_index, []).append(detection)

    for frame_index, frame_detections in detections_by_frame.items():
        if len(frame_detections) >= 5:
            avg_confidence = sum(d.confidence for d in frame_detections) / len(frame_detections)

            events.append(
                {
                    "event_type": "high_density",
                    "severity": "medium" if len(frame_detections) >= 8 else "low",
                    "confidence": round(min(avg_confidence, 0.95), 3),
                    "frame_index": frame_index,
                    "bbox": None,
                    "source": "yolo_object_detection",
                    "explanation": (
                        f"{len(frame_detections)} vehicles were detected in one sampled frame. "
                        "This supports a high-density traffic event."
                    ),
                }
            )

        for i in range(len(frame_detections)):
            for j in range(i + 1, len(frame_detections)):
                first = frame_detections[i]
                second = frame_detections[j]

                first_center = bbox_center(first.bbox)
                second_center = bbox_center(second.bbox)

                distance = (
                    (first_center[0] - second_center[0]) ** 2
                    + (first_center[1] - second_center[1]) ** 2
                ) ** 0.5

                first_area = bbox_area(first.bbox)
                second_area = bbox_area(second.bbox)
                scale = max(first_area, second_area) ** 0.5

                if scale <= 0:
                    continue

                normalized_distance = distance / scale

                if normalized_distance < 1.2:
                    confidence = round(min((first.confidence + second.confidence) / 2, 0.95), 3)

                    events.append(
                        {
                            "event_type": "unsafe_proximity",
                            "severity": "high" if normalized_distance < 0.8 else "medium",
                            "confidence": confidence,
                            "frame_index": frame_index,
                            "bbox": first.bbox,
                            "source": "yolo_object_detection",
                            "explanation": (
                                "Two vehicles appear close relative to their bounding-box scale. "
                                "This is a vehicle-detection-based proxy for unsafe proximity."
                            ),
                        }
                    )

    return events


def classifier_events(
    classifications: list[EventClassification],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    for classification in classifications:
        if classification.event_type == "normal_traffic":
            continue

        events.append(
            {
                "event_type": classification.event_type,
                "severity": severity_from_confidence(classification.confidence),
                "confidence": classification.confidence,
                "frame_index": 0,
                "bbox": None,
                "source": "clip_zero_shot_event_classifier",
                "explanation": (
                    f"The visual event classifier matched the scene to: "
                    f"'{classification.prompt}'."
                ),
            }
        )

    return events


def fuse_events(
    detections: list[VehicleDetection],
    classifications: list[EventClassification],
) -> list[dict[str, Any]]:
    events = []

    events.extend(object_detection_events(detections))
    events.extend(classifier_events(classifications))

    best_by_type: dict[str, dict[str, Any]] = {}

    for event in events:
        event_type = event["event_type"]
        current_best = best_by_type.get(event_type)

        if current_best is None or event["confidence"] > current_best["confidence"]:
            best_by_type[event_type] = event

    fused_events = list(best_by_type.values())
    fused_events.sort(key=lambda item: item["confidence"], reverse=True)

    return fused_events