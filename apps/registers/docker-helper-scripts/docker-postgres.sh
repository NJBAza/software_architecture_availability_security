#!/usr/bin/env bash

mkdir -p ../ny_taxi_postgres_data

docker network inspect pg-network >/dev/null 2>&1 || docker network create pg-network

docker run -it --rm \
  -e POSTGRES_USER="root" \
  -e POSTGRES_PASSWORD="root" \
  -e POSTGRES_DB="ny_taxi" \
  -v "$(pwd)/../ny_taxi_postgres_data:/var/lib/postgresql/data" \
  -p 5432:5432 \
  --network=pg-network \
  --name pgdatabase \
  postgres:18