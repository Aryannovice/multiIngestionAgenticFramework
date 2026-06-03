from retrieval.retrieval import RetrievalService
from models.schema import QueryRequest, RetrievalMode

service = RetrievalService()

# Build a proper QueryRequest
request = QueryRequest(
    query="Which startup received funding from Tiger Global?",
    top_k=5
)

# Choose the retrieval mode:
# - RetrievalMode.SEMANTIC → searches embeddings/vector index
# - RetrievalMode.STRUCTURED → searches structured metadata (like CSV/SQL)
# - RetrievalMode.HYBRID → combines both
results = service.answer(request, RetrievalMode.STRUCTURED)

print(results)
