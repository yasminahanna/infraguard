import json
import os
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException
from openai import OpenAI
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field, ValidationError
from starlette.responses import Response
from app.web_search import retrieve_web_context

from pathlib import Path
from app.reporter.report_builder import generate_daily_report
from app.reporter.feedback_store import append_feedback, load_recent_feedback


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
    retrieved_context: list[dict]
    latency_ms: int


def build_prompt(payload: RecommendationRequest, retrieved_context: list[dict]) -> str:
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

Retrieved web context:
{json.dumps(retrieved_context, indent=2)}
- Use retrieved web context only when it is relevant.
- Do not claim something is legally required unless the retrieved source clearly supports it.
- If web context is useful, mention the source title or URL in evidence_used.

Decision rules:
- If risk_level is high and speeding-like behavior exists, strongly consider install_speed_camera or increase_enforcement.
- If lane violations exist, strongly consider repaint_lane_markings.
- If low visibility conditions exist, consider improve_lighting.
- If hotspot_score is low, consider no_action_monitor.
- Do not invent sensor evidence, crash counts, or road facts not provided.
""".strip()




def call_openai_recommender(payload: RecommendationRequest, retrieved_context: list[dict]) -> Recommendation:
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

    prompt = build_prompt(payload, retrieved_context)

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
    retrieved_context = retrieve_web_context(
    event_types=payload.detection.event_types,
    risk_level=payload.hotspot.risk_level,
    trend=payload.hotspot.trend,
    metadata=payload.metadata,
    )

    recommendation = call_openai_recommender(payload, retrieved_context)

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
        retrieved_context=retrieved_context,
    )


@app.post("/v1/reports/generate")
def generate_report() -> dict:
    report = generate_daily_report()
    return {
        "status": "generated",
        "report_id": report["report_id"],
        "using_llm_api": report["recommender_status"]["using_llm_api"],
        "segments": len(report["hotspots"]),
        "store_path": os.getenv("REPORT_STORE_PATH", "/app/sample_data/daily_report_sample.json"),
    }


class AnalyzeClipRequest(BaseModel):
    camera_id: str = Field(..., min_length=2, max_length=100)
    road_segment_id: str = Field(..., min_length=2, max_length=100)
    location_name: str | None = None
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    clip_filename: str = Field(..., min_length=1, max_length=200)


@app.post("/v1/cameras/analyze-clip")
def analyze_camera_clip(payload: AnalyzeClipRequest) -> dict:
    """Run real detection on an uploaded clip, then regenerate the daily report.

    Internal endpoint called by the EEP after a clip is uploaded. Samples frames,
    detects events, appends them, and rebuilds the report so the new camera appears.
    """
    from app.reporter.clip_analyzer import analyze_clip

    try:
        analysis = analyze_clip(
            camera_id=payload.camera_id,
            road_segment_id=payload.road_segment_id,
            location_name=payload.location_name or payload.camera_id,
            lat=payload.lat,
            lon=payload.lon,
            clip_filename=payload.clip_filename,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    report = generate_daily_report()
    return {
        "status": "analyzed",
        "analysis": analysis,
        "report_id": report["report_id"],
        "using_llm_api": report["recommender_status"]["using_llm_api"],
        "segments": len(report["hotspots"]),
    }


@app.get("/v1/reports/latest")
def latest_report() -> dict:
    store_path = os.getenv("REPORT_STORE_PATH", "/app/sample_data/daily_report_sample.json")
    path = Path(store_path)
    if not path.exists():
        return {"status": "placeholder", "message": "No daily report generated yet."}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


class FeedbackRequest(BaseModel):
    report_id: str = Field(..., min_length=1, max_length=200)
    road_segment_id: str = Field(..., min_length=1, max_length=100)
    verdict: Literal["accept", "reject"]
    corrected_intervention: str | None = None
    note: str | None = Field(default=None, max_length=1000)
    admin_email: str | None = None


@app.post("/v1/reports/feedback")
def submit_feedback(payload: FeedbackRequest) -> dict:
    record = append_feedback(payload.model_dump())
    return {"status": "recorded", "feedback": record}


@app.get("/v1/reports/feedback")
def list_feedback(limit: int = 50) -> dict:
    return {"feedback": load_recent_feedback(limit)}