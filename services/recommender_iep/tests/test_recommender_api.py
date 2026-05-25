from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def valid_payload():
    return {
        "camera_id": "aub_gate_01",
        "road_segment_id": "segment_12",
        "detection": {
            "vehicle_count": 6,
            "events_detected": 3,
            "mean_confidence": 0.743,
            "event_types": [
                "unsafe_proximity",
                "high_density",
                "possible_speeding",
            ],
        },
        "hotspot": {
            "hotspot_score": 0.79,
            "risk_level": "high",
            "trend": "increasing",
            "cluster_id": "cluster_012",
            "evidence": [
                {
                    "label": "event_count",
                    "value": "3",
                },
                {
                    "label": "weighted_risk_score",
                    "value": "0.79",
                },
            ],
        },
        "metadata": {
            "speed_limit_kmh": 50,
            "weather": "clear",
            "time_of_day": "evening",
        },
    }


def test_health_endpoint_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["service"] == "recommender_iep"
    assert body["status"] == "ok"
    assert body["provider"] == "openai"


def test_recommend_returns_controlled_error_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = client.post("/recommend", json=valid_payload())

    assert response.status_code == 500

    body = response.json()

    assert "OPENAI_API_KEY is missing" in body["detail"]


def test_recommend_rejects_invalid_hotspot_score():
    payload = valid_payload()
    payload["hotspot"]["hotspot_score"] = 2.0

    response = client.post("/recommend", json=payload)

    assert response.status_code == 422


def test_recommend_rejects_invalid_priority_inputs():
    payload = valid_payload()
    payload["hotspot"]["risk_level"] = "extreme"

    response = client.post("/recommend", json=payload)

    assert response.status_code == 422


def test_recommend_rejects_negative_vehicle_count():
    payload = valid_payload()
    payload["detection"]["vehicle_count"] = -1

    response = client.post("/recommend", json=payload)

    assert response.status_code == 422