# Pruebas de disponibilidad y combinatoria

Este directorio agrupa la **documentación por escenario** y las **salidas CSV** (`results/`) para el análisis de las pruebas E1–E3, F1 (API raíz + IDS + SQLite) y los escenarios G (microservicio de reservas en `registers/`).

## Requisitos

- **Docker** y **Docker Compose**
- **Python 3.11** y **uv** (o el intérprete del proyecto)
- **PostgreSQL IDS** en `localhost:5432` con credenciales alineadas a `apps/services/IDS.py` (usuario `postgres`, contraseña `1234`, base `postgres`). Use [docker-compose.ids.yml](../../../docker-compose.ids.yml) en la raíz del repositorio (tres niveles por encima de esta carpeta).
- Esquema y semilla IDS: `scripts/ids_postgres_schema.sql` y `scripts/ids_postgres_seed.sql`
- Para escenarios **G**: stack `registers/` levantado, datos cargados (véase [README.md](../../../README.md) en la raíz del repo)

## Ejecución única (recomendada)

Desde la **raíz del repositorio** (Windows PowerShell):

```powershell
.\run_disponibilidad.ps1
```

O con Python (raíz del repo; requiere dependencias instaladas y `httpx`):

```bash
uv run python -m scripts.disponibilidad.run_all
```

Sin `uv`, desde la raíz del repositorio:

```powershell
$env:PYTHONPATH="."
python -m scripts.disponibilidad.run_all
```

Opciones útiles:

```bash
uv run python scripts/disponibilidad/run_all.py --solo E3
uv run python scripts/disponibilidad/run_all.py --skip G_capacidad
uv run python scripts/disponibilidad/run_all.py --no-docker-e1e2
uv run python scripts/disponibilidad/run_all.py --solo G_escalado_tiempo_respuesta
uv run python scripts/disponibilidad/run_all.py --solo G_rollback_carga
uv run python scripts/disponibilidad/run_all.py --solo G_rollback_carga_10pct_parejas
uv run python scripts/disponibilidad/run_all.py --solo G_rollback_carga_1pct
uv run python scripts/disponibilidad/run_all.py --solo G_latencia_escalonada
```

## Preparación de datos para nuevos G

Antes de tests de carga/rollback masivos, valide stock mínimo disponible:

```bash
uv run python -m scripts.disponibilidad.prepare_g_test_data --validate-only
```

Si el script devuelve IDs con `low_available`, el stock fue consumido por ejecuciones anteriores.

### Reset completo de base de datos (stock agotado)

Si las pruebas G muestran `error_pct: 100%` con `rollback_409` igual al número de conflictos, significa que el stock disponible en la BD está agotado. Para restaurarlo:

```powershell
# Desde la carpeta registers/ del repositorio
cd registers
docker compose down -v --remove-orphans
docker compose up -d orders_db reservations_db conciliator_db pgadmin
# Esperar ~10 segundos a que los contenedores estén listos
Start-Sleep 10
# Re-ingestar los datos CSV
docker exec -i orders_db psql -U postgres -d orders_db -c "\copy sales_orders FROM '/docker-entrypoint-initdb.d/sales_orders.csv' CSV HEADER"
docker exec -i reservations_db psql -U postgres -d reservations_db -c "\copy warehouse_stock FROM '/docker-entrypoint-initdb.d/warehouse_stock.csv' CSV HEADER"
```

O usar el script de ingesta si existe en el proyecto:

```powershell
cd registers
docker compose down -v --remove-orphans && docker compose up -d
```

Después de restaurar, volver a validar:

```bash
uv run python -m scripts.disponibilidad.prepare_g_test_data --validate-only
```

## Orden recomendado

1. Levantar Postgres IDS (`docker compose -f docker-compose.ids.yml up -d`) y sembrar tablas.
2. Bloque **E** y **F** (API raíz en `http://127.0.0.1:8000` por defecto).
3. Levantar `registers/` + ingest CSV.
4. Bloque **G** (reservas en `http://localhost:8002`).

Tras una corrida completa, consulte `registers/data/test/results/resumen_global.csv`.

## Subcarpetas por escenario

| Carpeta | Descripción breve |
|---------|-------------------|
| [E1_postgresql_caido_arranque](E1_postgresql_caido_arranque/README.md) | Impacto al arrancar sin PostgreSQL IDS |
| [E2_postgresql_caido_ejecucion](E2_postgresql_caido_ejecucion/README.md) | Fallo de PG durante petición IDS |
| [E3_carga_concurrente_ids](E3_carga_concurrente_ids/README.md) | Carga concurrente al endpoint IDS |
| [F1_consultas_parametrizadas](F1_consultas_parametrizadas/README.md) | Revisión estática SQL parametrizado |
| [G_concurrencia_mismo_stock](G_concurrencia_mismo_stock/README.md) | Dos+ clientes, mismo `stock_id` |
| [G_rollback_carga_conflicto_10pct_parejas](G_rollback_carga_conflicto_10pct_parejas/README.md) | `G_rollback_carga` unificado (mezcla carga normal + conflicto controlado) |
| [G_diez_parejas_diez_productos](G_diez_parejas_diez_productos/README.md) | Mismo producto con niveles 2,10,100,1000,5000,10000,20000 |
| [G_rollback_y_tiempo](G_rollback_y_tiempo/README.md) | Latencia en conflicto e integridad |
| [G_capacidad_usuarios_concurrentes](G_capacidad_usuarios_concurrentes/README.md) | 10 / 100 / 1000 / 100000 VUs (parametrizable) |
| [G_escalado_tiempo_respuesta_usuarios](G_escalado_tiempo_respuesta_usuarios/README.md) | Escalado de latencia hasta 5s o fallo |
| [G_rollback_carga_conflicto_10pct_parejas](G_rollback_carga_conflicto_10pct_parejas/README.md) | Rollback bajo carga 10% en parejas |
| [G_rollback_carga_conflicto_1pct](G_rollback_carga_conflicto_1pct/README.md) | Rollback bajo carga con 1% de conflicto |
| [G_latencia_escalonada_usuarios](G_latencia_escalonada_usuarios/README.md) | Latencia por usuarios en escalones definidos |

## Salida de gráficas

Todas las gráficas (existentes y nuevas) se guardan en:

- `registers/data/test/results/plots`

## Interpretación de métricas clave

- `error_pct`: porcentaje de solicitudes fallidas sobre `total_requests`.
- `rollback_409_count`: conflictos HTTP `409` contados en la ejecución.
- En escenarios controlados de conflicto (`G_rollback_carga`, `G_rollback_carga_1pct`), el conteo reportado de `rollback_409_count` se limita por diseño a `conflict_requests` para mantener coherencia con la carga configurada.
