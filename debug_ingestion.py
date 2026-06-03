import asyncio
import logging

from ingestion.ingestion import ingestion_service
from models.schema import IngestionRequest, SourceType

logging.basicConfig(level=logging.INFO)

async def main():
    request = IngestionRequest(
        source_type=SourceType.PDF,
        source_name="test_pdf",
        blob_path="pdf"   # your blob folder prefix
    )

    response = ingestion_service.submit_job(request)

    print(f"JOB CREATED: {response.job_id}")

    await ingestion_service.process_job(response.job_id)

    status = ingestion_service.get_job_status(response.job_id)

    print(status)

asyncio.run(main())
