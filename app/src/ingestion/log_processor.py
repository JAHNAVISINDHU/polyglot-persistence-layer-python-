import json
import os
from src.utils.logger import get_logger
from src.ingestion.event_handlers import (
    handle_driver_location_update,
    handle_package_status_change,
    handle_billing_event,
)

logger = get_logger(__name__)

LOG_PATH = os.getenv("LOG_PATH", "/app/events.log")

EVENT_HANDLERS = {
    "DRIVER_LOCATION_UPDATE": handle_driver_location_update,
    "PACKAGE_STATUS_CHANGE": handle_package_status_change,
    "BILLING_EVENT": handle_billing_event,
}


def ingest_log_file(file_path: str = LOG_PATH) -> dict:
    if not os.path.exists(file_path):
        logger.warning(f"events.log not found, skipping ingestion: {file_path}")
        return {"processed": 0, "errors": 0, "skipped": 0}

    logger.info(f"Starting log file ingestion: {file_path}")
    stats = {"processed": 0, "errors": 0, "skipped": 0}

    with open(file_path, "r") as f:
        for line_number, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                stats["skipped"] += 1
                continue

            try:
                event = json.loads(stripped)
            except json.JSONDecodeError as e:
                logger.error(f"Malformed JSON line in events.log, skipping: line={line_number} content={stripped[:100]} error={e}")
                stats["errors"] += 1
                continue

            event_type = event.get("event_type")
            handler = EVENT_HANDLERS.get(event_type)

            if not handler:
                logger.warning(f"Unknown event type, skipping: event_type={event_type} line={line_number}")
                stats["skipped"] += 1
                continue

            try:
                handler(event)
                stats["processed"] += 1
            except Exception as e:
                logger.error(f"Failed to process event: event_type={event_type} event_id={event.get('event_id')} error={e}")

    logger.info(f"Log file ingestion complete: {stats}")
    return stats
