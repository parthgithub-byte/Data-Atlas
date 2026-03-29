"""Background worker tasks."""

from app import create_app
from celery_app import celery_app
from core.pipeline import run_scan_pipeline


flask_app = create_app()


@celery_app.task(name="dfas.scan.run", bind=True)
def run_scan_task(self, scan_id: int):
    """Run a scan inside a Celery worker."""
    with flask_app.app_context():
        run_scan_pipeline(
            scan_id,
            execution_backend="celery",
            task_id=self.request.id,
        )
