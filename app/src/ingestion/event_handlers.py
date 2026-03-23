from src.databases import postgres, mongo, neo4j
from src.utils import retry_queue
from src.utils.logger import get_logger

logger = get_logger(__name__)


def handle_driver_location_update(event: dict):
    driver_id = event.get("driver_id")
    zone_id = event.get("zone_id")
    latitude = event.get("latitude")
    longitude = event.get("longitude")
    timestamp = event.get("timestamp")
    event_id = event.get("event_id")

    if not driver_id or not zone_id:
        logger.error(f"DRIVER_LOCATION_UPDATE missing required fields: event_id={event_id}")
        return

    cypher = """
        MERGE (d:Driver {driverId: $driverId})
        SET d.latitude = $latitude,
            d.longitude = $longitude,
            d.lastSeen = $timestamp,
            d.eventId = $eventId
        MERGE (z:Zone {zoneId: $zoneId})
        MERGE (d)-[r:LOCATED_IN]->(z)
        SET r.timestamp = $timestamp
        RETURN d, z
    """
    try:
        neo4j.run_query(cypher, {
            "driverId": driver_id,
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": timestamp,
            "eventId": event_id,
            "zoneId": zone_id,
        })
        logger.info(f"Driver location updated in Neo4j: driver_id={driver_id} zone_id={zone_id}")
    except Exception as e:
        logger.error(f"Failed to update driver location in Neo4j: driver_id={driver_id} error={e}")
        raise


def handle_package_status_change(event: dict):
    package_id = event.get("package_id")
    status = event.get("status")
    timestamp = event.get("timestamp")
    driver_id = event.get("driver_id")
    location = event.get("location")
    event_id = event.get("event_id")

    if not package_id or not status:
        logger.error(f"PACKAGE_STATUS_CHANGE missing required fields: event_id={event_id}")
        return

    status_entry = {
        "status": status,
        "timestamp": timestamp,
        "driver_id": driver_id,
        "location": location,
        "event_id": event_id,
    }

    try:
        collection = mongo.get_collection("packages")
        collection.update_one(
            {"package_id": package_id},
            {
                "$set": {"package_id": package_id, "updated_at": timestamp},
                "$push": {"status_history": status_entry},
            },
            upsert=True,
        )
        logger.info(f"Package status updated in MongoDB: package_id={package_id} status={status}")
    except Exception as e:
        logger.error(f"Failed to update package status in MongoDB: package_id={package_id} error={e}")
        raise


def check_package_delivered(package_id: str) -> bool:
    try:
        collection = mongo.get_collection("packages")
        doc = collection.find_one({"package_id": package_id})
        if not doc or not doc.get("status_history"):
            return False
        sorted_history = sorted(doc["status_history"], key=lambda x: x.get("timestamp", ""), reverse=True)
        return sorted_history[0].get("status") == "DELIVERED"
    except Exception as e:
        logger.error(f"Failed to check package delivery status: package_id={package_id} error={e}")
        return False


def insert_invoice(event: dict):
    invoice_id = event.get("invoice_id")
    package_id = event.get("package_id")
    amount = event.get("amount")
    customer_id = event.get("customer_id")
    currency = event.get("currency", "USD")
    timestamp = event.get("timestamp")
    event_id = event.get("event_id")

    try:
        postgres.execute(
            """INSERT INTO invoices (invoice_id, package_id, amount, customer_id, currency, timestamp, event_id)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (invoice_id, package_id, amount, customer_id, currency, timestamp, event_id),
        )
        logger.info(f"Invoice inserted into PostgreSQL: invoice_id={invoice_id} package_id={package_id}")
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower() or "23505" in str(e):
            logger.error(f"Duplicate invoice_id detected, skipping insertion: invoice_id={invoice_id} error={e}")
        else:
            logger.error(f"Failed to insert invoice: invoice_id={invoice_id} error={e}")
            raise


def handle_billing_event(event: dict):
    invoice_id = event.get("invoice_id")
    package_id = event.get("package_id")

    if not invoice_id or not package_id:
        logger.error(f"BILLING_EVENT missing required fields: event_id={event.get('event_id')}")
        return

    is_delivered = check_package_delivered(package_id)

    if not is_delivered:
        logger.warning(f"Package not yet DELIVERED, deferring billing event: package_id={package_id} invoice_id={invoice_id}")
        retry_queue.enqueue(event)
        return

    insert_invoice(event)
