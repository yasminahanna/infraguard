from time import perf_counter
from typing import Literal

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import Response

from app.event_classifier import summarize_classifications, classify_frame_events
from app.event_fusion import fuse_events
from app.frame_utils import cv2_to_pil, decode_base64_frame
from app.object_detector import detect_vehicles_in_frame


app = FastAPI(
    title="InfraGuard Detection IEP",
    description="Internal Endpoint 1: detects traffic-risk events using object detection and visual event classification.",
    version="0.3.0",
)

REQUEST_COUNT = Counter(
    "detection_requests_total",
    "Total number of detection requests.",
)

LATENCY = Histogram(
    "detection_latency_seconds",
    "Detection service latency in seconds.",
)

EVENT_COUNT = Counter(
    "detection_events_total",
    "Total detected traffic-risk events.",
    ["event_type"],
)

VEHICLE_COUNT_HISTOGRAM = Histogram(
    "detection_vehicle_count",
    "Distribution of detected vehicle counts.",
)

CONFIDENCE_HISTOGRAM = Histogram(
    "detection_mean_confidence",
    "Distribution of detection mean confidence.",
)

CLASSIFIER_EVENT_COUNT = Counter(
    "detection_classifier_events_total",
    "Total events proposed by the visual event classifier.",
    ["event_type"],
)


class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class DetectionRequest(BaseModel):
    camera_id: str = Field(..., min_length=2, max_length=100)
    road_segment_id: str = Field(..., min_length=2, max_length=100)
    timestamp: str
    location: Location
    frames_base64: list[str] = Field(default_factory=list, max_length=8)
    metadata: dict = Field(default_factory=dict)


class BoundingBox(BaseModel):
    x_min: int
    y_min: int
    x_max: int
    y_max: int


class RecklessEvent(BaseModel):
    event_type: Literal[
        "unsafe_proximity",
        "lane_region_violation",
        "possible_speeding",
        "wrong_direction_proxy",
        "high_density",
        "reckless_driving",
        "phone_usage_possible",
        "lane_violation",
        "normal_traffic",
    ]
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(..., ge=0, le=1)
    frame_index: int = Field(..., ge=0)
    bbox: BoundingBox | None = None
    source: Literal[
        "demo_fallback",
        "yolo_object_detection",
        "clip_zero_shot_event_classifier",
    ]
    explanation: str


class VehicleObject(BaseModel):
    class_name: str
    confidence: float = Field(..., ge=0, le=1)
    frame_index: int = Field(..., ge=0)
    bbox: BoundingBox


class EventClassificationOutput(BaseModel):
    event_type: str
    confidence: float = Field(..., ge=0, le=1)
    prompt: str


class DetectionResponse(BaseModel):
    service: str
    status: Literal["completed"]
    vehicle_count: int
    vehicles: list[VehicleObject]
    events: list[RecklessEvent]
    event_classifications: list[EventClassificationOutput]
    mean_confidence: float = Field(..., ge=0, le=1)
    models_used: list[str]
    decoded_real_frames: bool
    notes: list[str]
    latency_ms: int


def demo_fallback_events(frame_count: int) -> tuple[list[VehicleObject], list[RecklessEvent], float]:
    vehicles = [
        VehicleObject(
            class_name="car",
            confidence=0.70,
            frame_index=0,
            bbox=BoundingBox(x_min=100, y_min=80, x_max=220, y_max=170),
        ),
        VehicleObject(
            class_name="car",
            confidence=0.68,
            frame_index=0,
            bbox=BoundingBox(x_min=230, y_min=90, x_max=350, y_max=180),
        ),
    ]

    events = [
        RecklessEvent(
            event_type="unsafe_proximity",
            severity="medium",
            confidence=0.69,
            frame_index=0,
            bbox=BoundingBox(x_min=100, y_min=80, x_max=220, y_max=170),
            source="demo_fallback",
            explanation=(
                "Demo fallback event: frames were not valid base64 images, so the service returned "
                "a controlled placeholder event for integration testing."
            ),
        )
    ]

    if frame_count >= 3:
        events.append(
            RecklessEvent(
                event_type="high_density",
                severity="low",
                confidence=0.62,
                frame_index=1,
                bbox=None,
                source="demo_fallback",
                explanation=(
                    "Demo fallback event: multiple invalid test frames were provided, so the service "
                    "returned a controlled density placeholder for integration testing."
                ),
            )
        )

    return vehicles, events, 0.69


