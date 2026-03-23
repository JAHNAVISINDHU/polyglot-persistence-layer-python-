# 🚚 Polyglot Persistence Layer — Real-Time Logistics Platform

> **Repository:** [polyglot-persistence-layer-python-](https://github.com/JAHNAVISINDHU/polyglot-persistence-layer-python-)  
> **Author:** JAHNAVISINDHU  
> **Language:** Python (FastAPI)  
> **Databases:** Neo4j · MongoDB · PostgreSQL

A production-grade data processing pipeline built in **Python (FastAPI)** that routes logistics events to three specialized databases, each chosen for a specific query pattern. Implements an **eventual consistency model** with a retry queue and exposes a **unified query API**.

---

## 📐 Architecture Overview

```
events.log
    │
    ▼
┌─────────────────────────────────────────────────────┐
│              Event Router (Python / FastAPI)        │
│  ┌──────────────────────────────────────────────┐   │
│  │           Log Ingestion Pipeline             │   │
│  │  - Line-by-line JSON parsing                 │   │
│  │  - Malformed line error handling             │   │
│  │  - Event type dispatch                       │   │
│  └──────────┬──────────────┬───────────────────┘    │
│             │              │              │         │
│             ▼              ▼              ▼         │
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
polyglot-persistence-layer-python-/
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
        ├── main.py                        # FastAPI app entry point
        ├── config/
        │   └── settings.py                # Pydantic settings
        ├── databases/
        │   ├── postgres.py                # PostgreSQL client
        │   ├── mongo.py                   # MongoDB client
        │   └── neo4j.py                   # Neo4j driver
        ├── ingestion/
        │   ├── log_processor.py           # Log file reader
        │   └── event_handlers.py          # Per-event-type handlers
        ├── reconciliation/
        │   └── reconciler.py              # Retry queue processor
        ├── api/
        │   └── routes.py                  # FastAPI route handlers
        └── utils/
            ├── logger.py                  # Python logging utility
            └── retry_queue.py             # retry_queue.json manager
```

---

## 🚀 Step-by-Step Setup and Run

### Step 1 — Prerequisites

Make sure you have these installed:
- [Docker Desktop](https://www.docker.com/products/docker-desktop) >= 24
- [Docker Compose](https://docs.docker.com/compose/) >= 2.20
- [Git](https://git-scm.com/downloads)

---

### Step 2 — Clone the Repository

```bash
git clone https://github.com/JAHNAVISINDHU/polyglot-persistence-layer-python-.git
```

---

### Step 3 — Navigate into the Project Folder

```bash
cd polyglot-persistence-layer-python-
```

---

### Step 4 — Create the Environment File

On Mac/Linux:
```bash
cp .env.example .env
```

On Windows CMD:
```cmd
copy .env.example .env
```

---

### Step 5 — Start All Services

```bash
docker compose up --build
```

This single command will:
1. Build the Python FastAPI app image
2. Start PostgreSQL and wait until healthy
3. Start MongoDB and wait until healthy
4. Start Neo4j and wait until healthy
5. Start the app, auto-ingest events.log, run reconciliation, start the API

First run takes 3-5 minutes — Neo4j is slow to initialize!

---

### Step 6 — Wait for This Line

```
logistics_app | INFO: API server ready on port 3000
```

---

### Step 7 — Test the APIs

Open a second terminal:

```bash
# Health check
curl http://localhost:3000/query/health

# Package history
curl http://localhost:3000/query/package/pkg-test-456

# Check invoices
docker exec -it logistics_postgres psql -U logistics -d logistics_db -c "SELECT * FROM invoices;"

# Retry queue
curl http://localhost:3000/query/queue
```

---

### Step 8 — Test Reconciliation

```bash
echo '{"event_type":"PACKAGE_STATUS_CHANGE","event_id":"evt-rec-01","timestamp":"2024-01-15T12:00:00Z","package_id":"pkg-out-of-order-123","status":"DELIVERED","driver_id":"drv-456","location":"Final Stop"}' >> events.log

curl -X POST http://localhost:3000/query/ingest

curl http://localhost:3000/query/queue

docker exec -it logistics_postgres psql -U logistics -d logistics_db -c "SELECT * FROM invoices WHERE package_id = 'pkg-out-of-order-123';"
```

---

### Step 9 — Interactive API Docs

Open in browser:
```
http://localhost:3000/docs
```

---

### Step 10 — Neo4j Visual Graph

Open in browser:
```
http://localhost:7474
```

Login:
- Username: neo4j
- Password: logistics123

Run this query:
```cypher
MATCH (d:Driver)-[:LOCATED_IN]->(z:Zone) RETURN d, z
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /query/health | Check all 3 database connections |
| GET | /query/package/{id} | Unified sorted history for a package |
| GET | /query/queue | View deferred billing events |
| POST | /query/ingest | Manually trigger log file ingestion |
| POST | /query/reconcile | Manually trigger reconciliation |

---

## 🛑 Stop

```bash
# Stop but keep data
docker compose down

# Full reset
docker compose down -v
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| POSTGRES_USER | logistics | PostgreSQL username |
| POSTGRES_PASSWORD | logistics_pass | PostgreSQL password |
| POSTGRES_DB | logistics_db | PostgreSQL database |
| MONGO_USER | logistics | MongoDB username |
| MONGO_PASSWORD | logistics_pass | MongoDB password |
| MONGO_DB | logistics_db | MongoDB database |
| NEO4J_URI | bolt://neo4j:7687 | Neo4j Bolt URI |
| NEO4J_USER | neo4j | Neo4j username |
| NEO4J_PASSWORD | logistics123 | Neo4j password |
| APP_PORT | 3000 | API server port |
| LOG_LEVEL | info | Logging level |

---

## 📋 Requirements Compliance

| # | Requirement | Implementation |
|---|-------------|---------------|
| 1 | Docker Compose with 4 services + health checks | docker-compose.yml |
| 2 | Auto-ingest events.log, handle malformed lines | src/ingestion/log_processor.py |
| 3 | DRIVER_LOCATION_UPDATE to Neo4j | src/ingestion/event_handlers.py |
| 4 | PACKAGE_STATUS_CHANGE to MongoDB | src/ingestion/event_handlers.py |
| 5 | BILLING_EVENT to PostgreSQL | src/ingestion/event_handlers.py |
| 6 | Duplicate invoice_id prevented and logged | PostgreSQL UNIQUE + psycopg2 |
| 7 | Pre-delivery billing deferred to retry_queue.json | src/utils/retry_queue.py |
| 8 | Reconciliation processes retry queue | src/reconciliation/reconciler.py |
| 9 | GET /query/package/:id unified sorted history | src/api/routes.py |
| 10 | ADR at docs/ADR-001-Data-Store-Selection.md | Present |
| 11 | .env.example with all DB variables | Present |

---
