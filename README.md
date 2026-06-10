# ANAGENTICFRAMEWORK (MULTIAGENT)

An enterprise-style Retrieval-Augmented Generation (RAG) system built using:

* Azure OpenAI
* Azure AI Search
* Microsoft Fabric SQL
* FastAPI
* Hybrid Retrieval Architecture

---

# Features

* Semantic PDF Retrieval
* Structured SQL Retrieval
* Hybrid Retrieval (SQL + Semantic)
* Dynamic SQL Generation using LLMs
* SQL Safety Guardrails
* Citation Support
* Generated SQL Visibility
* Azure Identity Authentication
* Modular Retrieval Architecture
* Multi-Source Ingestion Pipeline
* PDF Chunking & Processing
* CSV/Table-Based Retrieval
* Retrieval Routing Framework

---

# Retrieval Modes

## Semantic Retrieval

Uses vector embeddings and Azure AI Search for semantic PDF/document retrieval.

## Structured Retrieval

Converts natural language into SQL queries and retrieves structured business data from Microsoft Fabric SQL.

## Hybrid Retrieval

Combines semantic reasoning from PDFs with factual structured SQL records.

---

# Multi-Ingestion Architecture

The system supports ingestion from multiple enterprise data sources:

* PDF Documents
* CSV Files
* SQL Tables (Microsoft Fabric Lakehouse / Warehouse)

Each source follows its own preprocessing pipeline:

| Source Type | Processing                          |
| ----------- | ----------------------------------- |
| PDF         | Text Extraction → Chunking          |
| CSV         | Schema Cleaning → Structured Tables |
| SQL         | Relational Query Processing         |

---

# Tech Stack

* Python
* FastAPI
* Azure OpenAI
* Azure AI Search
* Microsoft Fabric SQL
* Azure Blob Storage
* pyodbc
* PyMuPDF
* LangChain

---

# Example Queries

* "What is financial analysis?"
* "Which startups received funding from Tiger Global?"
* "How much did Tiger Global invest in education startups like Vedantu and why?"
* "Summarize the uploaded financial reports."
* "Find startup trends from structured funding datasets."

---

# Run Locally

```bash
uvicorn app.main:app --reload
```

Visit Swagger docs at:

```text
http://127.0.0.1:8000/docs
```

(unless another port is configured)

---

# Repository Structure

```text
ANAGENTICFRAMEWORK (MULTIAGENT)
│
├── config
│   └── settings.py
│
├── embeddings
│   └── embeddings.py
│
├──memory
│   └──context_builder.py
│   └──session_store.py
│   
├── ingestion
│   └── ingestion.py
│
├── models
│   └── schema.py
│
├── observability
│
├── retrieval
│   ├── retrieval.py
│   └── router.py
|   └── cache.py
│
├── scripts
│
├── utils
│   ├── azureclients.py
│   └── utils.py
│
├── app.py
├── README.md
├── requirements.txt
│
├── testcsvretrieval.py
├── testfabricsql.py
├── testhybrid.py
└── testretrieval.py
```

---

# Environment Variables (`.env`)

```env
AZUREOPENAIENDPOINT=
AZUREOPENAIAPIKEY=
AZUREOPENAIDEPLOYMENT=

AZUREAISEARCHENDPOINT=
AZUREAISEARCHAPIKEY=
AZUREAISEARCHINDEX=

FABRICSQLCONNECTION_STRING=
```

---

# Architecture Overview

```text
Azure Blob Storage (RAW)
        ↓
Multi-Source Ingestion
        ↓
Specialized Processing
    ├── PDF Chunking
    ├── CSV Cleaning
    └── SQL Processing
        ↓
Silver Layer (Lakehouse)
        ↓
Embeddings + Metadata
        ↓
Azure AI Search
        ↓
Retrieval Router
        ↓
Azure OpenAI Response Generation
```

---

# License

MIT
