import sys

sys.path.insert(0, ".")

from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)

from config.settings import get_settings
from utils.azure_clients import get_search_index_client


settings = get_settings()
client = get_search_index_client()


def ensure_dataset_metadata_index() -> None:
    name = settings.azure_ai_search_index_dataset_meta
    try:
        index = client.get_index(name)
        existing = {field.name for field in (index.fields or [])}
        added = False

        if "source" not in existing:
            index.fields.append(SearchableField(name="source", type=SearchFieldDataType.String, filterable=True))
            added = True
        if "chunk" not in existing:
            index.fields.append(SearchableField(name="chunk", type=SearchFieldDataType.String))
            added = True
        if "chunk_index" not in existing:
            index.fields.append(SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True))
            added = True

        if added:
            client.create_or_update_index(index)
            print(f"updated: {name}")
        else:
            print(f"exists: {name}")
        return
    except ResourceNotFoundError:
        pass

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="dataset_name", type=SearchFieldDataType.String),
        SearchableField(name="description", type=SearchFieldDataType.String),
        SimpleField(name="source_type", type=SearchFieldDataType.String, filterable=True, facetable=True),
    ]

    index = SearchIndex(name=name, fields=fields)
    client.create_index(index)
    print(f"created: {name}")


def ensure_document_chunks_index() -> None:
    name = settings.azure_ai_search_index_docs
    try:
        client.get_index(name)
        print(f"exists: {name}")
        return
    except ResourceNotFoundError:
        pass

    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="hnsw-config")],
        profiles=[VectorSearchProfile(name="vector-profile", algorithm_configuration_name="hnsw-config")],
    )

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="source", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="chunk", type=SearchFieldDataType.String),
        SimpleField(name="chunk_index", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchField(
            name="chunk_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="vector-profile",
        ),
    ]

    index = SearchIndex(name=name, fields=fields, vector_search=vector_search)
    client.create_index(index)
    print(f"created: {name}")


if __name__ == "__main__":
    ensure_dataset_metadata_index()
    try:
        ensure_document_chunks_index()
    except Exception as exc:
        print(f"warn: unable to create docs index '{settings.azure_ai_search_index_docs}': {exc}")
