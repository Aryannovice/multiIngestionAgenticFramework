# router.py
print("\nROUTER MODULE LOADED\n")
from models.schema import QueryRequest, RetrievalMode
from memory.context_builder import ContextBuilder
import logging

logger = logging.getLogger(__name__)
STRUCTURED_HINTS = {
    "sum", "avg", "average", "count", "total",
    "group by", "table", "dataset", "column", "rows", "sql",
}

class QueryRouter:
    def classify(self, request: QueryRequest, history: list[dict]) -> RetrievalMode:
        if request.mode_hint:
            return request.mode_hint

        query = request.query.lower()
        if any(hint in query for hint in STRUCTURED_HINTS):
            return RetrievalMode.STRUCTURED
        if " and " in query or "compare" in query:
            return RetrievalMode.HYBRID

        if history:
            logger.info(
    "Router received history size=%d",
    len(history),
)
            logger.info(
        "Last query=%s",
        history[-1]["query"],
    )
            last_query = history[-1]["query"].lower()
            logger.info(
            f"Last query from history: {last_query}"
)
            if any(hint in last_query for hint in STRUCTURED_HINTS):
                return RetrievalMode.STRUCTURED
            if " and " in last_query or "compare" in last_query:
                return RetrievalMode.HYBRID

        return RetrievalMode.SEMANTIC

    
# Instantiate a global router object
router = QueryRouter()
