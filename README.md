**Project Status**

**Working:**
- **Health endpoint:** `GET /health` returns service status.
- **Ingestion API:** `POST /ingestion/jobs` enqueues ingestion jobs (PDF/CSV) and job lifecycle (`queued` -> `running` -> `succeeded`/`failed`) is tracked.
- **Azure auth (local):** `DefaultAzureCredential` works via local `az login` and name-based endpoint derivation for Key Vault and AI Search.
- **Blob access:** App can list/read blobs from the configured storage account/container.
- **Retrieval routing:** Query router delegates to `structured` (Fabric stub) or `semantic` (Azure AI Search) paths and returns `citations`.

**Partially implemented / Not yet configured:**
- **Model generation:** OpenAI/Foundry generation call is wired in code, but you must configure `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_CHAT_DEPLOYMENT` (or store the key in Key Vault) to get generated answers instead of the fallback message.
- **Fabric SQL execution:** The Fabric (Lakehouse) SQL execution layer is a placeholder. There is a direct test script pattern available to verify connectivity; the actual production query wiring is TODO.
- **Index creation / full indexing:** Azure AI Search index bootstrap and indexing jobs are not yet automated.
- **Persistent queue/worker:** Current job registry is in-memory for smoke tests — needs a durable queue (e.g., Azure Storage Queue, Service Bus, or DB) for production.
- **PDF OCR/text extraction enhancements:** Basic PDF flow exists but may report `processed_records=0` depending on blob contents; robust OCR integration is TODO.

**Files of interest:**
- `app.py`: API entrypoint and routes. See [app.py](app.py#L1).
- `retrieval/retrieval.py`: Retrieval and generation logic. See [retrieval/retrieval.py](retrieval/retrieval.py#L1).
- `utils/azure_clients.py`: Azure client factories (Blob, Search, Key Vault, OpenAI). See [utils/azure_clients.py](utils/azure_clients.py#L1).
- `TODO.md`: Key Vault and smoke-test steps I added for you. See [TODO.md](TODO.md#L1).

**What is `jobid.txt`?**
- `jobid.txt` is a temporary helper file used during smoke tests to store the last ingestion `job_id` returned by `POST /ingestion/jobs`. The test script in the terminal writes the id there so subsequent `GET /ingestion/jobs/<id>` calls can poll the status easily.
- You can safely delete `jobid.txt` at any time. It is only an ephemeral convenience for manual testing.

**Quick smoke-test (copy/paste PowerShell)**

```powershell
# activate venv
& ".\.venv\Scripts\Activate.ps1"

# start server (in background terminal)
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# health
curl http://127.0.0.1:8000/health

# enqueue ingestion job and save id
$body = @{source_type='pdf'; blob_path='sample.pdf'} | ConvertTo-Json
$resp = Invoke-RestMethod -Uri http://127.0.0.1:8000/ingestion/jobs -Method Post -Body $body -ContentType 'application/json'
$resp.job_id > jobid.txt

# poll once
$job = Get-Content jobid.txt -Raw; Invoke-RestMethod -Uri "http://127.0.0.1:8000/ingestion/jobs/$job"

# run query (use JSON key `query`)
curl -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" -d '{"query":"What is the startup funding total?"}'
```

**Next steps to enable generation (summary)**
- Store your model key in Key Vault (`OPENAI-API-KEY`) and set `AZURE_KEY_VAULT_NAME` in `.env`.
- Add `AZURE_OPENAI_ENDPOINT` and `AZURE_OPENAI_CHAT_DEPLOYMENT` to `.env` (or set equivalent Key Vault secrets).
- Restart server and re-run the smoke test — `/query` should return a generated answer and `mode_used` indicating generation.

If you want, I can run the generation test for you after you set the Key Vault secret and `.env` values — just tell me when it's done.
