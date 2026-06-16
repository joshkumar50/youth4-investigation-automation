from celery import Celery

celery_app = Celery("iip_worker", broker="redis://:iip_secret_2024@redis:6379/0")

evidence_ids = [
    ("0d6a3c02-f70a-4abc-920c-c257f7dea43e", "174b3cdc-ffb5-4440-b8c3-30f0924ddf75", "uploads/174b3cdc-ffb5-4440-b8c3-30f0924ddf75/b5bb7681-abf8-47f7-b4a4-e958aae48084.txt", "document"),
    ("2b52d6dd-78da-4bb3-87c3-7dd97883400c", "174b3cdc-ffb5-4440-b8c3-30f0924ddf75", "uploads/174b3cdc-ffb5-4440-b8c3-30f0924ddf75/027ff671-8576-4956-875a-54c9e4da9bdf.txt", "document"),
    ("b5bb7681-abf8-47f7-b4a4-e958aae48084", "174b3cdc-ffb5-4440-b8c3-30f0924ddf75", "uploads/174b3cdc-ffb5-4440-b8c3-30f0924ddf75/2b52d6dd-78da-4bb3-87c3-7dd97883400c.txt", "document"),
    ("027ff671-8576-4956-875a-54c9e4da9bdf", "174b3cdc-ffb5-4440-b8c3-30f0924ddf75", "uploads/174b3cdc-ffb5-4440-b8c3-30f0924ddf75/0d6a3c02-f70a-4abc-920c-c257f7dea43e.txt", "document")
]

for ev in evidence_ids:
    celery_app.send_task(
        "tasks.pipeline.process_evidence_pipeline",
        args=[ev[0], ev[1], ev[2], ev[3]],
        queue="evidence_processing"
    )
print("Re-queued all stuck files!")
