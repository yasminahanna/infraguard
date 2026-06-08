import json
import os
import uuid
from pathlib import Path
from time import perf_counter
from typing import Literal

import httpx
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel, Field
from starlette.responses import FileResponse, Response


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


def get_cctv_clip_urls() -> list[str]:
    """Azure Blob CCTV clip URLs (comma-separated env), defaulting to the demo clip."""
    urls_text = os.getenv(
        "CCTV_CLIP_URLS",
        "https://igcctvzpvbm2.blob.core.windows.net/cctv-clips/cam_monitoring.mp4",
    )

    return [url.strip() for url in urls_text.split(",") if url.strip()]


def get_cctv_blob_base_url() -> str:
    """Base URL of the Azure Blob container holding the CCTV clips (trailing slash)."""
    base = os.getenv(
        "CCTV_BLOB_BASE_URL",
        "https://igcctvzpvbm2.blob.core.windows.net/cctv-clips/",
    )
    return base if base.endswith("/") else base + "/"


def camera_clip_dir() -> Path:
    """Directory on the shared volume where admin-uploaded camera clips are stored."""
    return Path(os.getenv("CAMERA_CLIP_DIR", "sample_data/clips"))


def uploaded_clip_path(camera_id: str) -> Path:
    return camera_clip_dir() / f"{camera_id}.mp4"


def public_eep_base() -> str:
    """Public base URL of this EEP, used to build clip URLs for uploaded videos."""
    return os.getenv("PUBLIC_EEP_URL", "http://localhost:8000").rstrip("/")


def resolve_camera_clip_url(camera_id: str, device: dict, fallback_clips: list[str]) -> str | None:
    """Per-camera footage URL.

    Resolution order:
      - an admin-uploaded clip on the volume        -> served by the EEP,
      - registry 'clip' set to a filename/URL       -> that clip (blob filename resolved
        against CCTV_BLOB_BASE_URL),
      - otherwise (no/empty clip)                   -> deterministic pick from
        CCTV_CLIP_URLS, so every camera and every incident still shows footage.
    """
    if uploaded_clip_path(camera_id).exists():
        return f"{public_eep_base()}/v1/cameras/{camera_id}/clip"

    clip = device.get("clip")
    if clip:
        return clip if clip.startswith("http") else get_cctv_blob_base_url() + clip

    if fallback_clips:
        return fallback_clips[sum(ord(c) for c in camera_id) % len(fallback_clips)]

    return None


BAKED_REGISTRY_PATH = Path(__file__).parent / "camera_registry.json"


def registry_store_path() -> Path:
    """Writable camera registry on the shared report volume (survives restarts).

    Cameras added from the admin UI are written here; the baked-in registry is the
    read-only seed (the 4 demo cameras).
    """
    return Path(os.getenv("CAMERA_REGISTRY_PATH", "sample_data/camera_registry.json"))


def _read_registry_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as file:
            return json.load(file).get("cameras", {})
    except (json.JSONDecodeError, OSError):
        return {}


def load_camera_registry() -> dict:
    """CCTV device registry (camera_id -> metadata: IP, model, status, clip...).

    Prefers the writable store on the volume (admin-added cameras), falling back to
    the baked-in seed when nothing has been added yet.
    """
    store = registry_store_path()
    if store.exists():
        return _read_registry_file(store)
    return _read_registry_file(BAKED_REGISTRY_PATH)


def save_camera_to_registry(camera_id: str, device: dict) -> None:
    """Upsert one camera into the writable registry store (seeding it from the baked-in
    seed on first write so the demo cameras are preserved)."""
    store = registry_store_path()
    cameras = _read_registry_file(store) if store.exists() else _read_registry_file(BAKED_REGISTRY_PATH)
    cameras[camera_id] = {**cameras.get(camera_id, {}), **device}

    store.parent.mkdir(parents=True, exist_ok=True)
    with store.open("w", encoding="utf-8") as file:
        json.dump({"cameras": cameras}, file, indent=2, ensure_ascii=False)


def find_incident_in_latest_report(incident_id: str) -> tuple[dict | None, dict | None]:
    """Locate (incident, parent_hotspot) in the stored daily report, else (None, None)."""
    report_path = Path("sample_data/daily_report_sample.json")

    if not report_path.exists():
        return None, None

    try:
        with report_path.open("r", encoding="utf-8") as file:
            report = json.load(file)
    except (json.JSONDecodeError, OSError):
        return None, None

    for hotspot in report.get("hotspots", []):
        for incident in hotspot.get("incidents", []):
            if incident.get("incident_id") == incident_id:
                return incident, hotspot

    return None, None


