from time import perf_counter
from typing import Literal

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import Response


app = FastAPI(
    title="InfraGuard Detection IEP",
    description="Internal Endpoint 1: detects reckless driving behavior events from camera frames.",
    version="0.1.0",
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
    "Total detected reckless-driving events.",
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
    ]
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(..., ge=0, le=1)
    frame_index: int = Field(..., ge=0)
    bbox: BoundingBox | None = None
    explanation: str


class DetectionResponse(BaseModel):
    service: str
    status: Literal["completed"]
    vehicle_count: int
    events: list[RecklessEvent]
    mean_confidence: float = Field(..., ge=0, le=1)
    latency_ms: int


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

    # Day 1 placeholder:
    # Later, this function will decode frames, run YOLO/OpenCV, and infer behavior.
    frame_count = max(len(payload.frames_base64), 1)

    events = [
        RecklessEvent(
            event_type="unsafe_proximity",
            severity="medium",
            confidence=0.74,
            frame_index=0,
            bbox=BoundingBox(x_min=100, y_min=80, x_max=220, y_max=170),
            explanation="Placeholder event: vehicles appear close within the sampled region.",
        )
    ]

    if frame_count >= 3:
        events.append(
            RecklessEvent(
                event_type="high_density",
                severity="low",
                confidence=0.68,
                frame_index=1,
                bbox=None,
                explanation="Placeholder event: multiple frames indicate possible traffic density.",
            )
        )

    for event in events:
        EVENT_COUNT.labels(event_type=event.event_type).inc()

    latency_ms = int((perf_counter() - start) * 1000)
    LATENCY.observe(latency_ms / 1000)

    return DetectionResponse(
        service="detection_iep",
        status="completed",
        vehicle_count=max(2, frame_count * 2),
        events=events,
        mean_confidence=round(sum(e.confidence for e in events) / len(events), 3),
        latency_ms=latency_ms,
    )