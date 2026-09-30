"""Tests for Document Synthetic Data Engine and PDF Rendering."""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_invoice_generation_and_pdf():
    payload = {
        "template_type": "invoice",
        "natural_language_query": "Quarterly cloud infrastructure consulting services",
        "currency": "USD",
        "locale": "en_US",
        "seed": 42
    }

    # 1. Test JSON generation
    response = client.post("/api/v1/documents/generate", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    doc = data["document"]
    assert "invoice_number" in doc
    assert "items" in doc
    assert len(doc["items"]) > 0

    # Mathematical consistency checks
    subtotal = sum(i["line_total"] for i in doc["items"])
    assert round(subtotal, 2) == doc["subtotal"]
    expected_tax = round(doc["subtotal"] * doc["tax_rate"], 2)
    assert abs(expected_tax - doc["tax_amount"]) <= 0.02
    assert abs(round(doc["subtotal"] + doc["tax_amount"], 2) - doc["total_amount"]) <= 0.02

    # 2. Test PDF download URL
    doc_id = data["document_id"]
    pdf_resp = client.get(f"/api/v1/documents/export-pdf/{doc_id}")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF")


def test_statement_continuous_running_balance():
    payload = {
        "template_type": "statement",
        "currency": "USD",
        "starting_balance": 10000.0,
        "seed": 99,
        "item_count": 12
    }

    response = client.post("/api/v1/documents/generate", json=payload)
    assert response.status_code == 200, response.text
    doc = response.json()["document"]

    txs = doc["transactions"]
    assert len(txs) == 12

    # Verify strict continuous running balance: prev_balance + credit - debit == current_balance
    current_bal = doc["opening_balance"]
    assert current_bal == 10000.0

    for tx in txs:
        if tx["type"] == "credit":
            current_bal += tx["amount"]
        else:
            current_bal -= tx["amount"]
        current_bal = round(current_bal, 2)
        assert abs(tx["running_balance"] - current_bal) <= 0.01

    assert abs(doc["closing_balance"] - current_bal) <= 0.01


def test_direct_pdf_rendering():
    payload = {
        "template_type": "statement",
        "starting_balance": 2500.0,
        "seed": 101
    }
    response = client.post("/api/v1/documents/render-pdf", json=payload)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000
