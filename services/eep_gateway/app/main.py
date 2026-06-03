import os
import uuid
from time import perf_counter
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import Response


app = FastAPI(
    title="InfraGuard EEP Gateway",
    description="External Endpoint: validates requests and orchestrates Detection, Hotspot, and Recommender IEPs.",
    version="0.1.0",
)

REQUEST_COUNT = Counter(
    "eep_requests_total",
    "Total number of EEP analyze requests.",
)

LATENCY = Histogram(
    "eep_latency_seconds",
    "EEP end-to-end request latency in seconds.",
)

IEP_FAILURE_COUNT = Counter(
    "eep_iep_failures_total",
    "Number of downstream IEP failures.",
    ["service"],
)


class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class AnalyzeRequest(BaseModel):
    camera_id: str = Field(..., min_length=2, max_length=100)
    road_segment_id: str = Field(..., min_length=2, max_length=100)
    timestamp: str
    location: Location
    frames_base64: list[str] = Field(..., min_length=1, max_length=8)
    metadata: dict = Field(default_factory=dict)


class AnalyzeResponse(BaseModel):
    request_id: str
    status: Literal["completed"]
    detection: dict
    hotspot: dict
    recommendation: dict
    fallbacks_used: list[str]
    latency_ms: int


def require_api_key(x_api_key: str | None) -> None:
    expected_api_key = os.getenv("API_KEY", "dev-secret-key")

    if x_api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


async def post_json(
    client: httpx.AsyncClient,
    url: str,
    payload: dict,
    service_name: str,
) -> dict:
    try:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException as exc:
        IEP_FAILURE_COUNT.labels(service=service_name).inc()
        raise HTTPException(
            status_code=504,
            detail=f"{service_name} timed out.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        IEP_FAILURE_COUNT.labels(service=service_name).inc()
        raise HTTPException(
            status_code=502,
            detail=f"{service_name} returned an error: {exc.response.text}",
        ) from exc
    except httpx.RequestError as exc:
        IEP_FAILURE_COUNT.labels(service=service_name).inc()
        raise HTTPException(
            status_code=502,
            detail=f"{service_name} is unreachable: {str(exc)}",
        ) from exc


@app.get("/health")
def health() -> dict:
    return {"service": "eep_gateway", "status": "ok"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/v1/analyze", response_model=AnalyzeResponse)
async def analyze(
    payload: AnalyzeRequest,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> AnalyzeResponse:
    start = perf_counter()
    REQUEST_COUNT.inc()
    require_api_key(x_api_key)

    request_id = f"req_{uuid.uuid4().hex[:12]}"
    fallbacks_used: list[str] = []

    detection_url = os.getenv("DETECTION_IEP_URL", "http://detection-iep:8001")
    hotspot_url = os.getenv("HOTSPOT_IEP_URL", "http://hotspot-iep:8002")
    recommender_url = os.getenv("RECOMMENDER_IEP_URL", "http://recommender-iep:8003")

    timeout_seconds = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "180"))

    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        detection_result = await post_json(
            client=client,
            url=f"{detection_url}/detect",
            payload=payload.model_dump(),
            service_name="detection_iep",
        )

        hotspot_payload = {
            "camera_id": payload.camera_id,
            "road_segment_id": payload.road_segment_id,
            "timestamp": payload.timestamp,
            "location": payload.location.model_dump(),
            "events": detection_result["events"],
            "metadata": payload.metadata,
        }

        hotspot_result = await post_json(
            client=client,
            url=f"{hotspot_url}/score",
            payload=hotspot_payload,
            service_name="hotspot_iep",
        )

        event_types = [event["event_type"] for event in detection_result["events"]]

        recommender_payload = {
            "camera_id": payload.camera_id,
            "road_segment_id": payload.road_segment_id,
            "detection": {
                "vehicle_count": detection_result["vehicle_count"],
                "events_detected": len(detection_result["events"]),
                "mean_confidence": detection_result["mean_confidence"],
                "event_types": event_types,
            },
            "hotspot": {
                "hotspot_score": hotspot_result["hotspot_score"],
                "risk_level": hotspot_result["risk_level"],
                "trend": hotspot_result["trend"],
                "cluster_id": hotspot_result["cluster_id"],
                "evidence": hotspot_result["evidence"],
            },
            "metadata": payload.metadata,
        }

        try:
            recommender_result = await post_json(
                client=client,
                url=f"{recommender_url}/recommend",
                payload=recommender_payload,
                service_name="recommender_iep",
            )
        except HTTPException as exc:
            fallbacks_used.append("recommender_service_unavailable")

            recommender_result = {
                "service": "recommender_iep",
                "status": "fallback",
                "provider": "emergency_static_fallback",
                "model": "none",
                "recommendation": {
                    "primary_intervention": "add_warning_signage",
                    "priority": hotspot_result["risk_level"],
                    "supporting_actions": [
                        "continue_monitoring",
                        "review_segment_manually",
                    ],
                    "explanation": (
                        "The LLM recommender service was unavailable. InfraGuard returned an "
                        "emergency conservative response so the deployed system remains functional. "
                        "This is not the final recommendation model; the intended fallback will be "
                        "a classifier trained on real public traffic or crash data."
                    ),
                    "evidence_used": [
                        f"hotspot_score={hotspot_result['hotspot_score']}",
                        f"risk_level={hotspot_result['risk_level']}",
                        f"trend={hotspot_result['trend']}",
                    ],
                    "confidence": 0.25,
                },
                "retrieved_context": [],
                "fallback_used": True,
                "fallback_reason": exc.detail,
                "latency_ms": 0,
            }

    latency_ms = int((perf_counter() - start) * 1000)
    LATENCY.observe(latency_ms / 1000)

    return AnalyzeResponse(
        request_id=request_id,
        status="completed",
        detection=detection_result,
        hotspot=hotspot_result,
        recommendation=recommender_result,
        fallbacks_used=fallbacks_used,
        latency_ms=latency_ms,
    )