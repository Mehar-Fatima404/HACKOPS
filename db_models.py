"""SQLAlchemy 2.0 Database Models for HackDataV2."""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Any

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    DateTime,
    ForeignKey,
    JSON,
    Boolean,
    Index,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


def utcnow():
    return datetime.now(timezone.utc)


class GenerationJob(Base):
    """Tracks synthetic data generation jobs across tabular, relational, and documents modes."""
    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    mode = Column(String(50), nullable=False, index=True)  # 'tabular' | 'relational' | 'documents'
    status = Column(String(50), nullable=False, default="COMPLETED", index=True)  # 'COMPLETED', 'FAILED', 'PENDING'
    row_count = Column(Integer, default=0)
    parameters = Column(JSON, nullable=True)  # JSONB / JSON of request options (seed, nulls, outliers, etc.)
    execution_time_ms = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)

    # Relationships
    datasets = relationship("GeneratedDataset", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_gen_job_mode_status", "mode", "status"),
        Index("idx_gen_job_created_at", "created_at"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "mode": self.mode,
            "status": self.status,
            "row_count": self.row_count,
            "parameters": self.parameters or {},
            "execution_time_ms": self.execution_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class GeneratedDataset(Base):
    """Stores generated tables, schemas, and payload previews for audit and export."""
    __tablename__ = "generated_datasets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("generation_jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    table_name = Column(String(100), nullable=False, default="primary")
    data_payload = Column(JSON, nullable=True)  # JSONB / JSON array of generated records or preview
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    job = relationship("GenerationJob", back_populates="datasets")

    def to_dict(self):
        return {
            "id": self.id,
            "job_id": self.job_id,
            "table_name": self.table_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AdminAuditLog(Base):
    """Live audit events for operational telemetry and streaming terminal."""
    __tablename__ = "admin_audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    endpoint = Column(String(255), nullable=False, index=True)
    client_ip = Column(String(100), default="127.0.0.1")
    status_code = Column(Integer, default=200)
    latency_ms = Column(Float, default=0.0)
    llm_tokens_used = Column(Integer, default=0)
    details = Column(Text, default="")
    timestamp = Column(DateTime(timezone=True), default=utcnow, index=True, nullable=False)

    __table_args__ = (
        Index("idx_audit_timestamp", "timestamp"),
        Index("idx_audit_endpoint", "endpoint"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "",
            "client_ip": self.client_ip,
            "endpoint": self.endpoint,
            "method": "POST",
            "status_code": self.status_code,
            "latency_ms": round(float(self.latency_ms), 2),
            "rows_generated": self.llm_tokens_used if "/schema/infer" in self.endpoint else 0,
            "llm_tokens_used": self.llm_tokens_used,
            "details": self.details or "",
        }


class SchemaRegistry(Base):
    """Custom DDL schemas and structured document templates."""
    __tablename__ = "schema_registries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True, default="")
    schema_json = Column(JSON, nullable=True)  # JSONB / JSON schema metadata
    ddl_raw = Column(Text, nullable=True)  # Raw SQL DDL / CREATE TABLE statements
    format = Column(String(50), nullable=False, default="sql")
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("idx_schema_name", "name"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "format": self.format or "sql",
            "description": self.description or "",
            "content": self.ddl_raw or "",
            "schema_json": self.schema_json or {},
            "created_at": self.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if self.created_at else "",
        }
