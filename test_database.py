"""Unit tests for persistent database models, SQL aggregations, and automatic fallback."""
import asyncio
import pytest
from fastapi.testclient import TestClient
from main import app
from app.db.session import init_db, get_db_info
from app.db.models import SchemaRegistry, GenerationJob, GeneratedDataset, AdminAuditLog
from app.db.repository import (
    record_generation_event,
    get_database_metrics,
    get_audit_logs,
    clear_audit_logs,
    get_custom_schemas,
    add_custom_schema,
    delete_custom_schema,
)

client = TestClient(app)


def test_database_init_and_info():
    """Verify database initialization, driver dialect, and fallback mechanism."""
    info = asyncio.run(init_db())
    assert "dialect" in info
    assert "driver" in info
    assert "is_fallback" in info
    assert info["dialect"] in ("sqlite", "postgresql")


def test_record_generation_event():
    """Verify GenerationJob, GeneratedDataset, and AdminAuditLog persistence in single transaction."""
    async def _run():
        return await record_generation_event(
            job_type="tabular",
            status="COMPLETED",
            rows_requested=100,
            rows_generated=100,
            latency_ms=45.2,
            endpoint="/api/v1/tabular/generate",
            method="POST",
            client_ip="127.0.0.1",
            parameters={"seed": 42},
            dataset_preview={"preview": [{"id": 1, "name": "Alice"}]},
            columns_meta=[{"name": "id", "type": "id"}],
            details="Test tabular batch 100 rows",
        )

    job = asyncio.run(_run())
    assert job is not None
    assert job.mode == "tabular"
    assert job.row_count == 100


def test_database_metrics_aggregation():
    """Verify that get_database_metrics executes live SQL aggregation queries."""
    metrics = asyncio.run(get_database_metrics())
    assert "total_rows_generated" in metrics
    assert "total_jobs_run" in metrics
    assert "total_requests" in metrics
    assert "rows_generated_by_engine" in metrics
    assert "avg_latency_ms" in metrics
    assert isinstance(metrics["total_rows_generated"], int)
    assert metrics["total_rows_generated"] >= 100


def test_custom_schema_crud():
    """Verify SchemaRegistry insertion, retrieval, and deletion."""
    async def _run():
        created = await add_custom_schema(
            name="Test Analytics DDL",
            format="sql",
            description="Event tracking schema",
            content="CREATE TABLE events (id UUID PRIMARY KEY, event_name VARCHAR);",
        )
        assert created["id"].startswith("schema-")
        assert created["name"] == "Test Analytics DDL"

        schemas = await get_custom_schemas()
        assert any(s["id"] == created["id"] for s in schemas)

        deleted = await delete_custom_schema(created["id"])
        assert deleted is True

        schemas_after = await get_custom_schemas()
        assert not any(s["id"] == created["id"] for s in schemas_after)

    asyncio.run(_run())


def test_api_admin_db_info_endpoint():
    """Test /api/v1/admin/db-info endpoint."""
    response = client.get("/api/v1/admin/db-info")
    assert response.status_code == 200
    data = response.json()
    assert "dialect" in data
    assert "driver" in data


def test_api_generation_persists_audit_log():
    """Test that calling tabular generate endpoint reflects in audit logs."""
    tab_res = client.post("/api/v1/tabular/generate", json={
        "schema_definitions": [{"name": "uid", "type": "id", "is_primary_key": True}],
        "row_count": 25,
        "random_seed": 77
    })
    assert tab_res.status_code == 200

    logs_res = client.get("/api/v1/admin/logs?limit=10")
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) > 0
    assert any(l["endpoint"] == "/api/v1/tabular/generate" for l in logs)


def test_export_postgres_sql_dump():
    """Test generating and exporting a PostgreSQL SQL dump."""
    req_body = {
        "entities": [
            {
                "name": "authors",
                "primary_key": "id",
                "columns": [{"name": "id", "type": "id", "is_primary_key": True}, {"name": "name", "type": "name"}]
            },
            {
                "name": "books",
                "primary_key": "id",
                "columns": [
                    {"name": "id", "type": "id", "is_primary_key": True},
                    {"name": "author_id", "type": "integer", "is_foreign_key": True},
                    {"name": "title", "type": "text"}
                ]
            }
        ],
        "relationships": [
            {
                "parent_entity": "authors",
                "child_entity": "books",
                "foreign_key": "author_id",
                "parent_key": "id",
                "cardinality": "1:N",
                "min_children": 1,
                "max_children": 2
            }
        ],
        "root_count": 3
    }
    response = client.post("/api/v1/relational/export-sql-dump", json=req_body)
    assert response.status_code == 200
    sql_text = response.text
    assert "BEGIN;" in sql_text
    assert "CREATE TABLE \"authors\"" in sql_text
    assert "CREATE TABLE \"books\"" in sql_text
    assert "INSERT INTO \"authors\"" in sql_text
    assert "INSERT INTO \"books\"" in sql_text
    assert "COMMIT;" in sql_text

