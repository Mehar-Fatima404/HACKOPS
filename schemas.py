"""Comprehensive Pydantic schemas for HackDataV2."""
from enum import Enum
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field, ConfigDict, model_validator


# -------------------------------------------------------------
# Tabular Schemas
# -------------------------------------------------------------
class ColumnType(str, Enum):
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    CATEGORICAL = "categorical"
    UUID = "uuid"
    EMAIL = "email"
    NAME = "name"
    FIRST_NAME = "first_name"
    LAST_NAME = "last_name"
    PHONE = "phone"
    ADDRESS = "address"
    CITY = "city"
    COUNTRY = "country"
    ZIPCODE = "zipcode"
    COMPANY = "company"
    JOB = "job"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    PRICE = "price"
    TEXT = "text"
    ID = "id"


class ColumnDistribution(str, Enum):
    UNIFORM = "uniform"
    NORMAL = "normal"
    EXPONENTIAL = "exponential"


class PrivacyAction(str, Enum):
    MASK = "mask"
    HASH = "hash"
    NOISE = "noise"


class PrivacyRule(BaseModel):
    column: str
    action: PrivacyAction
    noise_level: float = Field(default=0.05, ge=0.0, le=1.0)
    mask_char: str = "*"
    hash_algo: str = "sha256"


class ColumnDefinition(BaseModel):
    name: str
    type: ColumnType
    distribution: Optional[ColumnDistribution] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean: Optional[float] = None
    std_dev: Optional[float] = None
    precision: Optional[int] = 2
    categories: Optional[List[str]] = None
    weights: Optional[List[float]] = None
    pattern: Optional[str] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    foreign_reference: Optional[str] = None  # e.g. "customers.id"


class TabularGenerateRequest(BaseModel):
    schema_definitions: List[ColumnDefinition]
    row_count: int = Field(default=100, ge=1, le=50000)
    random_seed: Optional[int] = None
    null_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    outlier_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    privacy_rules: Optional[List[PrivacyRule]] = None


class ColumnStatistic(BaseModel):
    name: str
    type: str
    count: int
    null_count: int
    null_percentage: float
    distinct_count: int
    mean: Optional[float] = None
    std: Optional[float] = None
    min: Optional[Any] = None
    max: Optional[Any] = None
    median: Optional[float] = None
    p25: Optional[float] = None
    p75: Optional[float] = None
    outliers_count: Optional[int] = None
    top_values: Optional[Dict[str, int]] = None


class TabularGenerateResponse(BaseModel):
    records: List[Dict[str, Any]]
    statistics: Dict[str, ColumnStatistic]
    meta: Dict[str, Any]


