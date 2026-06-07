"""InfraGuard live CCTV stream ingestor.

Pluggable source (today: a recorded CCTV clip from Azure Blob; later: a live camera
image/stream URL). Samples frames on an interval, sends them through the real EEP
pipeline (detection -> hotspot -> recommender), logs the detected traffic-risk events,
and writes the latest result to a shared `live_feed.json` for the dashboard/demo.
"""
import base64
import json
import os
import tempfile
import time
import urllib.request

import cv2
import requests

SOURCE_URL = os.getenv(
    "SOURCE_URL",
    "https://igcctvzpvbm2.blob.core.windows.net/cctv-clips/cam_monitoring.mp4",
)
EEP_URL = os.getenv("EEP_URL", "http://eep-gateway:8000")
API_KEY = os.getenv("API_KEY", "")
INTERVAL = float(os.getenv("INGEST_INTERVAL_SECONDS", "30"))
FRAMES_PER_CALL = int(os.getenv("INGEST_FRAMES_PER_CALL", "3"))
CAMERA_ID = os.getenv("INGEST_CAMERA_ID", "live_cam_01")
ROAD_SEGMENT_ID = os.getenv("INGEST_ROAD_SEGMENT_ID", "segment_live")
LAT = float(os.getenv("INGEST_LAT", "33.8959"))
LON = float(os.getenv("INGEST_LON", "35.4794"))
LOCATION_NAME = os.getenv("INGEST_LOCATION_NAME", "Live CCTV feed")
LIVE_FEED_PATH = os.getenv("LIVE_FEED_PATH", "/app/sample_data/live_feed.json")


def resolve_source(url: str) -> str:
    """Download an http(s) source once to a temp file; pass through local paths."""
    if not url.lower().startswith("http"):
        return url
    dest = os.path.join(tempfile.gettempdir(), "ingest_source.mp4")
    print(f"[ingestor] downloading source: {url}", flush=True)
    urllib.request.urlretrieve(url, dest)
    print(f"[ingestor] source downloaded -> {dest}", flush=True)
    return dest


def sample_frames(cap, position: int, total: int, step: int) -> tuple[list[str], int]:
    frames_b64: list[str] = []
    for _ in range(FRAMES_PER_CALL):
        cap.set(cv2.CAP_PROP_POS_FRAMES, position % total)
        ok, frame = cap.read()
        if ok:
            encoded, buffer = cv2.imencode(".jpg", frame)
            if encoded:
                frames_b64.append(base64.b64encode(buffer.tobytes()).decode())
        position += step
    return frames_b64, position


def write_live_feed(payload_ts: str, body: dict) -> None:
    detection = body.get("detection", {})
    summary = {
        "updated_at": payload_ts,
        "camera_id": CAMERA_ID,
        "road_segment_id": ROAD_SEGMENT_ID,
        "location_name": LOCATION_NAME,
        "vehicle_count": detection.get("vehicle_count"),
        "events": detection.get("events", []),
        "hotspot": body.get("hotspot", {}),
        "recommendation_provider": body.get("recommendation", {}).get("provider"),
        "source": SOURCE_URL,
    }
    try:
        with open(LIVE_FEED_PATH, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
    except OSError as exc:
        print(f"[ingestor] could not write live feed: {exc}", flush=True)


def main() -> None:
    source = resolve_source(SOURCE_URL)
    cap = cv2.VideoCapture(source)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    step = max(1, total // 100)
    print(
        f"[ingestor] ready: {total} frames, interval={INTERVAL}s, "
        f"frames/call={FRAMES_PER_CALL}, eep={EEP_URL}",
        flush=True,
    )

    position = 0
    while True:
        frames_b64, position = sample_frames(cap, position, total, step)
        if not frames_b64:
            time.sleep(INTERVAL)
            continue

        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = {
            "camera_id": CAMERA_ID,
            "road_segment_id": ROAD_SEGMENT_ID,
            "timestamp": timestamp,
            "location": {"lat": LAT, "lon": LON},
            "frames_base64": frames_b64,
            "metadata": {
                "speed_limit_kmh": 50,
                "weather": "clear",
                "time_of_day": "day",
                "historical_avg_events": 1.5,
                "city": "Live",
                "country": "Live",
                "location_name": LOCATION_NAME,
            },
        }
        try:
            response = requests.post(
                f"{EEP_URL}/v1/analyze",
                json=payload,
                headers={"X-API-Key": API_KEY},
                timeout=180,
            )
            response.raise_for_status()
            body = response.json()
            detection = body.get("detection", {})
            events = detection.get("events", [])
            write_live_feed(timestamp, body)
            event_text = ", ".join(
                f"{e.get('event_type')}({e.get('severity')})" for e in events
            ) or "none"
            print(
                f"[ingestor] {timestamp} vehicles={detection.get('vehicle_count')} "
                f"events=[{event_text}]",
                flush=True,
            )
        except Exception as exc:  # keep the loop alive on any failure
            print(f"[ingestor] analyze failed: {exc}", flush=True)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
