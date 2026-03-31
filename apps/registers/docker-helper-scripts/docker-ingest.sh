#!/usr/bin/env bash

docker network inspect pg-network >/dev/null 2>&1 || docker network create pg-network

docker run -it --rm \
  --network=pg-network \
  -v "$(pwd)/../data:/app/data" \
  taxi_ingest:v001 \
  --csv-file=/app/data/taxis.csv \
  --pg-user=root \
  --pg-pass=root \
  --pg-host=pgdatabase \
  --pg-port=5432 \
  --pg-db=ny_taxi \
  --chunksize=50000 \
  --target-table=taxis