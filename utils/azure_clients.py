from __future__ import annotations

import logging
from functools import lru_cache

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings


logger = logging.getLogger(__name__)


def _resolve_key_vault_url(settings) -> str | None:
    if settings.azure_key_vault_uri:
        return settings.azure_key_vault_uri if settings.azure_key_vault_uri.startswith("https://") else f"https://{settings.azure_key_vault_uri}.vault.azure.net"
    if settings.azure_key_vault_name:
        return f"https://{settings.azure_key_vault_name}.vault.azure.net"
    return None


def _resolve_search_endpoint(settings) -> str | None:
    if settings.azure_ai_search_endpoint:
        return settings.azure_ai_search_endpoint if settings.azure_ai_search_endpoint.startswith("https://") else f"https://{settings.azure_ai_search_endpoint}.search.windows.net"
    if settings.azure_ai_search_service_name:
        return f"https://{settings.azure_ai_search_service_name}.search.windows.net"
    return None


def _resolve_search_api_key(settings) -> str | None:
    if settings.azure_ai_search_api_key:
        return settings.azure_ai_search_api_key

    secret_name = settings.azure_ai_search_api_key_secret_name
    if not secret_name:
        return None

    try:
        return get_secret_value(secret_name)
    except Exception:
        logger.info("Search API key secret '%s' not available; using AAD credential", secret_name)
        return None


@lru_cache(maxsize=1)
def resolve_docs_index_name() -> str:
    settings = get_settings()
    configured = settings.azure_ai_search_index_docs
    if not configured:
        raise ValueError("AZURE_AI_SEARCH_INDEX is required")
    return configured


@lru_cache(maxsize=1)
def resolve_vector_dimensions(index_name: str | None = None) -> int:
    settings = get_settings()
    target_index = index_name or resolve_docs_index_name()
    index_def = get_search_index_client().get_index(target_index)
    for field in index_def.fields or []:
        if getattr(field, "name", None) == "contentVector" and getattr(field, "vector_search_dimensions", None):
            return int(field.vector_search_dimensions)
    for field in index_def.fields or []:
        dims = getattr(field, "vector_search_dimensions", None)
        if dims:
            return int(dims)
    raise RuntimeError(f"Unable to resolve vector dimensions for index '{target_index}'")


@lru_cache(maxsize=1)
def get_credential() -> DefaultAzureCredential:
    try:
        return DefaultAzureCredential(exclude_interactive_browser_credential=False)
    except Exception as exc:
        logger.exception("Failed to initialize Azure credential")
        raise RuntimeError("Unable to initialize Azure credential chain") from exc


@lru_cache(maxsize=1)
def get_blob_service_client() -> BlobServiceClient:
    settings = get_settings()
    if not settings.azure_storage_account_name:
        raise ValueError("AZURE_STORAGE_ACCOUNT_NAME is required")
    account_url = f"https://{settings.azure_storage_account_name}.blob.core.windows.net"
    try:
        return BlobServiceClient(account_url=account_url, credential=get_credential())
    except Exception as exc:
        logger.exception("Failed to create BlobServiceClient")
        raise RuntimeError("Unable to create blob service client") from exc


@lru_cache(maxsize=2)
def get_search_client(index_name: str) -> SearchClient:
    settings = get_settings()
    endpoint = _resolve_search_endpoint(settings)
    if not endpoint:
        raise ValueError("AZURE_AI_SEARCH_ENDPOINT or AZURE_AI_SEARCH_SERVICE_NAME is required")
    try:
        search_key = _resolve_search_api_key(settings)
        credential = AzureKeyCredential(search_key) if search_key else get_credential()
        return SearchClient(
            endpoint=endpoint,
            index_name=index_name,
            credential=credential,
        )
    except Exception as exc:
        logger.exception("Failed to create SearchClient for index '%s'", index_name)
        raise RuntimeError("Unable to create Azure AI Search client") from exc


@lru_cache(maxsize=1)
def get_search_index_client() -> SearchIndexClient:
    settings = get_settings()
    endpoint = _resolve_search_endpoint(settings)
    if not endpoint:
        raise ValueError("AZURE_AI_SEARCH_ENDPOINT or AZURE_AI_SEARCH_SERVICE_NAME is required")
    try:
        search_key = _resolve_search_api_key(settings)
        credential = AzureKeyCredential(search_key) if search_key else get_credential()
        return SearchIndexClient(endpoint=endpoint, credential=credential)
    except Exception as exc:
        logger.exception("Failed to create SearchIndexClient")
        raise RuntimeError("Unable to create Azure AI Search index client") from exc


@lru_cache(maxsize=1)
def get_secret_client() -> SecretClient | None:
    settings = get_settings()
    vault_url = _resolve_key_vault_url(settings)
    if not vault_url:
        return None
    try:
        return SecretClient(vault_url=vault_url, credential=get_credential())
    except Exception as exc:
        logger.exception("Failed to create Key Vault SecretClient")
        raise RuntimeError("Unable to create key vault client") from exc


@retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
def get_secret_value(secret_name: str) -> str | None:
    secret_client = get_secret_client()
    if secret_client is None:
        logger.info("Key Vault not configured; secret '%s' is unavailable", secret_name)
        return None
    try:
        return secret_client.get_secret(secret_name).value
    except Exception as exc:
        logger.exception("Unable to resolve secret '%s'", secret_name)
        raise RuntimeError(f"Unable to resolve secret {secret_name}") from exc


@lru_cache(maxsize=1)
def get_openai_client() -> AzureOpenAI | None:
    settings = get_settings()
    if not settings.azure_openai_endpoint:
        logger.warning("AZURE_OPENAI_ENDPOINT not configured")
        return None
    try:
        logger.info(
            "Initializing Azure OpenAI client | endpoint=%s | api_version=%s",
            settings.azure_openai_endpoint,
            settings.azure_openai_api_version,
        )

        token_provider = get_bearer_token_provider(
            get_credential(),
            "https://cognitiveservices.azure.com/.default",
        )

        client = AzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            azure_ad_token_provider=token_provider,
        )

        return client

    except Exception as exc:
        logger.exception("Failed to initialize Azure OpenAI client")
        raise RuntimeError("Unable to create Azure OpenAI client") from exc