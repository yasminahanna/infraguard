from time import perf_counter
from typing import Literal

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import Response


app = FastAPI(
    title="InfraGuard Hotspot IEP",
    description="Internal Endpoint 2: scores road segments for emerging traffic-risk hotspots.",
    version="0.1.0",
)

REQUEST_COUNT = Counter(
    "hotspot_requests_total",
    "Total number of hotspot scoring requests.",
)

LATENCY = Histogram(
    "hotspot_latency_seconds",
    "Hotspot scoring latency in seconds.",
)

RISK_SCORE_HISTOGRAM = Histogram(
    "hotspot_score",
    "Distribution of computed hotspot risk scores.",
)

HOTSPOT_LEVEL_COUNT = Counter(
    "hotspot_level_total",
    "Count of hotspot risk levels.",
    ["risk_level"],
)


class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class RecklessEvent(BaseModel):
    event_type: str
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(..., ge=0, le=1)
    frame_index: int = Field(..., ge=0)
    explanation: str | None = None


class HotspotRequest(BaseModel):
    camera_id: str = Field(..., min_length=2, max_length=100)
    road_segment_id: str = Field(..., min_length=2, max_length=100)
    timestamp: str
    location: Location
    events: list[RecklessEvent] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class HotspotEvidence(BaseModel):
    label: str
    value: str


class HotspotResponse(BaseModel):
    service: str
    status: Literal["completed"]
    road_segment_id: str
    hotspot_score: float = Field(..., ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]
    trend: Literal["stable", "increasing", "decreasing"]
    cluster_id: str
    evidence: list[HotspotEvidence]
    latency_ms: int


def severity_weight(severity: str) -> float:
    if severity == "high":
        return 1.0
    if severity == "medium":
        return 0.65
    return 0.35


def compute_hotspot_score(events: list[RecklessEvent], metadata: dict) -> float:
    if not events:
        return 0.05

    weighted_event_score = sum(
        severity_weight(event.severity) * event.confidence for event in events
    )

    normalized_event_score = min(weighted_event_score / 4.0, 1.0)

    time_of_day = str(metadata.get("time_of_day", "unknown")).lower()
    weather = str(metadata.get("weather", "unknown")).lower()

    time_multiplier = 1.15 if time_of_day in {"night", "evening", "peak"} else 1.0
    weather_multiplier = 1.10 if weather in {"rain", "fog", "storm"} else 1.0

    score = normalized_event_score * time_multiplier * weather_multiplier
    return round(min(score, 1.0), 3)


def risk_level_from_score(score: float) -> Literal["low", "medium", "high"]:
    if score >= 0.70:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def trend_from_metadata(metadata: dict, event_count: int) -> Literal["stable", "increasing", "decreasing"]:
    historical_average = float(metadata.get("historical_avg_events", 2.0))

    if event_count > historical_average * 1.25:
        return "increasing"
    if event_count < historical_average * 0.75:
        return "decreasing"
    return "stable"


@app.get("/health")
def health() -> dict:
    return {"service": "hotspot_iep", "status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/score", response_model=HotspotResponse)
def score_hotspot(payload: HotspotRequest) -> HotspotResponse:
    start = perf_counter()
    REQUEST_COUNT.inc()

    hotspot_score = compute_hotspot_score(payload.events, payload.metadata)
    risk_level = risk_level_from_score(hotspot_score)
    trend = trend_from_metadata(payload.metadata, len(payload.events))

    cluster_id = f"cluster_{abs(hash(payload.road_segment_id)) % 1000:03d}"

    evidence = [
        HotspotEvidence(
            label="event_count",
            value=str(len(payload.events)),
        ),
        HotspotEvidence(
            label="weighted_risk_score",
            value=str(hotspot_score),
        ),
        HotspotEvidence(
            label="trend_basis",
            value=f"Compared current event count to historical average of {payload.metadata.get('historical_avg_events', 2.0)}",
        ),
    ]

    RISK_SCORE_HISTOGRAM.observe(hotspot_score)
    HOTSPOT_LEVEL_COUNT.labels(risk_level=risk_level).inc()

    latency_ms = int((perf_counter() - start) * 1000)
    LATENCY.observe(latency_ms / 1000)

    return HotspotResponse(
        service="hotspot_iep",
        status="completed",
        road_segment_id=payload.road_segment_id,
        hotspot_score=hotspot_score,
        risk_level=risk_level,
        trend=trend,
        cluster_id=cluster_id,
        evidence=evidence,
        latency_ms=latency_ms,
    )