# -------------------------------------------------------------
# Relational Schemas
# -------------------------------------------------------------
class CardinalityRule(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"


class EntityDefinition(BaseModel):
    name: str
    primary_key: str = "id"
    columns: List[ColumnDefinition]
    target_count: Optional[int] = None


class RelationshipDefinition(BaseModel):
    parent_entity: str
    child_entity: str
    foreign_key: str
    parent_key: str = "id"
    cardinality: CardinalityRule = CardinalityRule.ONE_TO_MANY
    min_children: int = Field(default=1, ge=1)
    max_children: int = Field(default=5, ge=1)

    @model_validator(mode="after")
    def validate_children_range(self):
        if self.min_children > self.max_children:
            self.max_children = self.min_children
        return self


class ReconcileRule(BaseModel):
    parent_entity: str  # e.g. "orders"
    child_entity: str   # e.g. "order_items"
    parent_total_field: str = "total_amount"
    child_price_field: str = "unit_price"
    child_quantity_field: str = "quantity"
    parent_foreign_key_in_child: str = "order_id"
    tax_rate: float = 0.0


class RelationalGenerateRequest(BaseModel):
    entities: List[EntityDefinition]
    relationships: List[RelationshipDefinition]
    reconciliation_rules: Optional[List[ReconcileRule]] = None
    seed: Optional[int] = None
    root_count: int = Field(default=20, ge=1, le=5000)


class RelationalValidation(BaseModel):
    foreign_keys_valid: bool
    orphans_count: int
    totals_reconciled: bool
    total_discrepancy: float
    details: List[str]


class RelationalGenerateResponse(BaseModel):
    tables: Dict[str, List[Dict[str, Any]]]
    validation: RelationalValidation
    meta: Dict[str, Any]


# -------------------------------------------------------------
# Document Schemas
# -------------------------------------------------------------
class DocumentTemplateType(str, Enum):
    INVOICE = "invoice"
    STATEMENT = "statement"


class DocumentGenerateRequest(BaseModel):
    template_type: DocumentTemplateType = DocumentTemplateType.INVOICE
    natural_language_query: Optional[str] = None
    locale: str = "en_US"
    currency: str = "USD"
    seed: Optional[int] = None
    item_count: Optional[int] = Field(default=5, ge=1, le=50)
    starting_balance: Optional[float] = Field(default=5000.0, ge=0.0)


class DocumentGenerateResponse(BaseModel):
    template_type: str
    document_id: str
    document: Dict[str, Any]
    pdf_download_url: Optional[str] = None
    meta: Dict[str, Any]


# -------------------------------------------------------------
# Schema Inference Schemas
# -------------------------------------------------------------
class InferredColumn(BaseModel):
    name: str
    inferred_type: str
    sample_values: List[Any]
    regex_format: Optional[str] = None
    nullable: bool = False
    is_candidate_pk: bool = False
    is_candidate_fk: bool = False
    suggested_generator: Dict[str, Any] = Field(default_factory=dict)


class InferredRelationship(BaseModel):
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float


class SchemaInferRequest(BaseModel):
    input_type: str = "auto"  # 'csv', 'json', 'sql', 'auto'
    raw_content: str


class SchemaInferResponse(BaseModel):
    tables: Dict[str, List[InferredColumn]]
    candidate_relationships: List[InferredRelationship]
    suggested_config: Dict[str, Any]
    meta: Dict[str, Any]


# -------------------------------------------------------------
# Admin & Telemetry Schemas
# -------------------------------------------------------------
class AuditLogEntry(BaseModel):
    id: str
    timestamp: str
    client_ip: str
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    rows_generated: int = 0
    details: str = ""


class CustomSchemaEntry(BaseModel):
    id: str
    name: str
    format: str = "sql"  # 'sql', 'json', 'csv'
    description: str = ""
    content: str
    created_at: str


class AdminConfigUpdateRequest(BaseModel):
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    system_prompt: Optional[str] = None
    rate_limit_per_minute: Optional[int] = None
    max_allowed_rows: Optional[int] = None
    max_relational_depth: Optional[int] = None
    differential_privacy_epsilon: Optional[float] = None
    enforce_differential_privacy: Optional[bool] = None
    enabled_templates: Optional[Dict[str, bool]] = None
    debug: Optional[bool] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None


class AdminMetricsResponse(BaseModel):
    uptime_seconds: float
    total_requests: int
    total_errors: int
    endpoint_traffic: Dict[str, int]
    rows_generated_by_engine: Dict[str, int]
    total_rows_generated: int
    avg_latency_ms: Dict[str, float]
    rate_limit_per_minute: int
    llm_provider: str
    llm_model: str


class AdminOverviewResponse(BaseModel):
    uptime_seconds: float
    total_requests: int
    total_errors: int
    total_rows_generated: int
    active_generation_tasks: int
    cpu_engine_load_pct: float
    memory_mb: float
    avg_latency_ms: Dict[str, float]
    export_counts: Dict[str, int]
    token_usage: Dict[str, Any]
    llm_provider: str
    llm_model: str
    system_prompt: str
    guardrails: Dict[str, Any]
    enabled_templates: Dict[str, bool]
    database_info: Optional[Dict[str, Any]] = None

