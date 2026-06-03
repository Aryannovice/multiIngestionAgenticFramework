from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any

from azure.storage.blob import BlobPrefix
from pypdf import PdfReader

from config.settings import get_settings
from embeddings.embeddings import EmbeddingService
from models.schema import IngestionJobResponse, IngestionJobStatusResponse, IngestionRequest, JobStatus, SourceType
from observability.mlflow_utils import tracker
from utils.azure_clients import get_blob_service_client
from utils.utils import generate_job_id, sha256_text, utc_now


logger = logging.getLogger(__name__)


@dataclass
class InMemoryJobRecord:
	job_id: str
	source_type: SourceType
	status: JobStatus
	created_at: Any
	updated_at: Any
	request: IngestionRequest
	details: dict[str, Any] = field(default_factory=dict)
	error: str | None = None


class IngestionService:
	def __init__(self) -> None:
		self.settings = get_settings()
		self.embedding_service = EmbeddingService()
		self._jobs: dict[str, InMemoryJobRecord] = {}
		self._fingerprints: set[str] = set()
		logger.info("Ingestion services initialized : %s", self.settings)

	def submit_job(self, request: IngestionRequest) -> IngestionJobResponse:
		try:
			logger.info("submitting ingestion job for source_type = %s, source_name = %s", request.source_type, request.source_name)
			job_id = generate_job_id()
			now = utc_now()
			record = InMemoryJobRecord(
				job_id=job_id,
				source_type=request.source_type,
				status=JobStatus.QUEUED,
				created_at=now,
				updated_at=now,
				request=request,
			)
			self._jobs[job_id] = record
			logger.debug("Job %s queued at %s", job_id, now)
			return IngestionJobResponse(
				job_id=job_id,
				status=record.status,
				source_type=record.source_type,
				created_at=record.created_at,
				message="Ingestion job queued",
			)
		except Exception as exc:
			logger.exception("Failed to submit ingestion job")
			raise RuntimeError("Unable to submit ingestion job") from exc

	def get_job_status(self, job_id: str) -> IngestionJobStatusResponse:
		logger.info("Fetching status for job %s", job_id)
		record = self._jobs.get(job_id)
		if record is None:
			logger.error("Job %s not found", job_id)
			raise KeyError(f"Job {job_id} not found")
	   
        

		return IngestionJobStatusResponse(
			job_id=record.job_id,
			status=record.status,
			source_type=record.source_type,
			created_at=record.created_at,
			updated_at=record.updated_at,
			details=record.details,
			error=record.error,
		)

	async def process_job(self, job_id: str) -> None:
		logger.info("Starting job processing for %s", job_id)
		record = self._jobs.get(job_id)
		if record is None:
			logger.error("Job %s not found for processing", job_id)
			return

		record.status = JobStatus.RUNNING
		record.updated_at = utc_now()
		try:
			request = record.request
			fingerprint_basis = f"{request.source_type}:{request.blob_path}:{request.source_name}:{request.sql_query}"
			fingerprint = sha256_text(fingerprint_basis)
			logger.debug("Generated fingerprint %s for job %s", fingerprint, job_id)

			if fingerprint in self._fingerprints:
				logger.info("Job %s deduplicated (fingerprint match)", job_id)
				record.status = JobStatus.SUCCEEDED
				record.details = {"deduplicated": True, "fingerprint": fingerprint}
				record.updated_at = utc_now()
				return

			if request.source_type == SourceType.PDF:
				logger.info("Processing PDF ingestion flow for job %s", job_id)
				processed = self._process_pdf_flow(request)
			elif request.source_type in (SourceType.CSV, SourceType.SQL):
				logger.info("Processing structured ingestion flow for job %s", job_id)
				processed = self._process_structured_flow(request)
			else:
				raise ValueError(f"Unsupported source type: {request.source_type}")

			self._fingerprints.add(fingerprint)
			record.status = JobStatus.SUCCEEDED
			record.details = {
				"deduplicated": False,
				"fingerprint": fingerprint,
				"processed_records": processed,
			}
			record.updated_at = utc_now()
			logger.info("Job %s completed successfully, processed records: %d", job_id, processed)
			tracker.log_metrics({"ingestion_processed_records": float(processed)}, tags={"source": request.source_type.value})
		except Exception as exc:
			logger.exception("Ingestion job %s failed", job_id)
			record.status = JobStatus.FAILED
			record.error = str(exc)
			record.updated_at = utc_now()

	def _process_pdf_flow(self, request: IngestionRequest) -> int:
		logger.info("starting pdf ingestion for blob path = : %s", request.blob_path)
		try:
			contents = self._load_blob_texts(request.blob_path or self.settings.azure_blob_pdf_prefix)
			indexed_count = 0
			for blob_name, text in contents:
				chunks = self.embedding_service.chunk_text(text)
				vectors = self.embedding_service.generate_embeddings(chunks)
				docs = self.embedding_service.build_search_documents(blob_name, chunks, vectors)
				indexed_count += self.embedding_service.index_documents(docs)
			return indexed_count
		except Exception as exc:
			logger.exception("PDF ingestion flow failed")
			raise RuntimeError("PDF ingestion flow failed") from exc

	def _process_structured_flow(self, request: IngestionRequest) -> int:
		try:
			# Placeholder: wire to Fabric SQL write path in next iteration.
			dataset_name = request.source_name or "structured_dataset"
			description = f"Structured source {dataset_name} ingested via {request.source_type.value}"
			metadata_doc = {
				"id": sha256_text(f"dataset:{dataset_name}"),
				"dataset_name": dataset_name,
				"description": description,
				"source_type": request.source_type.value,
			}
			client = get_blob_service_client()
			if self.settings.azure_storage_container:
				# Smoke check that credentials and container resolution work.
				container = client.get_container_client(self.settings.azure_storage_container)
				_ = container.get_container_properties()
			from utils.azure_clients import get_search_client

			search_client = get_search_client(self.settings.azure_ai_search_index_dataset_meta)
			search_client.upload_documents(documents=[metadata_doc])
			return 1
		except Exception as exc:
			logger.exception("Structured ingestion flow failed")
			raise RuntimeError("Structured ingestion flow failed") from exc

	def _write_local_metadata(self, metadata: dict[str, Any]) -> None:
		pass

	def _load_blob_texts(self, blob_prefix: str) -> list[tuple[str, str]]:
		if not self.settings.azure_storage_container:
			raise ValueError("AZURE_STORAGE_CONTAINER is required")

		try:
			service = get_blob_service_client()
			container = service.get_container_client(self.settings.azure_storage_container)
			results: list[tuple[str, str]] = []
			for blob_item in container.list_blobs(name_starts_with=blob_prefix):
				if blob_item.name.endswith("/"):
					continue
				blob_client = container.get_blob_client(blob_item.name)
				raw = blob_client.download_blob().readall()
				if blob_item.name.lower().endswith(".pdf"):
					try:
						reader = PdfReader(io.BytesIO(raw))
						pages = [page.extract_text() or "" for page in reader.pages]
						text = "\n".join(page for page in pages if page.strip())
					except Exception:
						logger.exception("Failed extracting PDF text from %s", blob_item.name)
						text = ""
				else:
					text = raw.decode("utf-8", errors="ignore")
				results.append((blob_item.name, text))
			return results
		except Exception as exc:
			logger.exception("Failed loading blobs from prefix %s", blob_prefix)
			raise RuntimeError("Blob read failed") from exc


ingestion_service = IngestionService()
