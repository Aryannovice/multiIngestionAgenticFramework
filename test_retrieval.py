from retrieval.retrieval import RetrievalService
from models.schema import QueryRequest, RetrievalMode

service = RetrievalService()

# Build a proper QueryRequest
request = QueryRequest(query="What is data analysis in finance?", top_k=5)

# Call the correct method
results = service.answer(request, RetrievalMode.SEMANTIC)

print(results)
