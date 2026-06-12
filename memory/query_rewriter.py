# # memory/query_rewriter.py

# import logging
# from collections import deque

# logger = logging.getLogger(__name__)


# class QueryRewriter:

#     def __init__(self, max_history: int = 7):
#         self.max_history = max_history

#     def _extract_context(
#         self,
#         recent_history: list[dict],
#     ) -> set[str]:

#         stopwords = {
#             "the", "is", "in", "on", "of", "and",
#             "a", "to", "for", "who", "what",
#             "which", "them", "those", "these",
#         }

#         context = set()

#         for item in recent_history:
#             query = item["query"]

#             tokens = query.lower().split()

#             for token in tokens:
#                 token = token.strip(".,?!()[]{}")

#                 if (
#                     token
#                     and token not in stopwords
#                     and len(token) > 2
#                 ):
#                     context.add(token)

#         return context

#     def _enrich_query(
#         self,
#         query: str,
#         context: set[str],
#     ) -> str:

#         followup_words = {
#             "which",
#             "these",
#             "them",
#             "one",
#             "those",
#             "their",
#             "they",
#         }

#         lower_query = query.lower()

#         if any(word in lower_query for word in followup_words):

#             if context:

#                 enriched_query = (
#                     f"{query}\n\n"
#                     f"Relevant Context Terms: "
#                     f"{', '.join(sorted(context))}"
#                 )

#                 return enriched_query

#         return query

#     def rewrite_query(
#         self,
#         query: str,
#         history: list[dict],
#         max_history: int = 7,
#     ) -> str:

#         logger.info(
#             "QUERY_REWRITER START | HISTORY_SIZE=%d",
#             len(history),
#         )

#         if not history:
#             logger.info(
#                 "QUERY_REWRITER NO HISTORY | RETURNING ORIGINAL QUERY"
#             )
#             return query

#         recent_history = history[-max_history:]

#         queue = deque(
#             [item["query"] for item in recent_history],
#             maxlen=max_history,
#         )

#         context = self._extract_context(
#             recent_history,
#         )

#         enriched_query = self._enrich_query(
#             query,
#             context,
#         )

#         history_text = "\n".join(
#             f"User: {q}"
#             for q in queue
#         )

#         rewritten_query = f"""
# Conversation History:
# {history_text}

# Current User Query:
# {enriched_query}
# """.strip()

#         logger.info(
#             """
# ================ QUERY REWRITE ================
# USING_HISTORY=%d

# CONTEXT_TERMS=%s

# ORIGINAL QUERY:
# %s

# REWRITTEN QUERY:
# %s
# ==============================================
# """,
#             len(recent_history),
#             sorted(context),
#             query,
#             rewritten_query,
#         )

#         return rewritten_query


# query_rewriter = QueryRewriter()

# memory/query_rewriter.py

import logging
from collections import deque
from observability.tracker import tracker

import spacy

logger = logging.getLogger(__name__)

try:
    nlp = spacy.load("en_core_web_sm")
    logger.info("QUERY_REWRITER spacy model loaded: en_core_web_sm")
except OSError:
    nlp = None
    logger.warning(
        "QUERY_REWRITER spacy model not found | "
        "run: python -m spacy download en_core_web_sm | "
        "falling back to heuristic extraction"
    )


class QueryRewriter:

    def __init__(self, max_history: int = 7):
        self.max_history = max_history

    def _extract_context_heuristic(
        self,
        recent_history: list[dict],
    ) -> set[str]:

        stopwords = {
            "the", "is", "in", "on", "of", "and",
            "a", "to", "for", "who", "what",
            "which", "them", "those", "these",
        }

        context = set()

        for item in recent_history:
            query = item["query"]
            tokens = query.lower().split()
            for token in tokens:
                token = token.strip(".,?!()[]{}")
                if (
                    token
                    and token not in stopwords
                    and len(token) > 2
                ):
                    context.add(token)

        return context

    def _extract_context_spacy(
        self,
        recent_history: list[dict],
    ) -> set[str]:

        context = set()

        for item in recent_history:
            doc = nlp(item["query"])

            for ent in doc.ents:
                cleaned = ent.text.strip(".,?!()[]{}")
                if cleaned:
                    context.add(cleaned)

            for token in doc:
                if (
                    token.pos_ in ("NOUN", "PROPN", "ADJ")
                    and not token.ent_type_
                    and not token.is_stop
                    and len(token.lemma_) > 2
                ):
                    context.add(token.lemma_.lower())

        return context

    def _extract_context(
        self,
        recent_history: list[dict],
    ) -> set[str]:

        if nlp is not None:
            return self._extract_context_spacy(recent_history)

        return self._extract_context_heuristic(recent_history)

    def _enrich_query(
        self,
        query: str,
        context: set[str],
    ) -> str:

        followup_words = {
            "which",
            "these",
            "them",
            "one",
            "those",
            "their",
            "they",
        }

        lower_query = query.lower()

        if any(word in lower_query for word in followup_words):

            if context:

                enriched_query = (
                    f"{query}\n\n"
                    f"Relevant Context Terms: "
                    f"{', '.join(sorted(context))}"
                )

                return enriched_query

        return query

    def rewrite_query(
        self,
        query: str,
        history: list[dict],
        max_history: int = 7,
    ) -> str:

        logger.info(
            "QUERY_REWRITER START | HISTORY_SIZE=%d",
            len(history),
        )

        if not history:
            logger.info(
                "QUERY_REWRITER NO HISTORY | RETURNING ORIGINAL QUERY"
            )
            return query

        recent_history = history[-max_history:]

        queue = deque(
            [item["query"] for item in recent_history],
            maxlen=max_history,
        )

        context = self._extract_context(recent_history)

        enriched_query = self._enrich_query(query, context)

        history_text = "\n".join(
            f"User: {q}"
            for q in queue
        )

        rewritten_query = f"""
Conversation History:
{history_text}

Current User Query:
{enriched_query}
""".strip()

        logger.info(
            """
================ QUERY REWRITE ================
USING_HISTORY=%d

CONTEXT_TERMS=%s

ORIGINAL QUERY:
%s

REWRITTEN QUERY:
%s
==============================================
""",
            len(recent_history),
            sorted(context),
            query,
            rewritten_query,
        )

        tracker.set_tag("query_rewritten", "true" if rewritten_query != query else "false")
        tracker.record("query_rewrite_history_size", float(len(recent_history)))

        return rewritten_query


query_rewriter = QueryRewriter()