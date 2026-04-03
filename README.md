# Microservices Architecture: Orders, Reservations, Conciliator

This project implements a **microservices-based architecture** using:

- FastAPI (3 independent services)
- PostgreSQL (one database per service)
- Docker & Docker Compose
- CSV data ingestion
- HTTP-based service-to-service communication
- Scalar API documentation

---

# Architecture Overview

Client → Orders Service → Reservations Service
                     ↘ Conciliator Service

- **Orders Service**: handles order lifecycle
- **Reservations Service**: handles stock and concurrency
- **Conciliator Service**: detects inconsistencies

---

# Project Structure

```
registers/
├── docker-compose.yml
├── data/
│   ├── warehouse_stock.csv
│   ├── reservations.csv
│   ├── sales_orders.csv
│   ├── order_items.csv
│   └── reconciliation_runs.csv
├── ingest/
├── orders_service/
├── reservations_service/
└── conciliator_service/
```

---

# Prerequisites

- Docker
- Docker Compose
- Python + uv (only for generating lock files)

---

# Setup & Execution

## 1. Generate dependency lock files

Run once:

```bash
cd ingest && uv lock && cd ..
cd orders_service && uv lock && cd ..
cd reservations_service && uv lock && cd ..
cd conciliator_service && uv lock && cd ..
```

---

## 2. Start databases

```bash
docker compose down -v --remove-orphans
docker compose up -d orders_db reservations_db conciliator_db pgadmin
docker compose ps
```

---

## 3. Build ingestion image

```bash
docker build -t registers_ingest:v1 ./ingest
```

---

## 4. Load data into databases

### Reservations DB

```bash
docker run --rm --network=registers_default -v "$(pwd)/data:/app/data" registers_ingest:v1 --csv-file=/app/data/warehouse_stock.csv --pg-user=root --pg-pass=root --pg-host=reservations_db --pg-db=reservations_db --target-table=warehouse_stock
```

```bash
docker run --rm --network=registers_default -v "$(pwd)/data:/app/data" registers_ingest:v1 --csv-file=/app/data/reservations.csv --pg-user=root --pg-pass=root --pg-host=reservations_db --pg-db=reservations_db --target-table=reservations
```

---

### Orders DB

```bash
docker run --rm --network=registers_default -v "$(pwd)/data:/app/data" registers_ingest:v1 --csv-file=/app/data/sales_orders.csv --pg-user=root --pg-pass=root --pg-host=orders_db --pg-db=orders_db --target-table=sales_orders
```

```bash
docker run --rm --network=registers_default -v "$(pwd)/data:/app/data" registers_ingest:v1 --csv-file=/app/data/order_items.csv --pg-user=root --pg-pass=root --pg-host=orders_db --pg-db=orders_db --target-table=order_items
```

---

### Conciliator DB

```bash
docker run --rm --network=registers_default -v "$(pwd)/data:/app/data" registers_ingest:v1 --csv-file=/app/data/reconciliation_runs.csv --pg-user=root --pg-pass=root --pg-host=conciliator_db --pg-db=conciliator_db --target-table=reconciliation_runs
```

---

## 5. Start FastAPI services

```bash
docker compose up -d --build orders_service reservations_service conciliator_service
docker compose ps
```

---

# Access Services

| Service            | URL                        |
|------------------|---------------------------|
| Orders API        | http://localhost:8001     |
| Reservations API  | http://localhost:8002     |
| Conciliator API   | http://localhost:8003     |
| pgAdmin           | http://localhost:8085     |

---

# Local verifications to observe status of the services
```bash
curl http://localhost:8001/health
curl http://localhost:8002/health
curl http://localhost:8003/health
```
---

# API Documentation (Scalar)

Each service exposes Scalar UI:

- Orders → http://localhost:8001/scalar
- Reservations → http://localhost:8002/scalar
- Conciliator → http://localhost:8003/scalar

---

# Service Communication

Services communicate via HTTP using Docker service names:

- orders_service → reservations_service
- conciliator_service → orders_service
- conciliator_service → reservations_service

---

# Example Workflow

## Create an order

```bash
curl -X POST http://localhost:8001/orders -H "Content-Type: application/json" -d '{
  "order_id": "ORD_TEST_001",
  "seller_id": "SELLER001",
  "store_id": "WH001",
  "stock_id": "STK00001",
  "quantity": 1,
  "total_amount": 120.0
}'
```

---

## Run reconciliation

```bash
curl -X POST http://localhost:8003/conciliator/reconcile
```

---

# Key Concepts

- Each service owns its own database
- No cross-database joins
- Communication via HTTP (httpx)
- Concurrency handled in Reservations service
- Conciliator detects inconsistencies

---

# Common Issues

### Services not running

```bash
docker compose up -d
```

### Check logs

```bash
docker compose logs -f orders_service
```

### Reset environment (deletes data)

```bash
docker compose down -v
```

---

# Summary

This project demonstrates:

- Microservices architecture
- Data isolation per service
- Distributed consistency patterns
- Concurrency handling
- Reconciliation strategy
