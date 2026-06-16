import asyncio
from app.database import AsyncSessionLocal
from sqlalchemy import text
from celery import Celery
from app.config import get_settings

async def main():
    settings = get_settings()
    celery_client = Celery("iip_client", broker=str(settings.redis_url))

    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT id, case_id, storage_path, file_type FROM evidence WHERE case_id = '174b3cdc-ffb5-4440-b8c3-30f0924ddf75'"))
        evidence_list = res.fetchall()
        print(f"Found {len(evidence_list)} stuck files.")
        for ev in evidence_list:
            celery_client.send_task(
                "tasks.pipeline.process_evidence_pipeline",
                args=[str(ev.id), str(ev.case_id), ev.storage_path, ev.file_type],
                queue="evidence_processing"
            )
        print("Re-queued all stuck files!")

if __name__ == "__main__":
    asyncio.run(main())
