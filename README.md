# 🚚 Polyglot Persistence Layer — Real-Time Logistics Platform

A production-grade data processing pipeline built in **Python (FastAPI)** that routes logistics events to three specialized databases, each chosen for a specific query pattern. Implements an **eventual consistency model** with a retry queue and exposes a **unified query API**.

---

## 📐 Architecture Overview

```
events.log
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              Event Router (Python / FastAPI)         │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │           Log Ingestion Pipeline              │  │
│  │  - Line-by-line JSON parsing                 │  │
│  │  - Malformed line error handling             │  │
│  │  - Event type dispatch                       │  │
│  └──────────┬──────────────┬───────────────────┘  │
│             │              │              │          │
│             ▼              ▼              ▼          │
│     DRIVER_LOCATION  PACKAGE_STATUS  BILLING_EVENT  │
│     _UPDATE          _CHANGE                        │
└─────────────┼──────────────┼──────────────┼─────────┘
              │              │              │
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────┐  ┌─────────────┐
       │  Neo4j   │  │ MongoDB  │  │ PostgreSQL  │
       │ (Graph)  │  │  (Doc)   │  │ (Relational)│
       └──────────┘  └──────────┘  └──────┬──────┘
                                          │
                                 retry_queue.json
                                 (if not DELIVERED)
                                          │
                                   Reconciliation
```

---

## 🗄️ Database Responsibilities

| Store | Technology | Event Type | Why |
|-------|-----------|-----------|-----|
| **Graph** | Neo4j | `DRIVER_LOCATION_UPDATE` | Graph-native driver↔zone relationships |
| **Document** | MongoDB | `PACKAGE_STATUS_CHANGE` | Flexible status history array per package |
| **Relational** | PostgreSQL | `BILLING_EVENT` | ACID + UNIQUE constraint for billing |

---

## 📦 Project Structure

```
logistics-platform/
├── docker-compose.yml
├── .env.example
├── events.log
├── retry_queue.json
├── docs/
│   └── ADR-001-Data-Store-Selection.md
├── scripts/
│   └── init_postgres.sql
└── app/
    ├── Dockerfile
    ├── requirements.txt
    └── src/
        ├── main.py                          # FastAPI app entry point
        ├── config/
        │   └── settings.py                  # Pydantic settings
        ├── databases/
        │   ├── postgres.py                  # PostgreSQL client
        │   ├── mongo.py                     # MongoDB client
        │   └── neo4j.py                     # Neo4j driver
        ├── ingestion/
        │   ├── log_processor.py             # Log file reader
        │   └── event_handlers.py            # Per-event-type handlers
        ├── reconciliation/
        │   └── reconciler.py                # Retry queue processor
        ├── api/
        │   └── routes.py                    # FastAPI route handlers
        └── utils/
            ├── logger.py                    # Python logging utility
            └── retry_queue.py               # retry_queue.json manager
```

---

## 🚀 Quick Start

### Prerequisites
- Docker Desktop ≥ 24
- Docker Compose ≥ 2.20

### Run

```bash
# 1. Copy environment file
cp .env.example .env

# 2. Start everything
docker compose up --build
```

Wait for:
```
logistics_app | INFO: API server ready on port 3000
```

---

## 📡 API Reference

### `GET /query/health`
```bash
curl http://localhost:3000/query/health
```

### `GET /query/package/{package_id}`
```bash
curl http://localhost:3000/query/package/pkg-test-456
```

### `GET /query/queue`
```bash
curl http://localhost:3000/query/queue
```

### `POST /query/ingest`
```bash
curl -X POST http://localhost:3000/query/ingest
```

### `POST /query/reconcile`
```bash
curl -X POST http://localhost:3000/query/reconcile
```

### 📖 Auto-generated API Docs (FastAPI)
```
http://localhost:3000/docs
```

---

## 🧪 Verification

```bash
# Health check
curl http://localhost:3000/query/health

# Package history from MongoDB
curl http://localhost:3000/query/package/pkg-test-456

# Invoices in PostgreSQL
docker exec -it logistics_postgres psql -U logistics -d logistics_db -c "SELECT * FROM invoices;"

# Drivers in Neo4j
docker exec -it logistics_neo4j cypher-shell -u neo4j -p logistics_pass "MATCH (d:Driver)-[:LOCATED_IN]->(z:Zone) RETURN d.driverId, z.zoneId"

# Retry queue
curl http://localhost:3000/query/queue

# Reconciliation test
echo '{"event_type":"PACKAGE_STATUS_CHANGE","event_id":"evt-rec-01","timestamp":"2024-01-15T12:00:00Z","package_id":"pkg-out-of-order-123","status":"DELIVERED","driver_id":"drv-456","location":"Final Stop"}' >> events.log
curl -X POST http://localhost:3000/query/ingest
curl http://localhost:3000/query/queue
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_USER` | `logistics` | PostgreSQL username |
| `POSTGRES_PASSWORD` | `logistics_pass` | PostgreSQL password |
| `POSTGRES_DB` | `logistics_db` | PostgreSQL database |
| `MONGO_USER` | `logistics` | MongoDB username |
| `MONGO_PASSWORD` | `logistics_pass` | MongoDB password |
| `MONGO_DB` | `logistics_db` | MongoDB database |
| `NEO4J_URI` | `bolt://neo4j:7687` | Neo4j Bolt URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `logistics_pass` | Neo4j password |
| `APP_PORT` | `3000` | API port |
| `LOG_LEVEL` | `info` | Logging level |

---

## 🛑 Stop

```bash
# Stop but keep data
docker compose down

# Full reset
docker compose down -v
```

---

## 📋 Requirements Compliance

| # | Requirement | Implementation |
|---|-------------|---------------|
| 1 | Docker Compose with 4 services + health checks | `docker-compose.yml` |
| 2 | Auto-ingest `events.log`, handle malformed lines | `src/ingestion/log_processor.py` |
| 3 | `DRIVER_LOCATION_UPDATE` → Neo4j Driver/Zone/LOCATED_IN | `src/ingestion/event_handlers.py` |
| 4 | `PACKAGE_STATUS_CHANGE` → MongoDB status_history | `src/ingestion/event_handlers.py` |
| 5 | `BILLING_EVENT` → PostgreSQL invoices | `src/ingestion/event_handlers.py` |
| 6 | Duplicate invoice_id prevented + logged | PostgreSQL UNIQUE + psycopg2 error handling |
| 7 | Pre-delivery billing → `retry_queue.json` | `src/utils/retry_queue.py` |
| 8 | Reconciliation processes retry queue | `src/reconciliation/reconciler.py` |
| 9 | `GET /query/package/:id` unified sorted history | `src/api/routes.py` |
| 10 | ADR at `docs/ADR-001-Data-Store-Selection.md` | ✅ |
| 11 | `.env.example` with all DB variables | ✅ |

---

## 📄 License

MIT
