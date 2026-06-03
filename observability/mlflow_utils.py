from __future__ import annotations

import logging

from config.settings import get_settings


logger = logging.getLogger(__name__)


class MLflowTracker:
	def __init__(self) -> None:
		self.settings = get_settings()
		self.enabled = self.settings.enable_mlflow
		self._mlflow = None
		if self.enabled:
			try:
				import mlflow

				self._mlflow = mlflow
				if self.settings.mlflow_tracking_uri:
					self._mlflow.set_tracking_uri(self.settings.mlflow_tracking_uri)
			except Exception:
				logger.exception("Failed to initialize MLflow; disabling tracking")
				self.enabled = False

	def log_metrics(self, metrics: dict[str, float], tags: dict[str, str] | None = None) -> None:
		if not self.enabled or self._mlflow is None:
			return
		try:
			with self._mlflow.start_run(nested=True):
				if tags:
					self._mlflow.set_tags(tags)
				self._mlflow.log_metrics(metrics)
		except Exception:
			logger.exception("MLflow metric logging failed")


tracker = MLflowTracker()
