**Store model key in Key Vault and enable generation — Steps**

- **Prerequisites**: `az login` completed in the terminal you will use; your account has Key Vault `get` secret permission (or ask IT to grant access).

- **1) Store the model key in Key Vault** (PowerShell):

```powershell
# replace values inside <> before running
az keyvault secret set --vault-name AZURE-4-O-MINI-KEY --name OPENAI-API-KEY --value "<YOUR_OPENAI_KEY>"
```

- **2) Add runtime config to `.env`** (project root):

Add these lines to `.env` (or set equivalent environment variables):

```
AZURE_OPENAI_ENDPOINT=https://<your-openai-endpoint>
AZURE_OPENAI_CHAT_DEPLOYMENT=<deployment-name>
AZURE_OPENAI_API_VERSION=2023-05-15
AZURE_KEY_VAULT_NAME=AZURE-4-O-MINI-KEY
```

- **3) Verify Key Vault secret is accessible (quick check)**:

```powershell
# confirm Key Vault secret exists
az keyvault secret show --vault-name AZURE-4-O-MINI-KEY --name OPENAI-API-KEY

# quick python check using the repo helper (requires same terminal with az login)
python -c "from utils.azure_clients import get_secret_value; print(get_secret_value('OPENAI-API-KEY'))"
```

- **4) Restart the app and smoke-test generation**:

```powershell
# activate venv and start server
& ".\.venv\Scripts\Activate.ps1"
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# in another terminal (or after server starts):
# health
curl http://127.0.0.1:8000/health

# test query (expects generated answer if model/deployment + KV secret configured)
curl -X POST http://127.0.0.1:8000/query -H "Content-Type: application/json" -d '{"query":"What is the startup funding total?"}'
```

- **5) Troubleshooting**:
- If `get_secret_value` prints errors: confirm `az login` and that your principal has `get` permission on the Key Vault secrets.
- If `/query` still returns the fallback message: confirm `.env` values loaded and `AZURE_OPENAI_CHAT_DEPLOYMENT` matches your deployment name.
- If Azure SDK auth fails: ensure you run `az login` in the same shell session and restart the server after login.

- **6) Optional (ask IT)**: If you cannot access Key Vault, ask IT to grant your user `Key Vault Secrets User` role (or equivalent) scoped to `AZURE-4-O-MINI-KEY`.

---

When you complete steps 1–3, reply here and I will: (A) run the smoke test for generation from my side, or (B) guide you through any errors you see. If you want, I can also add a small one-shot PowerShell script to automate the verification steps.