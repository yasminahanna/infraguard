import os

import httpx
import pytest


DEPLOYED_EEP_URL = os.getenv("DEPLOYED_EEP_URL")
DEPLOYED_API_KEY = os.getenv("DEPLOYED_API_KEY")


@pytest.mark.skipif(
    not DEPLOYED_EEP_URL or not DEPLOYED_API_KEY,
    reason="DEPLOYED_EEP_URL and DEPLOYED_API_KEY are not set.",
)
def test_deployed_eep_analyze_endpoint():
    payload = {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_12",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": 33.9001,
            "lon": 35.4832,
        },
        "frames_base64": [
            "fake_frame_1",
            "fake_frame_2",
            "fake_frame_3",
        ],
        "metadata": {
            "speed_limit_kmh": 50,
            "weather": "clear",
            "time_of_day": "evening",
            "historical_avg_events": 1.5,
            "city": "Beirut",
            "country": "Lebanon",
            "location_name": "AUB Gate area",
        },
    }

    response = httpx.post(
        f"{DEPLOYED_EEP_URL}/v1/analyze",
        headers={
            "X-API-Key": DEPLOYED_API_KEY,
        },
        json=payload,
        timeout=60,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "completed"
    assert body["request_id"].startswith("req_")
    assert body["detection"]["service"] == "detection_iep"
    assert body["hotspot"]["service"] == "hotspot_iep"
    assert body["recommendation"]["service"] == "recommender_iep"