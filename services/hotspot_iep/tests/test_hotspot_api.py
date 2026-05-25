from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "hotspot_iep",
        "status": "ok",
    }


def test_score_returns_hotspot_result_for_valid_payload():
    payload = {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_12",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": 33.9001,
            "lon": 35.4832,
        },
        "events": [
            {
                "event_type": "unsafe_proximity",
                "severity": "medium",
                "confidence": 0.74,
                "frame_index": 0,
                "explanation": "Vehicles appear close within the sampled region.",
            },
            {
                "event_type": "possible_speeding",
                "severity": "high",
                "confidence": 0.81,
                "frame_index": 2,
                "explanation": "Vehicle displacement suggests possible speeding.",
            },
        ],
        "metadata": {
            "speed_limit_kmh": 50,
            "weather": "clear",
            "time_of_day": "evening",
            "historical_avg_events": 1.0,
        },
    }

    response = client.post("/score", json=payload)

    assert response.status_code == 200

    body = response.json()

    assert body["service"] == "hotspot_iep"
    assert body["status"] == "completed"
    assert body["road_segment_id"] == "segment_12"
    assert 0 <= body["hotspot_score"] <= 1
    assert body["risk_level"] in ["low", "medium", "high"]
    assert body["trend"] in ["stable", "increasing", "decreasing"]
    assert body["cluster_id"].startswith("cluster_")
    assert len(body["evidence"]) >= 1


def test_score_returns_low_risk_for_no_events():
    payload = {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_empty",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": 33.9001,
            "lon": 35.4832,
        },
        "events": [],
        "metadata": {
            "historical_avg_events": 2.0,
        },
    }

    response = client.post("/score", json=payload)

    assert response.status_code == 200

    body = response.json()

    assert body["hotspot_score"] == 0.05
    assert body["risk_level"] == "low"


def test_score_rejects_invalid_confidence():
    payload = {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_12",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": 33.9001,
            "lon": 35.4832,
        },
        "events": [
            {
                "event_type": "unsafe_proximity",
                "severity": "medium",
                "confidence": 2.0,
                "frame_index": 0,
                "explanation": "Invalid confidence.",
            }
        ],
        "metadata": {},
    }

    response = client.post("/score", json=payload)

    assert response.status_code == 422


def test_score_rejects_invalid_location():
    payload = {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_12",
        "timestamp": "2026-04-10T14:30:00Z",
        "location": {
            "lat": -200,
            "lon": 35.4832,
        },
        "events": [],
        "metadata": {},
    }

    response = client.post("/score", json=payload)

    assert response.status_code == 422