@app.get("/v1/evidence/{incident_id}")
async def incident_evidence(
    incident_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    auth_info = await verify_supabase_admin(authorization)

    clips = get_cctv_clip_urls()
    registry = load_camera_registry()

    incident, hotspot = find_incident_in_latest_report(incident_id)

    if hotspot is not None:
        camera_id = hotspot.get("camera_id")
        road_segment_id = hotspot.get("road_segment_id")
        location_name = registry.get(camera_id, {}).get("display_name") or hotspot.get(
            "location_name", road_segment_id
        )
        risk_level = hotspot.get("risk_level", "unknown")
        event_type = (incident or {}).get("event_type", "traffic-risk event")
        # Same footage the camera marker shows: resolve from the parent camera's
        # registry clip so a dot and its camera are always consistent.
        clip_url = resolve_camera_clip_url(camera_id, registry.get(camera_id, {}), clips)
        explanation = (
            f"Flagged as '{event_type}' on {location_name} "
            f"(hotspot risk: {risk_level}). The clip below is the sampled CCTV footage "
            f"the detection model analyzed for this location."
        )
    else:
        camera_id = None
        road_segment_id = None
        location_name = None
        # No camera context (incident not in the latest report) -> demo fallback clip.
        clip_url = clips[sum(ord(c) for c in incident_id) % len(clips)] if clips else None
        explanation = (
            "CCTV footage for this monitored location. The detection model samples "
            "frames from this feed to identify traffic-risk events."
        )

    return {
        "incident_id": incident_id,
        "auth": auth_info,
        "evidence": {
            "clip_url": clip_url,
            "frame_url": None,
            "thumbnail_url": None,
            "clip_available": clip_url is not None,
            "start_time": (incident or {}).get("timestamp"),
            "end_time": None,
        },
        "decision_context": {
            "camera_id": camera_id,
            "road_segment_id": road_segment_id,
            "location_name": location_name,
            "explanation": explanation,
        },
    }


@app.get("/v1/cameras")
async def list_cameras(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """List monitored CCTV cameras for the map.

    Each camera is a real monitoring source (distinct from the red incident dots):
    it carries device metadata from the camera registry (IP address, model, status)
    and its public Azure Blob footage URL. Powers the camera markers on the dashboard.
    """
    auth_info = await verify_supabase_admin(authorization)

    clips = get_cctv_clip_urls()
    registry = load_camera_registry()
    report_path = Path("sample_data/daily_report_sample.json")

    report = {}
    if report_path.exists():
        try:
            with report_path.open("r", encoding="utf-8") as file:
                report = json.load(file)
        except (json.JSONDecodeError, OSError):
            report = {}

    cameras = []
    seen: set[str] = set()

    for hotspot in report.get("hotspots", []):
        camera_id = hotspot.get("camera_id")
        location = hotspot.get("location") or {}

        if not camera_id or camera_id in seen:
            continue
        if "lat" not in location or "lon" not in location:
            continue

        seen.add(camera_id)
        device = registry.get(camera_id, {})
        ip_address = device.get("ip_address")
        clip_url = resolve_camera_clip_url(camera_id, device, clips)

        cameras.append(
            {
                "camera_id": camera_id,
                "road_segment_id": hotspot.get("road_segment_id"),
                "location_name": device.get("display_name")
                or hotspot.get("location_name", camera_id),
                "location": {"lat": location["lat"], "lon": location["lon"]},
                "risk_level": hotspot.get("risk_level", "unknown"),
                "clip_url": clip_url,
                "clip_available": clip_url is not None,
                "ip_address": ip_address,
                "rtsp_url": f"rtsp://{ip_address}:554/Streaming/Channels/101"
                if ip_address
                else None,
                "model": device.get("model"),
                "resolution": device.get("resolution"),
                "fps": device.get("fps"),
                "status": device.get("status", "unknown"),
                "installed_on": device.get("installed_on"),
            }
        )

    return {"auth": auth_info, "camera_count": len(cameras), "cameras": cameras}


class CameraCreate(BaseModel):
    camera_id: str = Field(..., min_length=2, max_length=64)
    display_name: str | None = None
    ip_address: str | None = None
    model: str | None = None
    resolution: str | None = None
    fps: int | None = None
    status: str = "online"
    road_segment_id: str = Field(..., min_length=2, max_length=64)
    location_name: str | None = None
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


@app.post("/v1/cameras")
async def create_camera(
    camera: CameraCreate,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Register or update a CCTV camera from the admin UI (writes the volume registry).

    Stores both device metadata (IP/model/status) and the report context
    (road_segment_id, location, name) used when its uploaded clip is analyzed.
    """
    auth_info = await verify_supabase_admin(authorization)
    save_camera_to_registry(camera.camera_id, camera.model_dump())
    return {"status": "saved", "camera_id": camera.camera_id, "auth": auth_info}


@app.post("/v1/cameras/{camera_id}/clip")
async def upload_camera_clip(
    camera_id: str,
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Store an uploaded CCTV clip on the shared volume (served back via GET ...//clip)."""
    auth_info = await verify_supabase_admin(authorization)

    clip_dir = camera_clip_dir()
    clip_dir.mkdir(parents=True, exist_ok=True)
    dest = clip_dir / f"{camera_id}.mp4"

    with dest.open("wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)

    return {
        "status": "uploaded",
        "camera_id": camera_id,
        "bytes": dest.stat().st_size,
        "auth": auth_info,
    }


@app.get("/v1/cameras/{camera_id}/clip")
def serve_camera_clip(camera_id: str) -> FileResponse:
    """Serve an admin-uploaded clip (public, like the Azure Blob clips, so <video> can load it)."""
    path = uploaded_clip_path(camera_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No uploaded clip for this camera.")
    return FileResponse(path, media_type="video/mp4")


@app.post("/v1/cameras/{camera_id}/analyze")
async def analyze_camera_clip(
    camera_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Run the real detection pipeline on a camera's uploaded clip and refresh the report.

    Proxies to the recommender, which samples frames, calls the Detection IEP
    (YOLO + CLIP), appends the resulting events, and regenerates the daily report so the
    new camera appears on the map with real incidents.
    """
    auth_info = await verify_supabase_admin(authorization)

    device = load_camera_registry().get(camera_id)
    if not device:
        raise HTTPException(status_code=404, detail="Unknown camera. Register it first.")
    if not uploaded_clip_path(camera_id).exists():
        raise HTTPException(status_code=400, detail="No uploaded clip to analyze.")

    recommender_url = os.getenv("RECOMMENDER_IEP_URL", "http://recommender-iep:8003")
    payload = {
        "camera_id": camera_id,
        "road_segment_id": device.get("road_segment_id", f"segment_{camera_id}"),
        "location_name": device.get("location_name") or device.get("display_name") or camera_id,
        "lat": device.get("lat"),
        "lon": device.get("lon"),
        "clip_filename": f"{camera_id}.mp4",
    }

    try:
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{recommender_url}/v1/cameras/analyze-clip", json=payload)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Analysis failed: {exc}") from exc

    return {"status": "analyzed", "camera_id": camera_id, "result": resp.json(), "auth": auth_info}


def load_history_reports() -> list[dict]:
    """Full stored reports, deduped to ONE per report_id (one per day), newest first."""
    history_path = Path(
        os.getenv("REPORT_HISTORY_PATH", "sample_data/reports_history.jsonl")
    )
    if not history_path.exists():
        return []

    by_id: dict[str, dict] = {}
    order: list[str] = []
    try:
        with history_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                try:
                    report = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = report.get("report_id", report.get("generated_at", ""))
                if rid not in by_id:
                    order.append(rid)
                by_id[rid] = report  # later line for same day wins
    except OSError:
        return []

    return [by_id[rid] for rid in reversed(order)]


def _report_summary(report: dict) -> dict:
    daily = report.get("daily_report", {})
    return {
        "report_id": report.get("report_id"),
        "generated_at": report.get("generated_at"),
        "city": report.get("city"),
        "country": report.get("country"),
        "report_window": report.get("report_window"),
        "using_llm_api": report.get("recommender_status", {}).get("using_llm_api"),
        "summary": report.get("summary"),
        "hotspot_count": len(report.get("hotspots", [])),
        "title": daily.get("title"),
        "executive_summary": daily.get("executive_summary"),
    }


@app.get("/v1/reports/history")
async def reports_history(
    limit: int = 50,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Past daily reports (one per day, newest first) for the Archives view."""
    auth_info = await verify_supabase_admin(authorization)

    reports = [_report_summary(r) for r in load_history_reports()]
    if limit and limit > 0:
        reports = reports[:limit]

    return {"auth": auth_info, "report_count": len(reports), "reports": reports}


@app.get("/v1/reports/history/{report_id}")
async def report_detail(
    report_id: str,
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    """Full stored report (all sections) for the Archives 'click to open' view."""
    auth_info = await verify_supabase_admin(authorization)

    for report in load_history_reports():
        if report.get("report_id") == report_id:
            return {"auth": auth_info, "report": report}

    raise HTTPException(status_code=404, detail="Report not found.")


@app.get("/v1/live")
async def live_feed(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> dict:
    auth_info = await verify_supabase_admin(authorization)

    live_path = Path("sample_data/live_feed.json")

    if not live_path.exists():
        return {
            "status": "idle",
            "auth": auth_info,
            "message": (
                "No live CCTV feed yet. The stream ingestor publishes the latest "
                "sampled-frame analysis here once it is running."
            ),
        }

    try:
        with live_path.open("r", encoding="utf-8") as file:
            feed = json.load(file)
    except (json.JSONDecodeError, OSError):
        return {"status": "idle", "auth": auth_info, "message": "Live feed not ready."}

    feed["status"] = "live"
    feed["auth"] = auth_info

    return feed


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