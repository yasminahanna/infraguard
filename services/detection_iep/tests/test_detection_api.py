from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "detection_iep",
        "status": "ok",
    }


def test_detect_returns_events_for_valid_payload():
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
        },
    }

    response = client.post("/detect", json=payload)

    assert response.status_code == 200

    body = response.json()

    assert body["service"] == "detection_iep"
    assert body["status"] == "completed"
    assert body["vehicle_count"] >= 2
    assert body["mean_confidence"] >= 0
    assert body["mean_confidence"] <= 1
    assert len(body["events"]) >= 1

    first_event = body["events"][0]

    assert first_event["event_type"] in [
        "unsafe_proximity",
        "lane_region_violation",
        "possible_speeding",
        "wrong_direction_proxy",
        "high_density",
    ]
    assert first_event["severity"] in ["low", "medium", "high"]
    assert first_event["confidence"] >= 0
    assert first_event["confidence"] <= 1


def test_detect_rejects_invalid_latitude():
    payload = {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_12",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": 1000,
            "lon": 35.4832,
        },
        "frames_base64": [
            "fake_frame_1",
        ],
        "metadata": {},
    }

    response = client.post("/detect", json=payload)

    assert response.status_code == 422


def test_detect_rejects_too_many_frames():
    payload = {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_12",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": 33.9001,
            "lon": 35.4832,
        },
        "frames_base64": [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
        ],
        "metadata": {},
    }

    response = client.post("/detect", json=payload)

    assert response.status_code == 422