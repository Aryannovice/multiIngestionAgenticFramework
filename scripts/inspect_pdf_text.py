import io
import sys
sys.path.insert(0, '.')

from pypdf import PdfReader
from utils.azure_clients import get_blob_service_client
from config.settings import get_settings

settings = get_settings()
container = get_blob_service_client().get_container_client(settings.azure_storage_container)
for blob in container.list_blobs(name_starts_with=settings.azure_blob_pdf_prefix):
    if not blob.name.lower().endswith('.pdf'):
        continue
    print('BLOB', blob.name)
    raw = container.get_blob_client(blob.name).download_blob().readall()
    print('bytes', len(raw))
    reader = PdfReader(io.BytesIO(raw))
    print('pages', len(reader.pages))
    for i, page in enumerate(reader.pages[:3]):
        text = page.extract_text() or ''
        print('page', i, 'text_len', len(text))
        print(text[:500].replace('\n', ' '))
        print('---')
    print('===')
