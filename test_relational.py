"""Tests for Relational Synthetic Data Engine and API."""
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_relational_generation_and_reconciliation():
    payload = {
        "entities": [
            {
                "name": "customers",
                "primary_key": "id",
                "columns": [
                    {"name": "id", "type": "id", "is_primary_key": True},
                    {"name": "name", "type": "name"},
                    {"name": "email", "type": "email"}
                ],
                "target_count": 5
            },
            {
                "name": "orders",
                "primary_key": "id",
                "columns": [
                    {"name": "id", "type": "id", "is_primary_key": True},
                    {"name": "customer_id", "type": "integer", "is_foreign_key": True},
                    {"name": "order_date", "type": "date"},
                    {"name": "total_amount", "type": "price"}
                ]
            },
            {
                "name": "order_items",
                "primary_key": "id",
                "columns": [
                    {"name": "id", "type": "id", "is_primary_key": True},
                    {"name": "order_id", "type": "integer", "is_foreign_key": True},
                    {"name": "quantity", "type": "integer", "min_value": 1, "max_value": 5},
                    {"name": "unit_price", "type": "price", "min_value": 10.0, "max_value": 100.0}
                ]
            }
        ],
        "relationships": [
            {
                "parent_entity": "customers",
                "child_entity": "orders",
                "foreign_key": "customer_id",
                "parent_key": "id",
                "cardinality": "1:N",
                "min_children": 1,
                "max_children": 3
            },
            {
                "parent_entity": "orders",
                "child_entity": "order_items",
                "foreign_key": "order_id",
                "parent_key": "id",
                "cardinality": "1:N",
                "min_children": 2,
                "max_children": 4
            }
        ],
        "reconciliation_rules": [
            {
                "parent_entity": "orders",
                "child_entity": "order_items",
                "parent_total_field": "total_amount",
                "child_price_field": "unit_price",
                "child_quantity_field": "quantity",
                "parent_foreign_key_in_child": "order_id",
                "tax_rate": 0.05
            }
        ],
        "seed": 42
    }

    response = client.post("/api/v1/relational/generate", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()

    tables = data["tables"]
    assert "customers" in tables
    assert "orders" in tables
    assert "order_items" in tables
    assert len(tables["customers"]) == 5

    # Check validation
    validation = data["validation"]
    assert validation["foreign_keys_valid"] is True
    assert validation["orphans_count"] == 0
    assert validation["totals_reconciled"] is True
    assert validation["total_discrepancy"] == 0.0

    # Explicitly verify Orders.total_amount == sum(items.qty * items.unit_price) * 1.05
    items_by_order = {}
    for itm in tables["order_items"]:
        oid = itm["order_id"]
        sub = itm["quantity"] * itm["unit_price"]
        items_by_order[oid] = items_by_order.get(oid, 0.0) + sub

    for order in tables["orders"]:
        oid = order["id"]
        expected = round(items_by_order[oid] * 1.05, 2)
        assert abs(order["total_amount"] - expected) <= 0.01


def test_relational_postgres_sql_dump_export():
    payload = {
        "tables": {
            "customers": [
                {"id": 1, "company_name": "Acme Corp", "contact_name": "Alice", "contact_email": "alice@acme.com", "city": "Seattle", "country": "USA"},
                {"id": 2, "company_name": "Beta LLC", "contact_name": "Bob", "contact_email": "bob@beta.com", "city": "Boston", "country": "USA"},
            ],
            "orders": [
                {"id": 101, "customer_id": 1, "order_date": "2026-01-15", "status": "COMPLETED", "total_amount": 150.00},
                {"id": 102, "customer_id": 2, "order_date": "2026-01-16", "status": "PROCESSING", "total_amount": 85.50},
            ],
            "order_items": [
                {"id": 1001, "order_id": 101, "item_description": "Widget A", "quantity": 2, "unit_price": 50.00, "line_total": 100.00},
                {"id": 1002, "order_id": 101, "item_description": "Widget B", "quantity": 1, "unit_price": 50.00, "line_total": 50.00},
                {"id": 1003, "order_id": 102, "item_description": "Widget C", "quantity": 1, "unit_price": 85.50, "line_total": 85.50},
            ]
        },
        "generation_order": ["customers", "orders", "order_items"]
    }

    response = client.post("/api/v1/relational/export-sql", json=payload)
    assert response.status_code == 200, response.text
    assert "application/sql" in response.headers.get("content-type", "")
    assert 'filename="hackdata_relational_pg_dump.sql"' in response.headers.get("content-disposition", "")

    sql = response.text
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql

    # 1. Reverse topological teardown
    drop_items_idx = sql.index('DROP TABLE IF EXISTS "order_items"')
    drop_orders_idx = sql.index('DROP TABLE IF EXISTS "orders"')
    drop_customers_idx = sql.index('DROP TABLE IF EXISTS "customers"')
    assert drop_items_idx < drop_orders_idx < drop_customers_idx, "Teardown must be reverse topological (children first)"

    # 2. Forward topological DDL
    create_cust_idx = sql.index('CREATE TABLE "customers"')
    create_ord_idx = sql.index('CREATE TABLE "orders"')
    create_items_idx = sql.index('CREATE TABLE "order_items"')
    assert create_cust_idx < create_ord_idx < create_items_idx, "DDL must be forward topological (parents first)"

    # 3. Foreign Key Declarations
    assert 'REFERENCES "customers"("id")' in sql
    assert 'REFERENCES "orders"("id")' in sql
    assert 'SERIAL PRIMARY KEY' in sql

    # 4. Forward topological INSERTs
    insert_cust_idx = sql.index('INSERT INTO "customers"')
    insert_ord_idx = sql.index('INSERT INTO "orders"')
    insert_items_idx = sql.index('INSERT INTO "order_items"')
    assert insert_cust_idx < insert_ord_idx < insert_items_idx, "INSERTs must be forward topological (parents before children)"

    # 5. Serial sequence synchronizations
    assert "SELECT setval(pg_get_serial_sequence('customers', 'id'), coalesce(max(id), 1)) FROM customers;" in sql
    assert "SELECT setval(pg_get_serial_sequence('orders', 'id'), coalesce(max(id), 1)) FROM orders;" in sql
    assert "SELECT setval(pg_get_serial_sequence('order_items', 'id'), coalesce(max(id), 1)) FROM order_items;" in sql


def test_direct_generate_postgres_sql_dump():
    from app.engines.relational_engine import generate_postgres_sql_dump

    raw_data = {
        "customers": [
            {"id": 1, "company_name": "O'Reilly Media", "contact_email": "info@oreilly.com", "active": True},
        ],
        "orders": [
            {"id": 10, "customer_id": 1, "order_date": "2026-03-01", "total_amount": 99.99},
        ],
        "order_items": [
            {"id": 100, "order_id": 10, "item_description": "SQL & Data Engineering Guide", "quantity": 1, "unit_price": 99.99, "line_total": 99.99}
        ]
    }

    sql = generate_postgres_sql_dump(raw_data)
    assert "BEGIN;" in sql
    assert "COMMIT;" in sql

    # Reverse teardown
    assert sql.index('DROP TABLE IF EXISTS "order_items"') < sql.index('DROP TABLE IF EXISTS "orders"') < sql.index('DROP TABLE IF EXISTS "customers"')

    # Quoting and escaping test
    assert "'O''Reilly Media'" in sql
    assert "TRUE" in sql

    # Topological DDL
    assert sql.index('CREATE TABLE "customers"') < sql.index('CREATE TABLE "orders"') < sql.index('CREATE TABLE "order_items"')

    # Foreign key references
    assert 'REFERENCES "customers"("id")' in sql
    assert 'REFERENCES "orders"("id")' in sql

    # Exact Sequence Synchronization
    assert "SELECT setval(pg_get_serial_sequence('customers', 'id'), coalesce(max(id), 1)) FROM customers;" in sql
    assert "SELECT setval(pg_get_serial_sequence('orders', 'id'), coalesce(max(id), 1)) FROM orders;" in sql
    assert "SELECT setval(pg_get_serial_sequence('order_items', 'id'), coalesce(max(id), 1)) FROM order_items;" in sql


def test_export_postgres_sql_dump_empty_fallback():
    # Calling endpoint with empty json triggers the default generation fallback
    response = client.post("/api/v1/relational/dump/postgres", json={})
    assert response.status_code == 200
    assert "application/sql" in response.headers.get("content-type", "")
    assert 'filename="hackdata_relational_pg_dump.sql"' in response.headers.get("content-disposition", "")
    sql = response.text
    assert 'CREATE TABLE "customers"' in sql
    assert 'CREATE TABLE "orders"' in sql
    assert 'CREATE TABLE "order_items"' in sql
    assert "SELECT setval(pg_get_serial_sequence('customers', 'id'), coalesce(max(id), 1)) FROM customers;" in sql


