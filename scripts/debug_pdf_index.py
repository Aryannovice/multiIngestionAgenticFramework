import sys
sys.path.insert(0, '.')

from config.settings import get_settings
from ingestion.ingestion import ingestion_service

settings = get_settings()
texts = ingestion_service._load_blob_texts(settings.azure_blob_pdf_prefix)
print('loaded_blobs', len(texts))
for name, text in texts:
    print('blob', name, 'text_len', len(text))
    chunks = ingestion_service.embedding_service.chunk_text(text)
    print('chunks', len(chunks))
    vectors = ingestion_service.embedding_service.generate_embeddings(chunks)
    print('vectors', len(vectors))
    docs = ingestion_service.embedding_service.build_search_documents(name, chunks, vectors)
    print('docs', len(docs))
    if docs:
        print('first_doc_keys', list(docs[0].keys()))
        print('first_doc_preview', docs[0].get('chunk', '')[:200])
    indexed = ingestion_service.embedding_service.index_documents(docs)
    print('indexed', indexed)
    print('---')
