from functools import lru_cache
import os
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from observability.tracker import tracker

load_dotenv()

class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

	app_name: str = Field(default="anagenticframework", alias="APP_NAME")
	app_env: str = Field(default="dev", alias="APP_ENV")
	log_level: str = Field(default="INFO", alias="LOG_LEVEL")

	azure_subscription_id: str | None = Field(default=None, alias="AZURE_SUBSCRIPTION_ID")
	azure_resource_group: str | None = Field(default=None, alias="AZURE_RESOURCE_GROUP")
	azure_storage_account_name: str = Field(default="", alias="AZURE_STORAGE_ACCOUNT_NAME")
	azure_storage_container: str = Field(default="", alias="AZURE_STORAGE_CONTAINER")
	azure_blob_pdf_prefix: str = Field(default="pdf", alias="AZURE_BLOB_PDF_PREFIX")
	azure_blob_csv_prefix: str = Field(default="csv", alias="AZURE_BLOB_CSV_PREFIX")

	azure_key_vault_name: str | None = Field(default=None, alias="AZURE_KEY_VAULT_NAME")
	azure_key_vault_uri: str | None = Field(default=None, alias="AZURE_KEY_VAULT_URI")
	azure_ai_search_service_name: str | None = Field(default=None, alias="AZURE_AI_SEARCH_SERVICE_NAME")
	azure_ai_search_endpoint: str | None = Field(default=None, alias="AZURE_AI_SEARCH_ENDPOINT")
	azure_ai_search_api_key: str | None = Field(default=None, alias="AZURE_AI_SEARCH_API_KEY")
	azure_ai_search_api_key_secret_name: str = Field(
		default="AI-SEARCH", alias="AZURE_AI_SEARCH_API_KEY_SECRET_NAME"
	)
	azure_ai_search_index_docs: str = Field(default="txt-rfp-index", alias="AZURE_AI_SEARCH_INDEX")
	azure_ai_search_index_dataset_meta: str = Field(
		default="dataset_metadata", alias="AZURE_AI_SEARCH_INDEX_DATASET_META"
	)

	azure_openai_endpoint: str | None = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
	azure_openai_api_version: str = Field(default="2024-10-21", alias="AZURE_OPENAI_API_VERSION")
	azure_openai_chat_deployment: str | None = Field(default=None, alias="AZURE_OPENAI_CHAT_DEPLOYMENT")
	azure_openai_embedding_deployment: str | None = Field(
		default=None, alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
	)

	
	##DATABASE_URL
	##db_url: str = Field(default='postgresql://ayush:a1b2c3@localhost:5432/agenticframeworkdb', alias="DATABASE_URL")

	fabric_sql_server: str = Field(default="", alias="FABRIC_SQL_SERVER")
	fabric_sql_database: str = Field(default="", alias="FABRIC_SQL_DATABASE")
	fabric_sql_driver: str = Field(default="ODBC Driver 18 for SQL Server", alias="FABRIC_SQL_DRIVER")

	enable_mlflow: bool = Field(default=False, alias="ENABLE_MLFLOW")
	mlflow_tracking_uri: str | None = Field(default=None, alias="MLFLOW_TRACKING_URI")
	mlflow_experiment_name: str = Field(default="retrieval-agent", alias="MLFLOW_EXPERIMENT_NAME")

db_url = 'postgresql://ayush:a1b2c3@localhost:5432/agenticframeworkdb'

@lru_cache(maxsize=1)
def get_settings() -> Settings:
	settings = Settings()
	tracker.configure(
		enabled = settings.enable_mlflow,
		tracking_uri = settings.mlflow_tracking_uri,
		experiment_name = settings.mlflow_experiment_name,
	)
	return settings
