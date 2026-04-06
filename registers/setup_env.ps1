$ErrorActionPreference = "Stop"

Write-Host "1. Deteniendo y limpiando contenedores previos..." -ForegroundColor Cyan
docker compose down -v --remove-orphans

Write-Host "`n2. Levantando bases de datos y pgadmin..." -ForegroundColor Cyan
docker compose up -d orders_db reservations_db conciliator_db pgadmin

Write-Host "Esperando 10 segundos para que las bases de datos acepten conexiones..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
docker compose ps

Write-Host "`n3. Construyendo imagen de ingestión..." -ForegroundColor Cyan
docker build -t registers_ingest:v1 ./ingest

# Obtenemos la ruta actual para el montaje de volúmenes en Windows
$currentPath = (Get-Location).Path

Write-Host "`n4. Cargando datos en Reservations DB..." -ForegroundColor Cyan
docker run --rm --network=registers_default -v "$currentPath/data:/app/data" registers_ingest:v1 --csv-file=/app/data/warehouse_stock.csv --pg-user=root --pg-pass=root --pg-host=reservations_db --pg-db=reservations_db --target-table=warehouse_stock
docker run --rm --network=registers_default -v "$currentPath/data:/app/data" registers_ingest:v1 --csv-file=/app/data/reservations.csv --pg-user=root --pg-pass=root --pg-host=reservations_db --pg-db=reservations_db --target-table=reservations

Write-Host "`n5. Cargando datos en Orders DB..." -ForegroundColor Cyan
docker run --rm --network=registers_default -v "$currentPath/data:/app/data" registers_ingest:v1 --csv-file=/app/data/sales_orders.csv --pg-user=root --pg-pass=root --pg-host=orders_db --pg-db=orders_db --target-table=sales_orders
docker run --rm --network=registers_default -v "$currentPath/data:/app/data" registers_ingest:v1 --csv-file=/app/data/order_items.csv --pg-user=root --pg-pass=root --pg-host=orders_db --pg-db=orders_db --target-table=order_items

Write-Host "`n6. Cargando datos en Conciliator DB..." -ForegroundColor Cyan
docker run --rm --network=registers_default -v "$currentPath/data:/app/data" registers_ingest:v1 --csv-file=/app/data/reconciliation_runs.csv --pg-user=root --pg-pass=root --pg-host=conciliator_db --pg-db=conciliator_db --target-table=reconciliation_runs

Write-Host "`n7. Levantando servicios de FastAPI..." -ForegroundColor Cyan
docker compose up -d --build orders_service reservations_service conciliator_service
docker compose ps

Write-Host "`n¡Despliegue e ingestión finalizados con éxito!" -ForegroundColor Green