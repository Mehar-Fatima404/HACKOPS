"""Tests for Tabular Synthetic Data Engine and API."""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_tabular_generation_basic():
    payload = {
        "schema_definitions": [
            {"name": "id", "type": "id", "is_primary_key": True},
            {"name": "full_name", "type": "name"},
            {"name": "email", "type": "email"},
            {"name": "age", "type": "integer", "min_value": 18, "max_value": 65},
            {"name": "salary", "type": "price", "min_value": 50000, "max_value": 150000},
            {"name": "department", "type": "categorical", "categories": ["Eng", "Sales", "HR"]}
        ],
        "row_count": 50,
        "random_seed": 42,
        "null_rate": 0.0,
        "outlier_rate": 0.0
    }

    response = client.post("/api/v1/tabular/generate", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["records"]) == 50
    assert "statistics" in data
    assert "salary" in data["statistics"]
    assert data["statistics"]["salary"]["mean"] is not None
    assert data["statistics"]["department"]["top_values"] is not None

    # Check reproducibility with same seed
    response2 = client.post("/api/v1/tabular/generate", json=payload)
    data2 = response2.json()
    assert data["records"][0]["email"] == data2["records"][0]["email"]


def test_tabular_privacy_and_outliers():
    payload = {
        "schema_definitions": [
            {"name": "id", "type": "id", "is_primary_key": True},
            {"name": "email", "type": "email"},
            {"name": "ssn", "type": "ssn"},
            {"name": "score", "type": "float", "min_value": 10.0, "max_value": 100.0}
        ],
        "row_count": 30,
        "random_seed": 123,
        "null_rate": 0.1,
        "outlier_rate": 0.1,
        "privacy_rules": [
            {"column": "email", "action": "mask"},
            {"column": "ssn", "action": "hash"}
        ]
    }

    response = client.post("/api/v1/tabular/generate", json=payload)
    assert response.status_code == 200
    records = response.json()["records"]

    # Verify masking
    masked_emails = [r["email"] for r in records if r["email"] is not None]
    assert any("*" in e for e in masked_emails)

    # Verify hashing
    hashes = [r["ssn"] for r in records if r["ssn"] is not None]
    for h in hashes:
        assert len(h) == 16  # Truncated hex hash
