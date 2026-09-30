"""Tests for AI and Heuristic Schema Inference API."""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_infer_csv_snippet():
    csv_content = """user_id,full_name,user_email,user_phone,account_balance
1,Alice Johnson,alice@company.com,+1 555-0199,4500.50
2,Bob Smith,bob@domain.org,+1 555-0244,1200.00
3,Charlie Brown,charlie@enterprise.net,+1 555-0377,9850.75
"""
    payload = {
        "input_type": "csv",
        "raw_content": csv_content
    }

    response = client.post("/api/v1/schema/infer", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert "tables" in data
    assert "dataset" in data["tables"]
    cols = {c["name"]: c for c in data["tables"]["dataset"]}

    assert cols["user_email"]["inferred_type"] == "email"
    assert cols["user_phone"]["inferred_type"] == "phone"
    assert cols["account_balance"]["inferred_type"] == "price"
    assert "suggested_config" in data


def test_infer_sql_ddl():
    sql_content = """
    CREATE TABLE users (
        id INT PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        full_name VARCHAR(100)
    );

    CREATE TABLE orders (
        id INT PRIMARY KEY,
        customer_id INT,
        total_amount DECIMAL(10, 2),
        FOREIGN KEY (customer_id) REFERENCES users(id)
    );
    """
    payload = {
        "input_type": "sql",
        "raw_content": sql_content
    }

    response = client.post("/api/v1/schema/infer", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    assert "users" in data["tables"]
    assert "orders" in data["tables"]
    assert len(data["candidate_relationships"]) > 0

    fk = data["candidate_relationships"][0]
    assert fk["source_table"] == "orders"
    assert fk["source_column"] == "customer_id"
    assert fk["target_table"] == "users"
    assert fk["target_column"] == "id"
