"""Unit tests for API v1 health endpoints, request tracing, and input validation."""

import pytest
from fastapi.testclient import TestClient
from voicebridge.api.app import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_endpoints(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "system" in data
    assert "components" in data

    liveness_res = client.get("/api/health/liveness")
    assert liveness_res.status_code == 200
    assert liveness_res.json()["status"] == "alive"

    readiness_res = client.get("/api/health/readiness")
    assert readiness_res.status_code == 200
    assert readiness_res.json()["status"] == "ready"


def test_request_id_tracing(client):
    custom_id = "test-request-id-12345"
    res = client.get("/api/info", headers={"X-Request-ID": custom_id})
    assert res.status_code == 200
    assert res.headers.get("X-Request-ID") == custom_id

    # Auto-generation test
    auto_res = client.get("/api/info")
    assert auto_res.status_code == 200
    assert "X-Request-ID" in auto_res.headers
    assert len(auto_res.headers["X-Request-ID"]) > 0


def test_start_call_validation(client):
    # Invalid source_kind
    invalid_res = client.post("/api/start", json={"source_kind": "invalid_kind"})
    assert invalid_res.status_code == 422  # Unprocessable entity

    # Valid payload
    valid_payload = {
        "my_language": "en",
        "other_language": "ar",
        "source_kind": "wav",
        "wav_path": "assets/test_en.wav",
        "two_way": False,
    }
    # Note: start endpoint will return 200 started or 409 already running
    start_res = client.post("/api/start", json=valid_payload)
    assert start_res.status_code in (200, 409)

    # Clean up
    client.post("/api/stop")
