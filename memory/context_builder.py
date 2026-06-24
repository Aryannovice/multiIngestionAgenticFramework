import logging
import tiktoken

logger = logging.getLogger(__name__)


class ContextBuilder:

    def count_tokens(self, text: str, model: str = "gpt-4o") -> int:
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def _trim_history_by_tokens(
        self,
        history: list[dict],
        max_tokens: int = 3000,
    ) -> list[dict]:
        if not history:
            return []

        selected = []
        total_tokens = 0

        for item in reversed(history):
            query = item.get("query", "")
            response = item.get("response", "")
            turn_text = f"{query}\n{response}"
            turn_tokens = self.count_tokens(turn_text)

            if selected and total_tokens + turn_tokens > max_tokens:
                break

            selected.append(item)
            total_tokens += turn_tokens

        logger.info(
            "CONTEXT_BUILDER TRIM | TURNS_SELECTED=%d | TOKENS_USED=%d / %d",
            len(selected),
            total_tokens,
            max_tokens,
        )

        return list(reversed(selected))

    def build_context(
        self,
        history: list[dict],
        query: str,
        max_history: int = 10,
        retrieved_context: list[str] | None = None,
    ) -> list[dict]:

        history = self._trim_history_by_tokens(
            history,
            max_tokens=3000,
        )

        messages = [
            {
                "role": "system",
                "content": "System instructions here",
            }
        ]

        for item in history:
            messages.append({"role": "user", "content": item["query"]})
            messages.append({"role": "assistant", "content": item["response"]})

        # inject retrieved context into the final user message
        # rather than as a second system message
        if retrieved_context:
            context_block = "\n\n".join(retrieved_context)
            final_user_message = (
                f"Relevant context:\n{context_block}\n\n"
                f"Question: {query}"
            )
        else:
            final_user_message = query

        messages.append({"role": "user", "content": final_user_message})

        logger.info(
            "CONTEXT_BUILDER DONE | HISTORY_TURNS=%d | HAS_RETRIEVED_CONTEXT=%s",
            len(history),
            bool(retrieved_context),
        )

        return messages