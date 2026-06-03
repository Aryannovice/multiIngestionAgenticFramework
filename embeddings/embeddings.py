from __future__ import annotations

import json
import logging
from typing import Any

from config.settings import get_settings
from utils.azure_clients import get_openai_client, get_search_client, resolve_docs_index_name, resolve_vector_dimensions
from utils.utils import sha256_text


logger = logging.getLogger(__name__)


class EmbeddingService:
	def __init__(self) -> None:
		self.settings = get_settings()

	def chunk_text(self, text: str, chunk_size: int = 1200, overlap: int = 120) -> list[str]:
		if not text:
			return []
		chunks: list[str] = []
		start = 0
		while start < len(text):
			end = min(start + chunk_size, len(text))
			chunks.append(text[start:end])
			if end == len(text):
				break
			start = max(end - overlap, 0)
		return chunks

	def generate_embeddings(self, chunks: list[str]) -> list[list[float]]:
		if not chunks:
			return []
		if not self.settings.azure_openai_embedding_deployment:
			return []
		client = get_openai_client()
		if client is None:
			return []

		try:
			response = client.embeddings.create(
				model=self.settings.azure_openai_embedding_deployment,
				input=chunks,
			)
			return [item.embedding for item in response.data]
		except Exception:
			logger.exception("Embedding generation failed")
			return []

	def build_search_documents(
		self, source_name: str, chunks: list[str], vectors: list[list[float]] | None = None
	) -> list[dict[str, Any]]:
		vectors = vectors or []
		target_dimensions = resolve_vector_dimensions(resolve_docs_index_name())
		docs: list[dict[str, Any]] = []
		for index, chunk in enumerate(chunks):
			document: dict[str, Any] = {
				"id": sha256_text(f"{source_name}:{index}:{chunk[:64]}"),
				"content": chunk,
				"source": source_name,
				"chunk_id": index + 1,
				"metadata": json.dumps({"source_name": source_name, "chunk_id": index + 1}, ensure_ascii=False),
			}
			if index < len(vectors):
				document["contentVector"] = self._align_vector(vectors[index], target_dimensions)
			docs.append(document)
		return docs

	def _align_vector(self, vector: list[float], target_dimensions: int) -> list[float]:
		if len(vector) == target_dimensions:
			return vector
		if len(vector) > target_dimensions:
			return vector[:target_dimensions]
		return vector + [0.0] * (target_dimensions - len(vector))

	def index_documents(self, documents: list[dict[str, Any]]) -> int:
		if not documents:
			return 0
		try:
			index_name = resolve_docs_index_name()
			client = get_search_client(index_name)
			results = client.upload_documents(documents=documents)
			return sum(1 for item in results if item.succeeded)
		except Exception:
			logger.exception("Document indexing failed")
			return 0
