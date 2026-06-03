from __future__ import annotations

import json
import logging
import re
import struct
import time

import pyodbc
from azure.search.documents.models import VectorizedQuery

from config.settings import get_settings
from embeddings.embeddings import EmbeddingService
from models.schema import Citation, QueryRequest, QueryResponse, RetrievalMode
from observability.mlflow_utils import tracker
from utils.azure_clients import get_credential, get_openai_client, get_search_client, get_search_index_client, resolve_docs_index_name, resolve_vector_dimensions


logger = logging.getLogger(__name__)


class RetrievalService:
    

    def __init__(self) -> None:
        self.settings = get_settings()
        self.embedding_service = EmbeddingService()

    def answer(self, request: QueryRequest, mode: RetrievalMode) -> QueryResponse:
        start = time.perf_counter()

        try:
            if mode == RetrievalMode.SEMANTIC:
                contexts, citations = self._semantic_retrieval(request)
                answer = self._compose_answer(request.query, contexts)
            elif mode == RetrievalMode.STRUCTURED:
                contexts, citations = self._structured_retrieval(request)
                answer = self._compose_answer(request.query, contexts)
            else:
                answer, citations = self._hybrid_retrieval(request)

            latency_ms = int((time.perf_counter() - start) * 1000)

            tracker.log_metrics(
                {"query_latency_ms": float(latency_ms)},
                tags={"mode": mode.value},
            )

            return QueryResponse(
                answer=answer,
                mode_used=mode,
                citations=citations,
                latency_ms=latency_ms,
            )

        except Exception as exc:
            logger.exception("Retrieval failed")
            raise RuntimeError("Retrieval failed") from exc

    def _semantic_retrieval(self, request: QueryRequest) -> tuple[list[str], list[Citation]]:
        try:
            index_name = resolve_docs_index_name()
            search_client = get_search_client(index_name)

            index_def = get_search_index_client().get_index(index_name)
            field_names = {field.name for field in (index_def.fields or [])}

            text_field = (
                "content"
                if "content" in field_names
                else next(
                    (name for name in ("content", "chunk", "text", "description") if name in field_names),
                    None,
                )
            )

            source_field = (
                "source"
                if "source" in field_names
                else next(
                    (name for name in ("source", "source_name", "dataset_name", "file_name", "filename") if name in field_names),
                    None,
                )
            )

            vector_field = (
                "contentVector"
                if "contentVector" in field_names
                else next((name for name in field_names if name.lower().endswith("vector")), None)
            )

            if text_field is None:
                return ["Semantic retrieval unavailable"], []

            query_vectors = self.embedding_service.generate_embeddings([request.query])

            if query_vectors and vector_field:
                target_dimensions = resolve_vector_dimensions(index_name)
                query_vector = self.embedding_service._align_vector(query_vectors[0], target_dimensions)

                vector_query = VectorizedQuery(
                    vector=query_vector,
                    k_nearest_neighbors=request.top_k,
                    fields=vector_field,
                )

                results = search_client.search(
                    search_text=None,
                    vector_queries=[vector_query],
                    top=request.top_k,
                )
            else:
                results = search_client.search(
                    search_text=request.query,
                    top=request.top_k,
                )

            contexts: list[str] = []
            citations: list[Citation] = []

            for doc in results:
                passage = str(doc.get(text_field, ""))
                source = str(doc.get(source_field, "unknown"))

                if passage:
                    contexts.append(f"PDF Context:\n{passage}")
                    citations.append(Citation(source=source, reference=source))

            return contexts, citations

        except Exception:
            logger.exception("Semantic retrieval failed")
            return ["Semantic retrieval unavailable"], []

    def _generate_sql(self, question: str) -> str:
        openai_client = get_openai_client()
        deployment = self.settings.azure_openai_chat_deployment

        schema_context = """
    Table: startup_funding

    Columns:
    - sno
    - date
    - startupName
    - industryVertical
    - subvertical
    - citylocation
    - investorsName
    - investmenttype
    - amount
    - remarks
    """

        prompt = f"""
    Convert the user question into SQL.

    Rules:
    - Return ONLY SQL
    - Use valid T-SQL
    - Only SELECT queries
    - Use TOP 10
    - Never hallucinate columns
    
    EXAMPLES:

    Question:
    Which startups received funding from Tiger Global?

    SQL:
    SELECT TOP 10
    startupname,
    industryvertical,
    subvertical,
    citylocation,
    investorsname,
    investmenttype,
    amount,
    date
    FROM startup_funding
    WHERE investorsname LIKE '%Tiger Global%'


    Question:
    Show fintech startups

    SQL:
    SELECT TOP 10
    startupname,
    industryvertical,
    subvertical,
    citylocation,
    investorsname,
    investmenttype,
    amount,
    date
    FROM startup_funding
    WHERE industryvertical LIKE '%FinTech%'

    {schema_context}

    Question:
    {question}
    """

        completion = openai_client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": "You generate safe SQL queries."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=200,
        )

        sql = completion.choices[0].message.content.strip()
        sql = sql.replace("```sql", "").replace("```", "").strip()

        logger.info("Generated SQL: %s", sql)
        return sql
    

    


    def _normalize_sql_columns(self, sql: str) -> str:
        replacements = {
            "startupName": "startupname",
            "investorsName": "investorsname",
            "industryVertical": "industryvertical",
            "subVertical": "subvertical",
            "cityLocation": "citylocation",
            "investmentType": "investmenttype",
            "amountInUSD": "amount",
            "Amount_in_USD": "amount",
            "Startup_Name": "startupname",
            "Investors_Name": "investorsname",
            "Industry_Vertical": "industryvertical",
            "SubVertical": "subvertical",
            "City_Location": "citylocation",
            "Investment_Type": "investmenttype",
        }

        for wrong, correct in replacements.items():
            sql = sql.replace(wrong, correct)

        return sql
    
	
    


    def _structured_retrieval(self, request: QueryRequest) -> tuple[list[str], list[Citation]]:
        try:
            query = request.query.strip()

            if self._looks_like_sql(query):
                sql_query = query
            else:
                sql_query = self._generate_sql(query)
                sql_query = self._normalize_sql_columns(sql_query)
                logger.info("=" * 80)
                logger.info("user query: %s", query)
                logger.info("GENERATED SQL:\n%s", sql_query)
                logger.info("=" *80)
                

            rows = self._execute_fabric_sql(sql_query)
            

            if not rows:
                return ["No structured data found"], []

            contexts: list[str] = []

            for row in rows[:20]:
                startup = row.get("startupname", "Unknown")
                investor = row.get("investorsname", "Unknown")
                amount = row.get("amount", "Unknown")
                industry = row.get("industryvertical", "Unknown")
                city = row.get("citylocation", "Unknown")
                subvertical = row.get("subvertical", "Unknown")
                if not subvertical or subvertical.lower() == "nan":
                    subvertical = "Unknown"
                investment_type = row.get("investmenttype", "Unknown")
                date = row.get("date", "Unknown")

                formatted = (
                    f"Startup: {startup}\n"
                    f"Investor: {investor}\n"
                    f"Industry: {industry}\n"
                    f"City: {city}\n"
                    f"Funding Amount: {amount}\n"
                    f"Subvertical: {subvertical}\n"
                    f"Investment Type: {investment_type}\n"
                    f"Date: {date}\n"
                )

                contexts.append(formatted)
                logger.info("structured is %s", formatted)

            citations = [
                Citation(
                    source="fabric_sql",
                    reference=self.settings.fabric_sql_database or "fabric_sql",
                )
            ]

            return contexts, citations

        except Exception:
            logger.exception("Structured retrieval failed")
            return ["Sql retrieval failed , No data unavailable"], []

    def _looks_like_sql(self, query: str) -> bool:
        return bool(re.match(r"^\s*select\s+", query, flags=re.IGNORECASE))

    def _execute_fabric_sql(self, query: str) -> list[dict]:
        if not self.settings.fabric_sql_server or not self.settings.fabric_sql_database:
            raise RuntimeError("Fabric SQL server/database is not configured")
        if not self._looks_like_sql(query):
            raise RuntimeError("Only SELECT statements are allowed")

        driver = self._resolve_sql_driver()

        token = get_credential().get_token("https://database.windows.net/.default")
        token_bytes = token.token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        attrs_before = {1256: token_struct}  # SQL_COPT_SS_ACCESS_TOKEN

        conn_str = (
            f"Driver={{{driver}}};"
            f"Server=tcp:{self.settings.fabric_sql_server},1433;"
            f"Database={self.settings.fabric_sql_database};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )

        with pyodbc.connect(conn_str, attrs_before=attrs_before) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                if cursor.description is None:
                    return []
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchmany(50)
                logger.info("SQL returned %d rows", len(rows))
                if rows:
                    logger.info("sample rows : %s", rows[0])
                return [dict(zip(columns, row)) for row in rows]

    def _resolve_sql_driver(self) -> str:
        available = set(pyodbc.drivers())
        configured = self.settings.fabric_sql_driver.strip()
        if configured and configured in available:
            return configured
        for candidate in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"):
            if candidate in available:
                return candidate
        raise RuntimeError(f"No supported SQL ODBC driver found. Installed drivers: {sorted(available)}")

    def _hybrid_retrieval(self, request: QueryRequest) -> tuple[str, list[Citation]]:
        try:
            semantic_contexts, semantic_citations = self._semantic_retrieval(request)
            structured_contexts, structured_citations = self._structured_retrieval(request)

            semantic_text = "\n\n".join(semantic_contexts)
            structured_text = "\n\n".join(structured_contexts)

            combined_context = f"""
            PDF SEMANTIC CONTEXT:

            {semantic_text}

            STRUCTURED SQL RECORDS:
            {structured_text}
          """
            
            answer = self._compose_answer(
            request.query,
            [combined_context],   # <- IMPORTANT
        )

            citations = semantic_citations + structured_citations
            logger.info(
            "Hybrid retrieval got %d semantic contexts and %d structured contexts",
            len(semantic_contexts),
            len(structured_contexts),
        )


            return answer, citations

        except Exception:
            logger.exception("Hybrid retrieval failed")
            return "Hybrid retrieval unavailable", []

    def _compose_answer(self, query: str, contexts: list[str]) -> str:
        openai_client = get_openai_client()
        deployment = self.settings.azure_openai_chat_deployment
        if openai_client is None or not deployment:
            return f"No model endpoint configured yet. Query: {query}\nContext size: {len(contexts)}"

        try:
            context_text = "\n\n".join(contexts[:8])
            logger.info("compose answer with %d contexts and %d chars", len(contexts), len(context_text))
            completion = openai_client.chat.completions.create(
                model=deployment,
                messages = [
    {
    "role": "system",
    "content": (
        "You are an enterprise hybrid retrieval assistant.\n\n"

        "You receive:\n"
        "1. PDF semantic context\n"
        "2. Structured SQL business records\n\n"

        "CRITICAL RULES:\n"
        "- NEVER omit structured SQL fields when present\n"
        "- Preserve city, date, amount, investment type, industry, and subvertical\n"
        "- If structured records exist, prioritize them for factual answers\n"
        "- Use PDF context only for explanation/background\n"
        "- Do not summarize away structured business fields\n"
        "- Present structured data clearly in bullet/tabular format\n"
        "- Never hallucinate missing values\n"
    ),
},
    {
        "role": "user",
        "content": f"Question: {query}\n\nContext:\n{context_text}",
    },
			
],
			
                max_tokens=600,
                temperature=0.1,
            )
            response_text = completion.choices[0].message.content.strip()

            logger.info(
                "Generation succeeded | deployment=%s | contexts=%d",
                deployment,
                len(contexts),
            )

            return response_text
        except Exception:
            logger.exception("OpenAI synthesis failed; returning context fallback")
            return f"Unable to synthesize with model. Retrieved {len(contexts)} context chunks."


retrieval_service = RetrievalService()
