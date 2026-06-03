from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from config.settings import get_settings
from ingestion.ingestion import ingestion_service
from models.schema import ErrorResponse, IngestionJobResponse, IngestionJobStatusResponse, IngestionRequest, QueryRequest, QueryResponse
from retrieval.retrieval import retrieval_service
from retrieval.router import router
from utils.utils import setup_logging
import asyncio

settings = get_settings()
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)


async def main():
	try:
		await asyncio.sleep(1)  
		logger.info("Application startup complete")
	except asyncio.CancelledError:
		logger.info("Application startup cancelled well")

@asynccontextmanager
async def lifespan(_: FastAPI):
	logger.info("Starting application", extra={"env": settings.app_env})
	try:
		yield
	finally:
		logger.info("Stopping application")


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
	started = time.perf_counter()
	try:
		response = await call_next(request)
		latency_ms = int((time.perf_counter() - started) * 1000)
		response.headers["x-latency-ms"] = str(latency_ms)
		return response
	except Exception:
		logger.exception("Unhandled middleware exception")
		raise


@app.exception_handler(Exception)
async def generic_exception_handler(_: Request, exc: Exception):
	logger.exception("Unhandled application exception")
	payload = ErrorResponse(code="INTERNAL_ERROR", message="Unexpected server error", details={"error": str(exc)})
	return JSONResponse(status_code=500, content=payload.model_dump())


@app.get("/health")
async def health() -> dict[str, str]:
	return {"status": "ok", "service": settings.app_name, "env": settings.app_env}


@app.post("/ingestion/jobs", response_model=IngestionJobResponse)
async def submit_ingestion_job(request: IngestionRequest, background_tasks: BackgroundTasks) -> IngestionJobResponse:
	try:
		result = ingestion_service.submit_job(request)
		background_tasks.add_task(ingestion_service.process_job, result.job_id)
		return result
	except Exception as exc:
		logger.exception("Failed to submit ingestion job")
		raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/ingestion/jobs/{job_id}", response_model=IngestionJobStatusResponse)
async def get_ingestion_job(job_id: str) -> IngestionJobStatusResponse:
	try:
		return ingestion_service.get_job_status(job_id)
	except KeyError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc
	except Exception as exc:
		logger.exception("Failed to fetch ingestion job status")
		raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
	try:
		mode = router.classify(request)
		return retrieval_service.answer(request, mode)
	except Exception as exc:
		logger.exception("Query execution failed")
		raise HTTPException(status_code=500, detail=str(exc)) from exc
