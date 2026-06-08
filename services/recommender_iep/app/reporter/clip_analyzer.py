"""Analyze an admin-uploaded CCTV clip with the real detection pipeline.

Samples frames from the uploaded video, runs them through the Detection IEP
(YOLOv8n + CLIP), turns the detected events into report-shaped events, and appends
them to a volume-backed "added events" file that the daily-report builder merges in.
This is what makes an uploaded camera produce a real report (not seeded data).
"""

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import httpx


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sample_frames(video_path: Path, max_frames: int = 12, jpeg_quality: int = 80) -> list[str]:
    """Evenly sample up to max_frames JPEG frames from the video, base64-encoded."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return []

    frames_b64: list[str] = []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0

    def _encode(frame) -> str | None:
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        return base64.b64encode(buf.tobytes()).decode() if ok else None

    if total > 0:
        step = max(total // max_frames, 1)
        for idx in range(0, total, step):
            if len(frames_b64) >= max_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok:
                continue
            enc = _encode(frame)
            if enc:
                frames_b64.append(enc)
    else:
        while len(frames_b64) < max_frames:
            ok, frame = cap.read()
            if not ok:
                break
            enc = _encode(frame)
            if enc:
                frames_b64.append(enc)

    cap.release()
    return frames_b64


def _run_detection(
    frames_b64: list[str], camera_id: str, road_segment_id: str, lat: float, lon: float
) -> tuple[list[dict], int]:
    """Call the Detection IEP in <=8-frame batches; return (events, max vehicle_count)."""
    detection_url = os.getenv("DETECTION_IEP_URL", "http://detection-iep:8001")
    events: list[dict] = []
    vehicle_counts: list[int] = []

    for i in range(0, len(frames_b64), 8):
        batch = frames_b64[i : i + 8]
        payload = {
            "camera_id": camera_id,
            "road_segment_id": road_segment_id,
            "timestamp": _now_iso(),
            "location": {"lat": lat, "lon": lon},
            "frames_base64": batch,
            "metadata": {"source": "admin_upload"},
        }
        resp = httpx.post(f"{detection_url}/detect", json=payload, timeout=180)
        resp.raise_for_status()
        det = resp.json()
        vehicle_counts.append(int(det.get("vehicle_count", 0)))
        events.extend(det.get("events", []))

    return events, (max(vehicle_counts) if vehicle_counts else 0)


def _added_events_path() -> Path:
    return Path(os.getenv("ADDED_EVENTS_PATH", "/app/sample_data/added_events.json"))


def _append_added_events(road_segment_id: str, segment_meta: dict, report_events: list[dict]) -> None:
    """Upsert this segment's meta + events into the volume-backed added-events file."""
    path = _added_events_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {"segments": {}, "events": []}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {"segments": {}, "events": []}

    data.setdefault("segments", {})[road_segment_id] = segment_meta
    # Re-analysis of a segment replaces its prior events.
    data["events"] = [
        e for e in data.get("events", []) if e.get("road_segment_id") != road_segment_id
    ]
    data["events"].extend(report_events)

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def analyze_clip(
    camera_id: str,
    road_segment_id: str,
    location_name: str,
    lat: float,
    lon: float,
    clip_filename: str,
) -> dict:
    """Sample -> detect -> append events for one uploaded camera clip."""
    clip_dir = Path(os.getenv("CAMERA_CLIP_DIR", "/app/sample_data/clips"))
    video_path = clip_dir / clip_filename
    if not video_path.exists():
        raise FileNotFoundError(f"clip not found: {video_path}")

    max_frames = int(os.getenv("ANALYZE_MAX_FRAMES", "12"))
    frames = sample_frames(video_path, max_frames=max_frames)
    if not frames:
        raise ValueError("could not sample any frames from the uploaded clip")

    det_events, vehicle_count = _run_detection(frames, camera_id, road_segment_id, lat, lon)

    report_events = [
        {
            "incident_id": f"inc_{uuid.uuid4().hex[:8]}",
            "road_segment_id": road_segment_id,
            "camera_id": camera_id,
            "event_type": e.get("event_type", "unknown"),
            "severity": e.get("severity", "medium"),
            "confidence": float(e.get("confidence", 0.0)),
            "timestamp": _now_iso(),
            "lat": lat,
            "lon": lon,
            "vehicle_count": vehicle_count,
            "evidence": {"source": "admin_upload", "clip_url": None},
        }
        for e in det_events
    ]

    # If no reckless events fired, still record one summary incident so the camera
    # appears on the map with its real vehicle count.
    if not report_events:
        report_events.append(
            {
                "incident_id": f"inc_{uuid.uuid4().hex[:8]}",
                "road_segment_id": road_segment_id,
                "camera_id": camera_id,
                "event_type": "normal_traffic",
                "severity": "low",
                "confidence": 0.5,
                "timestamp": _now_iso(),
                "lat": lat,
                "lon": lon,
                "vehicle_count": vehicle_count,
                "evidence": {"source": "admin_upload", "clip_url": None},
            }
        )

    segment_meta = {
        "camera_id": camera_id,
        "location_name": location_name,
        "location": {"lat": lat, "lon": lon},
        "radius_meters": 150,
        "metadata": {"speed_limit_kmh": 50, "source": "admin_upload"},
    }

    _append_added_events(road_segment_id, segment_meta, report_events)

    return {
        "frames_analyzed": len(frames),
        "events_detected": len(det_events),
        "vehicle_count": vehicle_count,
        "incidents_added": len(report_events),
    }