@app.get("/health")
def health() -> dict:
    return {"service": "detection_iep", "status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/detect", response_model=DetectionResponse)
def detect_reckless_behavior(payload: DetectionRequest) -> DetectionResponse:
    start = perf_counter()
    REQUEST_COUNT.inc()

    notes: list[str] = []
    all_vehicles: list[VehicleObject] = []
    classifications_by_frame = []
    decoded_real_frames = False

    for frame_index, frame_base64 in enumerate(payload.frames_base64):
        image = decode_base64_frame(frame_base64)

        if image is None:
            continue

        decoded_real_frames = True

        frame_detections = detect_vehicles_in_frame(
            image=image,
            frame_index=frame_index,
        )

        for detection in frame_detections:
            all_vehicles.append(
                VehicleObject(
                    class_name=detection.class_name,
                    confidence=detection.confidence,
                    frame_index=detection.frame_index,
                    bbox=BoundingBox(**detection.bbox),
                )
            )

        pil_image = cv2_to_pil(image)
        frame_classifications = classify_frame_events(pil_image)
        classifications_by_frame.append(frame_classifications)

    if decoded_real_frames:
        summarized_classifications = summarize_classifications(classifications_by_frame)

        for classification in summarized_classifications:
            CLASSIFIER_EVENT_COUNT.labels(event_type=classification.event_type).inc()

        raw_vehicle_detections = [
            type(
                "VehicleDetectionLike",
                (),
                {
                    "class_name": vehicle.class_name,
                    "confidence": vehicle.confidence,
                    "bbox": vehicle.bbox.model_dump(),
                    "frame_index": vehicle.frame_index,
                },
            )()
            for vehicle in all_vehicles
        ]

        raw_events = fuse_events(
            detections=raw_vehicle_detections,
            classifications=summarized_classifications,
        )

        events = [
            RecklessEvent(
                event_type=event["event_type"],
                severity=event["severity"],
                confidence=event["confidence"],
                frame_index=event["frame_index"],
                bbox=BoundingBox(**event["bbox"]) if event["bbox"] is not None else None,
                source=event["source"],
                explanation=event["explanation"],
            )
            for event in raw_events
        ]

        event_classifications = [
            EventClassificationOutput(
                event_type=classification.event_type,
                confidence=classification.confidence,
                prompt=classification.prompt,
            )
            for classification in summarized_classifications
        ]

        confidence_values = [vehicle.confidence for vehicle in all_vehicles]
        confidence_values.extend([classification.confidence for classification in summarized_classifications])

        if confidence_values:
            mean_confidence = round(sum(confidence_values) / len(confidence_values), 3)
        else:
            mean_confidence = 0.0
            notes.append("No vehicles or event classifications were detected in decoded frames.")
    else:
        frame_count = max(len(payload.frames_base64), 1)
        all_vehicles, events, mean_confidence = demo_fallback_events(frame_count)
        event_classifications = []
        notes.append(
            "No valid base64 image frames were decoded. Used controlled demo fallback for integration testing."
        )

    for event in events:
        EVENT_COUNT.labels(event_type=event.event_type).inc()

    VEHICLE_COUNT_HISTOGRAM.observe(len(all_vehicles))
    CONFIDENCE_HISTOGRAM.observe(mean_confidence)

    latency_ms = int((perf_counter() - start) * 1000)
    LATENCY.observe(latency_ms / 1000)

    models_used = ["demo_fallback"]

    if decoded_real_frames:
        models_used = [
            "yolov8n_vehicle_detector",
            "clip_zero_shot_event_classifier",
        ]

    return DetectionResponse(
        service="detection_iep",
        status="completed",
        vehicle_count=len(all_vehicles),
        vehicles=all_vehicles,
        events=events,
        event_classifications=event_classifications,
        mean_confidence=mean_confidence,
        models_used=models_used,
        decoded_real_frames=decoded_real_frames,
        notes=notes,
        latency_ms=latency_ms,
    )