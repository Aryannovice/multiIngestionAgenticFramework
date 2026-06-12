from __future__ import annotations

import logging
import threading
import mlflow
import time
from typing import Any

logger = logging.getLogger(__name__)

class RetrievalTracker:
    """
    A drop-in replacement for logger, so we call tracker.info() instead of logger.info().
    Everything still goes to our log handler.

    Since we defined ThreadPoolExecutor in hybrid, we ensure flush() runs concurrently
    instead of sequentially, which is the default behavior of Python logging.
    """

    def __init__(self) -> None:
        self._mlflow = None
        self._enabled = False
        self._experiment: str = "retrieval-agent"
        self._lock = threading.Lock()
        self._spans: dict[int, dict[str, Any]] = {}

    def configure(self, enabled, tracking_uri: str = "", experiment_name: str = "retrieval-agent"):
        with self._lock:
            self._enabled = enabled
            if not enabled:
                return
            try:
                import mlflow
                self._mlflow = mlflow
                if tracking_uri:
                    mlflow.set_tracking_uri(tracking_uri)
            except ImportError:
                logger.exception("mlflow not installed — tracking disabled")
                self._enabled = False
                return

            # separate try — experiment issues shouldn't kill tracking entirely
            try:
                self._mlflow.set_experiment(experiment_name)
            except Exception:
                logger.warning(
                    "Could not set experiment '%s' — it may be deleted. "
                    "Run `mlflow gc` to hard-delete it, or use a different name. "
                    "Falling back to default experiment.",
                    experiment_name,
                )

    def info(self, msg: str, *args, metric: str | None = None, value: float | None = None) -> None:
        """
        Drop-in for logger.info().
        Example: tracker.info("embed done", metric="embedding_latency_ms", value=123)
        """
        logger.info(msg, *args)
        if metric is not None and value is not None:
            self._record(metric, value)

    def warning(self, msg: str, *args) -> None:
        logger.warning(msg, *args)

    def exception(self, msg: str, *args) -> None:
        logger.exception(msg, *args)
        self._tag("error", msg % args if args else msg)

    # Span accumulation — called internally by info() or directly
    def _span(self) -> dict[str, Any]:
        tid = threading.get_ident()
        if tid not in self._spans:
            # create new entry if previous tid doesn't exist
            self._spans[tid] = {"metrics": {}, "tags": {}}
        return self._spans[tid]

    def _record(self, key: str, value: float) -> None:
        self._span()["metrics"][key] = value

    def _tag(self, key: str, value: float) -> None:
        self._span()["tags"][key] = str(value)[:200]

    def set_tag(self, key: str, value: str) -> None:
        """Set a tag for current thread's span."""
        self._tag(key, value)

    def record(self, key: str, value: float) -> None:
        """Record a metric for current thread's span."""
        self._record(key, value)

    def flush(self, run_name: str = "retrieval") -> None:
        """
        Ship accumulated metrics/tags in the thread's span
        in a single MLflow run, then clear the span.
        """
        if not self._enabled or self._mlflow is None:
            return
        tid = threading.get_ident()
        span = self._spans.pop(tid, {"metrics": {}, "tags": {}})

        if not span["metrics"] and not span["tags"]:
            return

        try:
            with self._mlflow.start_run(run_name=run_name):
                if span["tags"]:
                    self._mlflow.set_tags(span["tags"])
                if span["metrics"]:
                    self._mlflow.log_metrics(span["metrics"])
        except Exception:
            logger.exception("MLflow logging failed during flush()")


tracker = RetrievalTracker()






                

