"""Unit tests for the CCTV camera registry endpoint (GET /v1/cameras).

Runs in dev mode (REQUIRE_SUPABASE_AUTH unset/false), so verify_supabase_admin
short-circuits and no Supabase token is needed.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

SERVICE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _service_cwd(monkeypatch):
    # The cameras endpoint reads sample_data/daily_report_sample.json relative to CWD.
    monkeypatch.chdir(SERVICE_ROOT)
    monkeypatch.delenv("REQUIRE_SUPABASE_AUTH", raising=False)


from app.main import app  # noqa: E402

client = TestClient(app)


def test_list_cameras_returns_registry_devices():
    response = client.get("/v1/cameras")

    assert response.status_code == 200
    body = response.json()

    assert body["camera_count"] == len(body["cameras"])
    assert body["camera_count"] >= 1

    cameras = {camera["camera_id"]: camera for camera in body["cameras"]}
    assert "aub_gate_01" in cameras

    aub = cameras["aub_gate_01"]
    # Device metadata from the camera registry.
    assert aub["ip_address"] == "10.20.14.11"
    assert aub["rtsp_url"] == "rtsp://10.20.14.11:554/Streaming/Channels/101"
    assert aub["status"] == "online"
    assert aub["model"]
    # Map + per-camera footage wiring (registry 'clip' resolved against blob base).
    assert "lat" in aub["location"] and "lon" in aub["location"]
    assert aub["clip_url"].endswith("/cam_monitoring.mp4")
    assert aub["clip_url"].startswith("http")
    assert aub["clip_available"] is True

    # Each online camera maps to its own registered clip.
    assert cameras["hamra_02"]["clip_url"].endswith("/cam_hamra.mp4")
    assert cameras["corniche_01"]["clip_url"].endswith("/cam_corniche.mp4")


def test_every_camera_shows_footage():
    # Yasmina feedback: every incident/camera should show footage. A camera with no
    # registered clip (e.g. the degraded downtown_01) falls back to a default clip.
    body = client.get("/v1/cameras").json()
    cameras = {camera["camera_id"]: camera for camera in body["cameras"]}

    for camera in cameras.values():
        assert camera["clip_url"], f"{camera['camera_id']} has no clip_url"
        assert camera["clip_available"] is True


def test_cameras_are_unique_per_camera_id():
    body = client.get("/v1/cameras").json()
    camera_ids = [camera["camera_id"] for camera in body["cameras"]]
    assert len(camera_ids) == len(set(camera_ids))
