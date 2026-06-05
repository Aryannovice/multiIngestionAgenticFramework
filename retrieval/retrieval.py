from __future__ import annotations
# from retrieval.cache import RedisCache
import json
import logging
from pydoc import doc
import re
import struct
import time
from concurrent.futures import ThreadPoolExecutor
import token
from flask import ctx
from flask import ctx
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
        # self.cache = RedisCache()
    

    def answer(self, request: QueryRequest, mode: RetrievalMode) -> QueryResponse:
        overall_start = time.perf_counter()
        generated_sql = None
        citations = None
        
        try:
            timings = {
            "embed": 0,
            "search": 0,
            "sql_gen": 0,
            "sql_exec": 0,
            "generation": 0,
        }
            
            if mode == RetrievalMode.SEMANTIC:
                search_start = time.perf_counter()
                contexts, citations = self._semantic_retrieval(request)
                timings["search"] = int((time.perf_counter() - search_start) * 1000)

            
                generation_start = time.perf_counter()
                answer = self._compose_answer(request.query, contexts)
                timings["generation"] = int((time.perf_counter() - generation_start) * 1000)
                
            elif mode == RetrievalMode.STRUCTURED:
                sql_gen_start = time.perf_counter()
                contexts, citations, generated_sql = self._structured_retrieval(request)
                timings["sql_gen"] = int((time.perf_counter() - sql_gen_start) * 1000)

                generation_start = time.perf_counter()
                answer = self._compose_answer(request.query, contexts)
                timings["generation"] = int((time.perf_counter() - generation_start) * 1000)
                
            else:
                hybrid_start = time.perf_counter()
                answer, citations, generated_sql = self._hybrid_retrieval(request)
                timings["hybrid"] = int((time.perf_counter() - hybrid_start) * 1000)

            latency_ms = int((time.perf_counter() - overall_start) * 1000)

            logger.info(
            " total=%dms",
            latency_ms,
        )
            tracker.log_metrics(
            {"query_latency_ms": float(latency_ms)},
            tags={"mode": mode.value},
        )
            

            return QueryResponse(
                answer=answer,
                mode_used=mode,
                citations=citations,
                latency_ms=latency_ms,
                generated_sql=generated_sql,
            )

        except Exception as exc:
            logger.exception("Retrieval failed")
            raise RuntimeError("Retrieval failed") from exc
    def _rerank_results(self, query : str, results: list, top_n: int = 5,):
        """lightweight re ranker"""

        if not results:
            return []
        
        openai_client = get_openai_client()

        if openai_client is None:
            return results[:top_n]
        
        text_blocks = []

        for idx, doc in enumerate(results, start = 1):
            content = doc.get("content", "")
            if len(content) > 1200:
                content = content[:1200]
            text_blocks.append(f"Result {idx}:\n{content}")

        prompt = f"""
        Query: {query}

        Below are retreived chunks.
        Rank them from MOST relevant to LEAST relevant.

        Return only a comma separated list of chunk numbers.

        Example:
        3,1,5,2,4

        Chunks:
        {chr(10).join(text_blocks)}
        """

        try:
            response = openai_client.chat.completions.create(
                model=self.settings.azure_openai_chat_deployment,
                messages=[
                    {
                        "role": "user", "content":( "You are a retrieval reranker. Return only chunk numbers."),
                     },
                     {
                         "role" : "user",
                         "content" : prompt
                     },
                ],
                temperature = 0,
                max_tokens = 50,
            )

            ranking_text = response.choices[0].message.content.strip()

            ranked_indices = []

            ranked_indices = [
                int(x) for x in re.findall(r"\d+", ranking_text)
            ]

            reranked = []

            for idx in ranked_indices:
                if 1 <= idx <= len(results):
                    reranked.append(results[idx-1])

            if not reranked:
                return results[:top_n]
            
            return reranked[:top_n]
        
        except Exception:
            logger.exception("Re ranking failed, returning original order")
            return results[:top_n]

        except Exception as e:
            logger.exception("Failed to create chat completion")
            raise RuntimeError("Failed to create chat completion") from e

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
            
            embed_start = time.perf_counter()
            query_vectors = self.embedding_service.generate_embeddings([request.query])
            embed_ms = int((time.perf_counter() - embed_start) * 1000)
            logger.info("Generated query embedding in %d ms", embed_ms)

            search_start = time.perf_counter()
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
            results = list(results)
            results = self._rerank_results(request.query, results, top_n = 5)
            search_ms = int((time.perf_counter() - search_start) * 1000)
            logger.info("Executed search in %d ms and got %d results", search_ms, len(results))

            

            processs_start = time.perf_counter()
            def process_job(doc):
                source = doc.get(source_field, "")
                passage = doc.get(text_field, "Unknown")

                if passage:
                    return f"PDF Context:\n{passage}", Citation(source=source, reference=source)
                else:
                    return None, None

            contexts: list[str] = []
            citations: list[Citation] = []

            # result_list = list(results)

            # max_workers = min(15, len(result_list))

            with ThreadPoolExecutor(max_workers = 15) as executor:
                for result in executor.map(process_job, results):
                    if result:
                        ctx, cix = result
                        contexts.append(ctx)
                        citations.append(cix)

            process_ms = int((time.perf_counter() - processs_start) * 1000)
            logger.info("Processed search results in %d ms", process_ms)

            return contexts, citations

        except Exception:
            logger.exception("Semantic retrieval failed")
            return ["Semantic retrieval unavailable"], []

    def _generate_sql(self, question: str) -> str:
        # cached = self.cache.get("sql", question)
        # if cached:
        #     logger.info("Cache hit for SQL generation")
        #     return cached
        
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
        # self.cache.set("sql", question, sql)
        logger.info("Cached SQL generation result")
        return sql
    
    def _validate_sql_query(self, sql:str)->None:

        normalized =  sql.lower().strip()

        forbidden_keywords = [
        "insert ",
        "update ",
        "delete ",
        "drop ",
        "alter ",
        "truncate ",
        "create ",
        "merge ",
        "exec ",
        "execute ",
        "grant ",
        "revoke ",
        "commit ",
        "rollback ",
        
    ]
        
        for keyword in forbidden_keywords:
          
          if keyword in normalized:

            raise RuntimeError(
                f"Unsafe SQL detected: {keyword.strip()}"
            )

        if not normalized.startswith("select"):
           

           raise RuntimeError("Only SELECT queries allowed")
    

    


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
                sql_gen_start = time.perf_counter()
                sql_query = self._generate_sql(query)
                sql_query = self._normalize_sql_columns(sql_query)
                logger.info("=" * 80)
                logger.info("user query: %s", query)
                logger.info("GENERATED SQL:\n%s", sql_query)
                logger.info("=" *80)
                sql_gen_ms = int((time.perf_counter() - sql_gen_start) * 1000)
                logger.info("Generated SQL in %d ms", sql_gen_ms)
            sql_execute_start = time.perf_counter()
            rows = self._execute_fabric_sql(sql_query)
            sql_execute_ms = int((time.perf_counter() - sql_execute_start) * 1000)
            logger.info("Executed SQL in %d ms", sql_execute_ms)

            if not rows:
                return ["No structured data found"], [], sql_query

            contexts: list[str] = []

            def format_row(row: dict) -> str:

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
                logger.info("structured is %s", formatted)
                return formatted
            
            contexts = [format_row(row) for row in rows[:45]]

            citations = [
                Citation(
                    source="fabric_sql",
                    reference=self.settings.fabric_sql_database or "fabric_sql",
                )
            ]

            return contexts, citations, sql_query

        except Exception:
            logger.exception("Structured retrieval failed")
            return ["Sql retrieval failed , No data unavailable"], [], None

    def _looks_like_sql(self, query: str) -> bool:
        return bool(re.match(r"^\s*select\s+", query, flags=re.IGNORECASE))

    def _execute_fabric_sql(self, query: str) -> list[dict]:
        if not self.settings.fabric_sql_server or not self.settings.fabric_sql_database:
            raise RuntimeError("Fabric SQL server/database is not configured")
        if not self._looks_like_sql(query):
            raise RuntimeError("Only SELECT statements are allowed")

        driver = self._resolve_sql_driver()
        token_start = time.perf_counter()
        token = get_credential().get_token("https://database.windows.net/.default")
        toekn_recieved = int((time.perf_counter() - token_start) * 1000)
        logger.info("Acquired SQL access token in %d ms", toekn_recieved)
        token_bytes = token.token.encode("utf-16-le")
        token_struct = struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)
        attrs_before = {1256: token_struct}  # SQL_COPT_SS_ACCESS_TOKEN

        conn_str = (
            f"Driver={{{driver}}};"
            f"Server=tcp:{self.settings.fabric_sql_server},1433;"
            f"Database={self.settings.fabric_sql_database};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )
        pyodbc_connect_start = time.perf_counter()
        with pyodbc.connect(conn_str, attrs_before=attrs_before) as conn:
            pyodbc_connect_ms = int((time.perf_counter() - pyodbc_connect_start) * 1000)
            logger.info("Connected to SQL in %d ms", pyodbc_connect_ms)
            query_ms = time.perf_counter()
            with conn.cursor() as cursor:
                self._validate_sql_query(query)
                
                cursor.execute(query)
                if cursor.description is None:
                    return []
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchmany(50)
                query_returned_ms = int((time.perf_counter() - query_ms) * 1000)
                logger.info("SQL query executed and returned in %d ms", query_returned_ms)
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

            reasoning_keywords = [
                "why",
                "reason",
                "explain",
                "compare",
                "difference",
                "vs ",
                "versus ",
            ]
            requires_reasoning = any(keyword in request.query.lower() for keyword in reasoning_keywords)
            semantic_request = request.model_copy()

            if requires_reasoning:
               semantic_request.top_k = 8
            else:
               semantic_request.top_k = 4

            with ThreadPoolExecutor(max_workers = 2) as executor:
                future_semantic = executor.submit(self._semantic_retrieval, semantic_request)
                future_structured = executor.submit(self._structured_retrieval, request)
            semantic_contexts, semantic_citations = future_semantic.result()
            structured_contexts, structured_citations, generated_sql = future_structured.result()



            semantic_text = "\n\n".join(semantic_contexts)
            structured_text = "\n\n".join(structured_contexts)

            if requires_reasoning:
               
               synthesis_hint = """
Use SQL records as the primary source of factual information.

If SQL records contain funding amounts, investors, dates, or startup names,
those values take precedence over all other context.

Use PDF context only to explain business reasoning or industry background.

Do not infer investment amounts that are not explicitly stated.

If multiple investors are listed in a funding round,
do not attribute the entire funding amount to a single investor.
"""
            else:
               
               synthesis_hint = """
The user is asking primarily for factual business data.
Prioritize SQL structured records.
"""

            combined_context = f"""

            {synthesis_hint}
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


            return answer, citations, generated_sql

        except Exception:
            logger.exception("Hybrid retrieval failed")
            return "Hybrid retrieval unavailable", [], None
        
    def _hybrid_retrieval_stream(self, request: QueryRequest):
        try:

            reasoning_keywords = [
                "why",
                "reason",
                "explain",
                "compare",
                "difference",
                "vs ",
                "versus ",
            ]
            requires_reasoning = any(keyword in request.query.lower() for keyword in reasoning_keywords)
            semantic_request = request.model_copy()

            if requires_reasoning:
               semantic_request.top_k = 8
            else:
               semantic_request.top_k = 4

            with ThreadPoolExecutor(max_workers = 2) as executor:
                future_semantic = executor.submit(self._semantic_retrieval, semantic_request)
                future_structured = executor.submit(self._structured_retrieval, request)
            semantic_contexts, semantic_citations = future_semantic.result()
            structured_contexts, structured_citations, generated_sql = future_structured.result()



            semantic_text = "\n\n".join(semantic_contexts)
            structured_text = "\n\n".join(structured_contexts)

            if requires_reasoning:
               
               synthesis_hint = """
Use SQL records as the primary source of factual information.

If SQL records contain funding amounts, investors, dates, or startup names,
those values take precedence over all other context.

Use PDF context only to explain business reasoning or industry background.

Do not infer investment amounts that are not explicitly stated.

If multiple investors are listed in a funding round,
do not attribute the entire funding amount to a single investor.
"""
            else:
               
               synthesis_hint = """
The user is asking primarily for factual business data.
Prioritize SQL structured records.


"""

            logger.info("Structured contexts:")
            for ctx in structured_contexts[:3]:
               
               logger.info(ctx)
            combined_context = f"""

            {synthesis_hint}
            PDF SEMANTIC CONTEXT:

            {semantic_text}

            STRUCTURED SQL RECORDS:
            {structured_text}
          """
            logger.info("=" * 80)
            logger.info("COMBINED CONTEXT")
            logger.info(combined_context)
            logger.info("=" * 80)

            logger.info(
    "Hybrid stream got %d semantic citations and %d structured citations",
    len(semantic_citations),
    len(structured_citations),
)
            
            logger.info(
    "Generated SQL for stream:\n%s",
    generated_sql,


)
            
            logger.info(
    "Sending %d semantic contexts and %d structured contexts to LLM",
    len(semantic_contexts),
    len(structured_contexts),
)
            
            yield "\n=== GENERATED SQL ===\n"

            yield generated_sql

            yield "\n\n=== ANSWER ===\n\n"

            for token in self._compose_answer_stream( request.query,[combined_context], ):
                
                yield token
        
        except Exception:
            logger.exception("Hybrid retrieval failed")
            return iter(["Hybrid retrieval unavailable"])


    def _compose_answer(self, query: str, contexts: list[str]) -> str:
        generation_start = time.perf_counter()
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
			
                max_tokens=250,
                temperature=0.1,
            )
            response_text = completion.choices[0].message.content.strip()

            logger.info(
                "Generation succeeded | deployment=%s | contexts=%d",
                deployment,
                len(contexts),
            )
            generation_ms = (int((time.perf_counter()-generation_start) *1000))
            logger.info("Generated answer in %d ms", generation_ms)

            return response_text
        except Exception:
            logger.exception("OpenAI synthesis failed; returning context fallback")
            return f"Unable to synthesize with model. Retrieved {len(contexts)} context chunks."
        

    def _compose_answer_stream(self, query: str, contexts: list[str]):
        openai_client = get_openai_client()

        if openai_client is None:
            yield "Model Unavailable"
            return 
        
        context_text = "\n\n".join(contexts[:8])
        stream_start = time.perf_counter()
        first_token = None

        

        stream = openai_client.chat.completions.create(
            model = self.settings.azure_openai_chat_deployment,
            messages = [
                {
                    "role":"system",
                    "content":(
                        "You are an enterprise hybrid retrieval assistant.\n\n"

            "You receive:\n"
            "1. PDF semantic context\n"
            "2. Structured SQL business records\n\n"

            "CRITICAL RULES:\n"

            "- Structured SQL records are the authoritative source for factual data.\n"
            "- Preserve startup name, city, date, amount, industry, subvertical, investor names, and investment type exactly as provided.\n"
            "- Never modify funding amounts.\n"
            "- Never convert currencies.\n"
            "- Never infer missing investor-specific contributions.\n"
            "- If multiple investors are listed, do not attribute the full funding amount to a single investor.\n"
            "- If information is unavailable, explicitly say so.\n"
            "- Use PDF context only for industry background, explanation, or reasoning.\n"
            "- Do not hallucinate facts not present in the retrieved context.\n"
            "- When answering funding questions, first present the retrieved SQL facts, then provide explanation if relevant.\n"
            "- Do not speculate about business motivations unless explicitly stated in the context.\n"
                    ),
                },
                {
                    "role":"user",
                        "content": f"Question: {query}\n\nContext:\n{context_text}",
                },
            ],
            temperature = 0.1,
            stream = True,

        )

        

        buffer = ""
        last_token_time = time.perf_counter()
        for chunk in stream:

            if not chunk.choices:
                print("EMPTY CHOICES EVENT")
                continue
            # print(repr(chunk))

            delta = chunk.choices[0].delta
            # print("DELTA:", delta)
            # print(repr(chunk))
            if delta and delta.content:

                if first_token is None:
                   
                    
                   first_token = time.perf_counter()
                   logger.info(
                f"First token latency: {(first_token - stream_start)*1000:.0f} ms"
            )
                   
                current = time.perf_counter()
                gap_ms = (current - last_token_time) * 1000
                if gap_ms > 500:
                   
                   logger.info(f"Large token gap: {gap_ms:.0f} ms")
                   last_token_time = current

                logger.info(
            "TOKEN CHUNK ARRIVED %s",
            time.perf_counter()
        )
                buffer += delta.content
#                 logger.info(
#     "CHUNK: %s",
#     repr(delta.content)
# )
                if len(buffer) > 30:
                   yield buffer
                   buffer = ""


retrieval_service = RetrievalService()
