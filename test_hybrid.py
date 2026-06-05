from retrieval.retrieval import retrieval_service
from models.schema import QueryRequest, RetrievalMode


def run_stream_test(query: str, mode: RetrievalMode):

    request = QueryRequest(
        query=query,
        top_k=5,
    )

    print("\n" + "=" * 80)
    print(f"MODE: {mode.value}")
    print("=" * 80)

    print("\nQUERY:\n")
    print(query)

    print("\nSTREAMING ANSWER:\n")

    if mode == RetrievalMode.SEMANTIC:

        contexts, citations = (
            retrieval_service._semantic_retrieval(request)
        )

    elif mode == RetrievalMode.STRUCTURED:

        contexts, citations, _ = (
            retrieval_service._structured_retrieval(request)
        )

    else:

        semantic_contexts, semantic_citations = (
            retrieval_service._semantic_retrieval(request)
        )

        structured_contexts, structured_citations, _ = (
            retrieval_service._structured_retrieval(request)
        )

        contexts = semantic_contexts + structured_contexts

        citations = (
            semantic_citations +
            structured_citations
        )

    for token in retrieval_service._compose_answer_stream(
        request.query,
        contexts,
    ):
        print(token, end="", flush=True)

    print("\n")

    print("\nCITATIONS:\n")

    for citation in citations:
        print(
            f"- Source: {citation.source} | "
            f"Reference: {citation.reference}"
        )


if __name__ == "__main__":

    run_stream_test(
        query="How much did Tiger Global invest in education startups like vedantu and why?",
        mode=RetrievalMode.HYBRID,
    )