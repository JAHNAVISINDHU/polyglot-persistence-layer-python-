from src.utils import retry_queue
from src.utils.logger import get_logger
from src.ingestion.event_handlers import check_package_delivered, insert_invoice

logger = get_logger(__name__)


def run_reconciliation() -> dict:
    queue = retry_queue.get_all()

    if not queue:
        logger.info("Retry queue is empty, nothing to reconcile")
        return {"processed": 0, "remaining": 0}

    logger.info(f"Starting reconciliation for {len(queue)} deferred events")
    processed_count = 0

    for event in queue:
        invoice_id = event.get("invoice_id")
        package_id = event.get("package_id")

        is_delivered = check_package_delivered(package_id)

        if not is_delivered:
            logger.info(f"Package still not DELIVERED, keeping in retry queue: package_id={package_id} invoice_id={invoice_id}")
            continue

        logger.info(f"Package is now DELIVERED, processing deferred billing event: package_id={package_id} invoice_id={invoice_id}")

        try:
            insert_invoice(event)
            retry_queue.dequeue(invoice_id)
            processed_count += 1
        except Exception as e:
            logger.error(f"Failed to process deferred billing event: invoice_id={invoice_id} error={e}")

    remaining = len(retry_queue.get_all())
    logger.info(f"Reconciliation complete: processed={processed_count} remaining={remaining}")
    return {"processed": processed_count, "remaining": remaining}
