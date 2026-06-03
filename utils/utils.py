from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone


def setup_logging(log_level: str) -> None:
	logging.basicConfig(
		level=getattr(logging, log_level.upper(), logging.INFO),
		format="%(asctime)s %(levelname)s %(name)s %(message)s",
	)


def utc_now() -> datetime:
	return datetime.now(timezone.utc)


def sha256_text(value: str) -> str:
	return hashlib.sha256(value.encode("utf-8")).hexdigest()


def generate_job_id() -> str:
	return str(uuid.uuid4())
