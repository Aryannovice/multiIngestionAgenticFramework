class ContextBuilder:
    def build_context(
        self,
        history: list[dict],
        query: str,
        max_history: int = 10,
        retrieved_context: list[str] | None = None,
    ):
        history = history[-max_history:]

        messages = [
            {
                "role": "system",
                "content": "System instructions here",
            }
        ]

        for item in history:
            messages.append(
                {
                    "role": "user",
                    "content": item["query"],
                }
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": item["response"],
                }
            )

        if retrieved_context:
            messages.append(
                {
                    "role": "system",
                    "content": "\n\n".join(retrieved_context),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": query,
            }
        )

        return messages