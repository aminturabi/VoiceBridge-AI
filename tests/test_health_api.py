"""Unit tests for /api/health endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from voicebridge.api.app import create_app


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_endpoint(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "system" in data or "cpu_percent" in data



def test_liveness_endpoint(client):
    res = client.get("/api/health/liveness")
    assert res.status_code == 200
    assert res.json()["status"] == "alive"


def test_readiness_endpoint(client):
    res = client.get("/api/health/readiness")
    assert res.status_code == 200
    assert res.json()["status"] == "ready"
