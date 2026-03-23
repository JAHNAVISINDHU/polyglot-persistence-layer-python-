from fastapi import APIRouter, HTTPException
from typing import List, Any, Dict
from src.databases import postgres, mongo, neo4j
from src.utils import retry_queue
from src.utils.logger import get_logger
from src.ingestion.log_processor import ingest_log_file
from src.reconciliation.reconciler import run_reconciliation

router = APIRouter()
logger = get_logger(__name__)


@router.get("/package/{package_id}", response_model=List[Dict[str, Any]])
def get_package_history(package_id: str):
    events = []

    # 1. MongoDB — package status history
    try:
        collection = mongo.get_collection("packages")
        doc = collection.find_one({"package_id": package_id})
        if doc and doc.get("status_history"):
            for entry in doc["status_history"]:
                events.append({
                    "source_system": "document_store",
                    "timestamp": entry.get("timestamp"),
                    "event_details": {
                        "status": entry.get("status"),
                        "driver_id": entry.get("driver_id"),
                        "location": entry.get("location"),
                        "event_id": entry.get("event_id"),
                    },
                })
    except Exception as e:
        logger.error(f"Failed to query MongoDB for package history: package_id={package_id} error={e}")

    # 2. PostgreSQL — billing events
    try:
        rows = postgres.execute(
            "SELECT * FROM invoices WHERE package_id = %s", (package_id,)
        )
        for row in rows:
            events.append({
                "source_system": "relational_store",
                "timestamp": str(row["timestamp"]) if row.get("timestamp") else None,
                "event_details": {
                    "invoice_id": row["invoice_id"],
                    "amount": float(row["amount"]),
                    "customer_id": row["customer_id"],
                    "currency": row["currency"],
                    "event_id": row["event_id"],
                },
            })
    except Exception as e:
        logger.error(f"Failed to query PostgreSQL for package history: package_id={package_id} error={e}")

    # 3. Neo4j — driver location events linked to package
    try:
        cypher = """
            MATCH (d:Driver {lastPackageId: $packageId})-[:LOCATED_IN]->(z:Zone)
            RETURN d.driverId AS driverId, d.latitude AS latitude,
                   d.longitude AS longitude, d.lastSeen AS timestamp,
                   z.zoneId AS zoneId, d.eventId AS eventId
        """
        records = neo4j.run_query(cypher, {"packageId": package_id})
        for record in records:
            events.append({
                "source_system": "graph_store",
                "timestamp": record["timestamp"],
                "event_details": {
                    "driver_id": record["driverId"],
                    "latitude": record["latitude"],
                    "longitude": record["longitude"],
                    "zone_id": record["zoneId"],
                    "event_id": record["eventId"],
                },
            })
    except Exception as e:
        logger.error(f"Failed to query Neo4j for package history: package_id={package_id} error={e}")

    # Sort by timestamp ascending
    events.sort(key=lambda x: x.get("timestamp") or "")
    return events


@router.get("/health")
def health_check():
    health = {"status": "ok", "databases": {}}

    try:
        postgres.execute("SELECT 1")
        health["databases"]["postgres"] = "healthy"
    except Exception:
        health["databases"]["postgres"] = "unhealthy"
        health["status"] = "degraded"

    try:
        mongo.get_db().command("ping")
        health["databases"]["mongo"] = "healthy"
    except Exception:
        health["databases"]["mongo"] = "unhealthy"
        health["status"] = "degraded"

    try:
        neo4j.run_query("RETURN 1")
        health["databases"]["neo4j"] = "healthy"
    except Exception:
        health["databases"]["neo4j"] = "unhealthy"
        health["status"] = "degraded"

    return health


@router.get("/queue")
def get_queue():
    queue = retry_queue.get_all()
    return {"count": len(queue), "events": queue}


@router.post("/ingest")
def trigger_ingest():
    try:
        stats = ingest_log_file()
        result = run_reconciliation()
        return {"message": "Ingestion complete", "stats": stats, "reconciliation": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconcile")
def trigger_reconcile():
    try:
        result = run_reconciliation()
        return {"message": "Reconciliation complete", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
