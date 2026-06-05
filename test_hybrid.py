
from retrieval.retrieval import retrieval_service
from models.schema import QueryRequest, RetrievalMode


def run_test(query: str, mode: RetrievalMode):

    request = QueryRequest(
        query=query,
        top_k=5,
    )

    response = retrieval_service.answer(
        request=request,
        mode=mode,
    )

    print("\n" + "=" * 80)
    print(f"MODE: {mode.value}")
    print("=" * 80)

    print("\nQUERY:\n")
    print(query)

    print("\nANSWER:\n")
    print(response.answer)

    print("\nCITATIONS:\n")

    for citation in response.citations:
        print(
            f"- Source: {citation.source} | "
            f"Reference: {citation.reference}"
        )

    print(f"\nLATENCY: {response.latency_ms} ms")


if __name__ == "__main__":

    # -------------------------
    # SEMANTIC TEST
    # -------------------------

    # run_test(
    #     query="What is financial analysis?",
    #     mode=RetrievalMode.SEMANTIC,
    # )

    # -------------------------
    # STRUCTURED TEST
    # -------------------------

    # run_test(
    #     query="Which startups received funding from Tiger Global?",
    #     mode=RetrievalMode.STRUCTURED,
    # )

    # -------------------------
    # HYBRID TEST
    # -------------------------

    run_test(
        query="How much did Tiger Global invest in education startups like vedantu and why?",
        mode=RetrievalMode.HYBRID,
    )
