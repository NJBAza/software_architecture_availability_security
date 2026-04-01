#!/usr/bin/env bash

set -e

cd "$(dirname "$0")/.."

docker build -t registers_ingest:v1 .

docker run --rm \
  --network=registers_default \
  -v "$(pwd)/data:/app/data" \
  registers_ingest:v1 \
  --csv-file=/app/data/warehouse_stock.csv \
  --pg-user=root \
  --pg-pass=root \
  --pg-host=pgdatabase \
  --pg-port=5432 \
  --pg-db=warehouse_reservations \
  --chunksize=50000 \
  --target-table=warehouse_stock

docker run --rm \
  --network=registers_default \
  -v "$(pwd)/data:/app/data" \
  registers_ingest:v1 \
  --csv-file=/app/data/reservations.csv \
  --pg-user=root \
  --pg-pass=root \
  --pg-host=pgdatabase \
  --pg-port=5432 \
  --pg-db=warehouse_reservations \
  --chunksize=50000 \
  --target-table=reservations
