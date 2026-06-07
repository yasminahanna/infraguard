import json
import os
import uuid
from pathlib import Path
from time import perf_counter
from typing import Literal

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import Response


app = FastAPI(
    title="InfraGuard EEP Gateway",
    description="External Endpoint: validates requests and orchestrates Detection, Hotspot, and Recommender IEPs.",
    version="0.1.0",
)


def get_frontend_origins() -> list[str]:
    origins_text = os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://localhost:3000",
    )

    return [
        origin.strip()
        for origin in origins_text.split(",")
        if origin.strip()
    ]


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_frontend_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


def supabase_auth_required() -> bool:
    return os.getenv("REQUIRE_SUPABASE_AUTH", "false").lower() == "true"


def get_allowed_admin_emails() -> set[str]:
    emails_text = os.getenv("SUPABASE_ADMIN_EMAILS", "")

    return {
        email.strip().lower()
        for email in emails_text.split(",")
        if email.strip()
    }


async def verify_supabase_admin(authorization: str | None) -> dict:
    if not supabase_auth_required():
        return {
            "auth_required": False,
            "user": None,
        }

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing Supabase bearer token.",
        )

    access_token = authorization.replace("Bearer ", "", 1).strip()

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")

    if not supabase_url or not supabase_anon_key:
        raise HTTPException(
            status_code=500,
            detail="Supabase backend auth is enabled but Supabase configuration is missing.",
        )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "apikey": supabase_anon_key,
                    "Authorization": f"Bearer {access_token}",
                },
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Supabase token.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not verify Supabase token.",
        ) from exc

    user = response.json()
    user_email = str(user.get("email", "")).lower()

    allowed_admin_emails = get_allowed_admin_emails()

    if allowed_admin_emails and user_email not in allowed_admin_emails:
        raise HTTPException(
            status_code=403,
            detail="Authenticated user is not an approved InfraGuard admin.",
        )

    return {
        "auth_required": True,
        "user": {
            "id": user.get("id"),
            "email": user.get("email"),
        },
    }


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


@app.get("/v1/reports/latest")
async def latest_report(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    auth_info = await verify_supabase_admin(authorization)

    report_path = Path("sample_data/daily_report_sample.json")

    if not report_path.exists():
        return {
            "status": "placeholder",
            "auth": auth_info,
            "message": (
                "Latest daily report endpoint placeholder. "
                "In production, this will return the latest generated 24-hour CCTV safety report."
            ),
        }

    with report_path.open("r", encoding="utf-8") as file:
        report = json.load(file)

    report["auth"] = auth_info

    return report


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


class ReportFeedbackRequest(BaseModel):
    report_id: str = Field(..., min_length=1, max_length=200)
    road_segment_id: str = Field(..., min_length=1, max_length=100)
    verdict: Literal["accept", "reject"]
    corrected_intervention: str | None = None
    note: str | None = Field(default=None, max_length=1000)
    admin_email: str | None = None


@app.post("/v1/reports/feedback")
async def submit_report_feedback(
    payload: ReportFeedbackRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    await verify_supabase_admin(authorization)
    recommender_url = os.getenv("RECOMMENDER_IEP_URL", "http://recommender-iep:8003")
    async with httpx.AsyncClient(timeout=15) as client:
        return await post_json(
            client=client,
            url=f"{recommender_url}/v1/reports/feedback",
            payload=payload.model_dump(),
            service_name="recommender_iep",
        )


@app.get("/v1/reports/feedback")
async def list_report_feedback(
    limit: int = 50,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    await verify_supabase_admin(authorization)
    recommender_url = os.getenv("RECOMMENDER_IEP_URL", "http://recommender-iep:8003")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.get(
            f"{recommender_url}/v1/reports/feedback", params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()