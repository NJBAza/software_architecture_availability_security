#!/usr/bin/env bash

mkdir -p ../pgadmin_data

docker network inspect pg-network >/dev/null 2>&1 || docker network create pg-network

docker run -it --rm \
  -e PGADMIN_DEFAULT_EMAIL="admin@admin.com" \
  -e PGADMIN_DEFAULT_PASSWORD="root" \
  -v "$(pwd)/../pgadmin_data:/var/lib/pgadmin" \
  -p 8085:80 \
  --network=pg-network \
  --name pgadmin \
  dpage/pgadmin4