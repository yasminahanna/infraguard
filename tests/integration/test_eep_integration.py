import httpx


def test_eep_analyze_orchestrates_services():
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
        },
    }

    response = httpx.post(
        "http://localhost:8000/v1/analyze",
        headers={
            "X-API-Key": "dev-secret-key",
        },
        json=payload,
        timeout=20,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "completed"
    assert body["request_id"].startswith("req_")

    assert body["detection"]["service"] == "detection_iep"
    assert body["detection"]["status"] == "completed"
    assert len(body["detection"]["events"]) >= 1

    assert body["hotspot"]["service"] == "hotspot_iep"
    assert body["hotspot"]["status"] == "completed"
    assert 0 <= body["hotspot"]["hotspot_score"] <= 1

    assert body["recommendation"]["service"] == "recommender_iep"
    assert "recommendation" in body["recommendation"]

    assert "latency_ms" in body
    assert body["latency_ms"] >= 0


def test_eep_rejects_invalid_api_key():
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
        ],
        "metadata": {},
    }

    response = httpx.post(
        "http://localhost:8000/v1/analyze",
        headers={
            "X-API-Key": "wrong-key",
        },
        json=payload,
        timeout=20,
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or missing API key."


def test_eep_rejects_invalid_payload():
    payload = {
        "camera_id": "a",
        "road_segment_id": "segment_12",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": 500,
            "lon": 35.4832,
        },
        "frames_base64": [],
        "metadata": {},
    }

    response = httpx.post(
        "http://localhost:8000/v1/analyze",
        headers={
            "X-API-Key": "dev-secret-key",
        },
        json=payload,
        timeout=20,
    )

    assert response.status_code == 422