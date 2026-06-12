from __future__ import annotations
import uuid
from fastapi.responses import StreamingResponse
import logging
import time
from contextlib import asynccontextmanager
from copy import deepcopy
from memory.query_rewriter import query_rewriter
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from httpcore import request
from httpcore import request
from sqlalchemy import exc
from observability.tracker import tracker
from config.settings import get_settings
from ingestion.ingestion import ingestion_service
from models.schema import ErrorResponse, IngestionJobResponse, IngestionJobStatusResponse, IngestionRequest, QueryRequest, QueryResponse
from retrieval.retrieval import retrieval_service
from retrieval.router import router
from utils.utils import setup_logging
import asyncio
# from memory.context_builder import ContextBuilder
from memory.session_store import session_manager
	

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
async def query(request: QueryRequest):
    try:
        print("QUERY ENDPOINT HIT")

        session_id = getattr(request, "session_id", None) or str(uuid.uuid4())
        session = session_manager.get_or_create_session(session_id)
        history = session.get_history()

        logger.info("SESSION=%s | HISTORY_SIZE=%d", session_id, len(history))
        logger.info("HISTORY_CONTENT=%s", history)

        mode = router.classify(request, history)
        rewritten_query = query_rewriter.rewrite_query(request.query, history)
        logger.info("original_query=%s | rewritten_query=%s", request.query, rewritten_query)

        rewritten_request = deepcopy(request)
        rewritten_request.query = rewritten_query

        response = retrieval_service.answer(rewritten_request, mode)

        logger.info(f"Response content: {response}")

        session.append_history(request.query, response.answer)
        return response

    except Exception as exc:
        logger.exception("Query execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc





@app.post("/query/stream")
async def query_stream(request: QueryRequest):
    try:
        print("QUERY_STREAM HIT")

        session_id = getattr(request, "session_id", None) or str(uuid.uuid4())
        print("SESSION_ID =", session_id)

        history = session_manager.get_history(session_id)

        logger.info(
            "SESSION=%s | HISTORY_SIZE=%d",
            session_id,
            len(history),
        )

        mode = router.classify(request, history)
        rewritten_query = query_rewriter.rewrite_query(request.query, history)
        logger.info("original_query=%s | rewritten_query=%s", request.query, rewritten_query)

        rewritten_request = deepcopy(request)
        rewritten_request.query = rewritten_query

        if mode.name == "SEMANTIC":
            contexts, _ = retrieval_service._semantic_retrieval(rewritten_request)
            stream = retrieval_service._compose_answer_stream(
                rewritten_request.query,
                contexts,
            )

        elif mode.name == "STRUCTURED":
            contexts, _, _ = retrieval_service._structured_retrieval(rewritten_request)
            stream = retrieval_service._compose_answer_stream(
                rewritten_request.query,
                contexts,
            )

        else:
            stream = retrieval_service._hybrid_retrieval_stream(rewritten_request)

        def memory_stream():
            full_response = []

            for chunk in stream:
                full_response.append(chunk)
                yield chunk

            final_answer = "".join(full_response)

            session_manager.append(
                session_id=session_id,
                query=request.query,
                response=final_answer,
            )

            # Tracker calls placed correctly here
            tracker.set_tag("request_way", mode.value)
            tracker.set_tag("session_id", session_id)
            tracker.record("response_length", float(len(final_answer)))

            logger.info(
                "Completed streaming response for SESSION=%s | RESPONSE_LENGTH=%d",
                session_id,
                len(final_answer),
            )

        return StreamingResponse(
            memory_stream(),
            media_type="text/event-stream",
        )

    except Exception as exc:
        logger.exception("Query stream execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc






										   