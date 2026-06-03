from __future__ import annotations

from models.schema import QueryRequest, RetrievalMode


STRUCTURED_HINTS = {
	"sum",
	"avg",
	"average",
	"count",
	"total",
	"group by",
	"table",
	"dataset",
	"column",
	"rows",
	"sql",
}


class QueryRouter:
	def classify(self, request: QueryRequest) -> RetrievalMode:
		if request.mode_hint is not None:
			return request.mode_hint

		query = request.query.lower()
		if any(hint in query for hint in STRUCTURED_HINTS):
			return RetrievalMode.STRUCTURED
		if " and " in query or "compare" in query:
			return RetrievalMode.HYBRID
		return RetrievalMode.SEMANTIC


router = QueryRouter()
