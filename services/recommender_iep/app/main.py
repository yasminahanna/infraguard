import json
import os
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException
from openai import OpenAI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import Response


app = FastAPI(
    title="InfraGuard LLM Recommender IEP",
    description="Internal Endpoint 3: uses an LLM to recommend road safety interventions from detection and hotspot evidence.",
    version="0.1.0",
)

REQUEST_COUNT = Counter(
    "recommender_requests_total",
    "Total number of recommendation requests.",
)

LATENCY = Histogram(
    "recommender_latency_seconds",
    "Recommendation service latency in seconds.",
)

LLM_FAILURE_COUNT = Counter(
    "recommender_llm_failures_total",
    "Number of LLM call or validation failures.",
    ["failure_type"],
)

RECOMMENDATION_COUNT = Counter(
    "recommendation_type_total",
    "Count of recommended primary interventions.",
    ["intervention"],
)


class HotspotEvidence(BaseModel):
    label: str
    value: str


class HotspotSummary(BaseModel):
    hotspot_score: float = Field(..., ge=0, le=1)
    risk_level: Literal["low", "medium", "high"]
    trend: Literal["stable", "increasing", "decreasing"]
    cluster_id: str
    evidence: list[HotspotEvidence] = Field(default_factory=list)


class DetectionSummary(BaseModel):
    vehicle_count: int = Field(..., ge=0)
    events_detected: int = Field(..., ge=0)
    mean_confidence: float = Field(..., ge=0, le=1)
    event_types: list[str] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    camera_id: str = Field(..., min_length=2, max_length=100)
    road_segment_id: str = Field(..., min_length=2, max_length=100)
    detection: DetectionSummary
    hotspot: HotspotSummary
    metadata: dict = Field(default_factory=dict)


class Recommendation(BaseModel):
    primary_intervention: Literal[
        "install_speed_camera",
        "add_warning_signage",
        "repaint_lane_markings",
        "improve_lighting",
        "add_speed_bumps",
        "increase_enforcement",
        "review_signal_timing",
        "redesign_intersection",
        "no_action_monitor",
    ]
    priority: Literal["low", "medium", "high"]
    supporting_actions: list[str] = Field(..., min_length=1, max_length=5)
    explanation: str = Field(..., min_length=20, max_length=1000)
    evidence_used: list[str] = Field(..., min_length=1, max_length=8)
    confidence: float = Field(..., ge=0, le=1)


class RecommendationResponse(BaseModel):
    service: str
    status: Literal["completed"]
    provider: Literal["openai"]
    model: str
    recommendation: Recommendation
    latency_ms: int


def build_prompt(payload: RecommendationRequest) -> str:
    return f"""
You are an AI road-safety infrastructure advisor for a smart-city engineering team.

Your task:
Recommend road safety interventions using ONLY the evidence provided.

You must return STRICT JSON only. Do not include markdown. Do not include explanations outside JSON.

Allowed values:

primary_intervention must be one of:
- install_speed_camera
- add_warning_signage
- repaint_lane_markings
- improve_lighting
- add_speed_bumps
- increase_enforcement
- review_signal_timing
- redesign_intersection
- no_action_monitor

priority must be one of:
- low
- medium
- high

Required JSON schema:
{{
  "primary_intervention": "one allowed value",
  "priority": "low | medium | high",
  "supporting_actions": ["1 to 5 short actions"],
  "explanation": "clear explanation based only on the evidence",
  "evidence_used": ["specific evidence strings used"],
  "confidence": 0.0
}}

Evidence:
camera_id: {payload.camera_id}
road_segment_id: {payload.road_segment_id}

Detection summary:
- vehicle_count: {payload.detection.vehicle_count}
- events_detected: {payload.detection.events_detected}
- mean_confidence: {payload.detection.mean_confidence}
- event_types: {payload.detection.event_types}

Hotspot summary:
- hotspot_score: {payload.hotspot.hotspot_score}
- risk_level: {payload.hotspot.risk_level}
- trend: {payload.hotspot.trend}
- cluster_id: {payload.hotspot.cluster_id}
- hotspot_evidence: {[item.model_dump() for item in payload.hotspot.evidence]}

Road metadata:
{json.dumps(payload.metadata, indent=2)}

Decision rules:
- If risk_level is high and speeding-like behavior exists, strongly consider install_speed_camera or increase_enforcement.
- If lane violations exist, strongly consider repaint_lane_markings.
- If low visibility conditions exist, consider improve_lighting.
- If hotspot_score is low, consider no_action_monitor.
- Do not invent sensor evidence, crash counts, or road facts not provided.
""".strip()


def call_openai_recommender(payload: RecommendationRequest) -> Recommendation:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    timeout_seconds = float(os.getenv("LLM_TIMEOUT_SECONDS", "12"))

    if not api_key:
        LLM_FAILURE_COUNT.labels(failure_type="missing_api_key").inc()
        raise HTTPException(
            status_code=500,
            detail="OPENAI_API_KEY is missing. Add it to .env before running the recommender service.",
        )

    client = OpenAI(api_key=api_key, timeout=timeout_seconds)

    prompt = build_prompt(payload)

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful road-safety engineering assistant. Return strict JSON only.",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        LLM_FAILURE_COUNT.labels(failure_type="api_call_failed").inc()
        raise HTTPException(
            status_code=502,
            detail=f"OpenAI API call failed: {str(exc)}",
        ) from exc

    raw_content = response.choices[0].message.content

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        LLM_FAILURE_COUNT.labels(failure_type="invalid_json").inc()
        raise HTTPException(
            status_code=502,
            detail="LLM returned invalid JSON.",
        ) from exc

    try:
        return Recommendation.model_validate(parsed)
    except ValidationError as exc:
        LLM_FAILURE_COUNT.labels(failure_type="schema_validation_failed").inc()
        raise HTTPException(
            status_code=502,
            detail=f"LLM JSON failed schema validation: {exc.errors()}",
        ) from exc


@app.get("/health")
def health() -> dict:
    return {
        "service": "recommender_iep",
        "status": "ok",
        "provider": "openai",
        "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
        "has_api_key": bool(os.getenv("OPENAI_API_KEY")),
    }


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/recommend", response_model=RecommendationResponse)
def recommend(payload: RecommendationRequest) -> RecommendationResponse:
    start = perf_counter()
    REQUEST_COUNT.inc()

    recommendation = call_openai_recommender(payload)

    RECOMMENDATION_COUNT.labels(
        intervention=recommendation.primary_intervention
    ).inc()

    latency_ms = int((perf_counter() - start) * 1000)
    LATENCY.observe(latency_ms / 1000)

    return RecommendationResponse(
        service="recommender_iep",
        status="completed",
        provider="openai",
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        recommendation=recommendation,
        latency_ms=latency_ms,
    )