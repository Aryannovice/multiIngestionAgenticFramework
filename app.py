from __future__ import annotations
import uuid
from fastapi.responses import StreamingResponse
import logging
import time
from contextlib import asynccontextmanager
from copy import deepcopy
from database.models import Session, User
# from psycopg import rows
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, Response , status, HTTPException
from memory.query_rewriter import query_rewriter
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from observability.tracker import tracker
from config.settings import get_settings
from ingestion.ingestion import ingestion_service
from models.schema import ErrorResponse, IngestionJobResponse, IngestionJobStatusResponse, IngestionRequest, QueryRequest, QueryResponse, RegisterResponse, Token, TokenData, RegisterRequest
from retrieval.retrieval import retrieval_service
from retrieval.router import router
from utils.utils import setup_logging
import asyncio
from typing import Annotated
from pwdlib import PasswordHash 
# from memory.context_builder import ContextBuilder
from fastapi.security import OAuth2PasswordRequestForm
from memory.session_store import session_manager
from auth.auth import authenticate_user, create_access_token, get_current_user

settings = get_settings()
db_url = settings.db_url
setup_logging(settings.log_level)
logger = logging.getLogger(__name__)
password_hash = PasswordHash.recommended()


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
          
       existing = User.get_by_username(settings.admin_username)
       print("EXISTING ADMIN USER:", existing)
       if not existing:
           hashed = PasswordHash.recommended().hash(settings.admin_password)
           result = User.create(settings.admin_username, settings.admin_email, hashed, role="admin")
           print("ADMIN USER CREATED:", result)
           logger.info("Admin user created", extra={"username": settings.admin_username})
           tracker.set_tag("admin_user_created", True)
    except Exception as exc:
         print("Failed to create admin user:", exc)

   
    yield
    logger.info("stopping application")
    



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


def require_admin(current_user: Annotated[TokenData, Depends(get_current_user)]):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user

@app.get("/sessions")
def list_sessions(current_user: Annotated[TokenData, Depends(get_current_user)]):
    rows = Session.get_by_user(current_user.user_id)
    if not rows:
        return JSONResponse(content=[])
    return JSONResponse(content=[
        {
            "session_id": str(row[0]),
            "user_id": str(row[1]),
            "name": row[2],
            "created_at": str(row[3]),
            "last_active": str(row[4]),
        }
        for row in rows
    ])



@app.get("/admin/sessions")
def list_all_sessions(_: Annotated[TokenData, Depends(require_admin)]):
    rows = Session.get_all()
    if not rows:
        return JSONResponse(content=[])
    return JSONResponse(content=[
        {
            "session_id": str(row[0]),
            "user_id": str(row[1]),
            "name": row[2],
            "created_at": str(row[3]),
            "last_active": str(row[4]),
        }
        for row in rows
    ])

	
@app.get("/ingestion/jobs/{job_id}", response_model=IngestionJobStatusResponse)
async def get_ingestion_job(job_id: str) -> IngestionJobStatusResponse:
	try:
		return ingestion_service.get_job_status(job_id)
	except KeyError as exc:
		raise HTTPException(status_code=404, detail=str(exc)) from exc
	except Exception as exc:
		logger.exception("Failed to fetch ingestion job status")
		raise HTTPException(status_code=500, detail=str(exc)) from exc

@app.post("/auth/register", response_model=RegisterResponse)
async def register(request: RegisterRequest):
    existing = User.get_by_username(request.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    
    hashed = password_hash.hash(request.password)
    row = User.create(request.username, request.email, hashed)
    
    logger.info("AUTH | USER_REGISTERED | USER=%s", request.username)
    return RegisterResponse(
        user_id=str(row[0]),
        username=row[1],
        email=row[2],
    )

@app.post("/auth/token", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    User.update_last_login(user["user_id"])
    token = create_access_token(user["user_id"], user["username"], user["role"])
    tracker.set_tag("auth_status", "success")

    logger.info("AUTH | TOKEN_ISSUED | USER=%s", user["username"])
    return Token(access_token=token, token_type="bearer")

 
	
    
	
    

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, current_user: Annotated[TokenData, Depends(get_current_user)]):
    try:
        print("QUERY ENDPOINT HIT")
        user_id = current_user.user_id

        session_id = request.session_id or str(uuid.uuid4())
        session = session_manager.get_or_create_session(session_id, user_id)
        session_id = session.session_id
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
        return Response(
            content=response.model_dump_json(),
            media_type="application/json",
            headers={"X-Session-Id": session_id},
        )

    except Exception as exc:
        logger.exception("Query execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc





@app.post("/query/stream")
async def query_stream(
    request: QueryRequest,
    current_user: Annotated[TokenData, Depends(get_current_user)]
):
    try:
        user_id = current_user.user_id
        print("QUERY_STREAM HIT")

        session_id = request.session_id or str(uuid.uuid4())
        print("SESSION_ID =", session_id)
        session = session_manager.get_or_create_session(request.session_id, user_id)
        session_id = session.session_id

        print("SESSION_ID AFTER GET_OR_CREATE_SESSION =", session_id)

        history = session_manager.get_history(session_id, current_user.user_id)

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
        user_id = current_user.user_id
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
                user_id=user_id
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
            headers={"X-Session-ID": session_id}  ##if we want a session id in form of text we just refer from here staright up
        )

    except Exception as exc:
        logger.exception("Query stream execution failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
