"""Tests for Admin and Telemetry API."""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_admin_metrics():
    response = client.get("/api/v1/admin/metrics")
    assert response.status_code == 200, response.text
    data = response.json()

    assert "total_requests" in data
    assert "uptime_seconds" in data
    assert "rows_generated_by_engine" in data
    assert "avg_latency_ms" in data


def test_admin_config_update():
    update_payload = {
        "llm_provider": "gemini",
        "llm_model": "gemini-2.0-flash",
        "rate_limit_per_minute": 200
    }
    response = client.post("/api/v1/admin/config", json=update_payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["status"] == "success"
    assert data["updated_fields"]["llm_model"] == "gemini-2.0-flash"
    assert data["updated_fields"]["rate_limit_per_minute"] == 200

    # Verify metrics reflects updated config
    metrics_resp = client.get("/api/v1/admin/metrics")
    m_data = metrics_resp.json()
    assert m_data["llm_model"] == "gemini-2.0-flash"
    assert m_data["rate_limit_per_minute"] == 200
