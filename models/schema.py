from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SourceType(str, Enum):
	PDF = "pdf"
	CSV = "csv"
	SQL = "sql"


class RetrievalMode(str, Enum):
	STRUCTURED = "structured"
	SEMANTIC = "semantic"
	HYBRID = "hybrid"


class JobStatus(str, Enum):
	QUEUED = "queued"
	RUNNING = "running"
	SUCCEEDED = "succeeded"
	FAILED = "failed"


class IngestionRequest(BaseModel):
	source_type: SourceType
	blob_path: str | None = Field(default=None, description="Blob path or prefix to ingest")
	source_name: str | None = Field(default=None, description="Optional source identifier")
	sql_query: str | None = Field(default=None, description="Optional SQL for SQL source ingestion")
	metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionJobResponse(BaseModel):
	job_id: str
	status: JobStatus
	source_type: SourceType
	created_at: datetime
	message: str


class IngestionJobStatusResponse(BaseModel):
	job_id: str
	status: JobStatus
	source_type: SourceType
	created_at: datetime
	updated_at: datetime
	details: dict[str, Any] = Field(default_factory=dict)
	error: str | None = None


class QueryRequest(BaseModel):
	session_id: str | None = Field(default=None, description="Optional session ID for context tracking")
	query: str = Field(min_length=3)
	top_k: int = Field(default=5, ge=1, le=20)
	mode_hint: RetrievalMode | None = None
	filters: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
	source: str
	reference: str
	score: float | None = None


class Token(BaseModel):
	access_token: str
	token_type: str = "bearer"

class TokenData(BaseModel):
	username: str | None = None


class QueryResponse(BaseModel):
	answer: str
	mode_used: RetrievalMode
	citations: list[Citation] = Field(default_factory=list)
	latency_ms: int
	generated_sql: str | None = None


class ErrorResponse(BaseModel):
	code: str
	message: str
	details: dict[str, Any] = Field(default_factory=dict)
