# Pruebas Test V2: Concurrencia, Disponibilidad y Seguridad

## Requisitos previos (dos stacks)

Las pruebas de **disponibilidad (bloque 2)** usan el servicio de reservas y su PostgreSQL. Las de **seguridad (bloque 3)** cargan usuarios en otra base PostgreSQL para el IDS.

### 1) Registros (reservas + `warehouse_stock`)

Desde la raiz del repositorio:

```powershell
cd registers
docker compose down -v --remove-orphans
docker compose up -d
cd ..
```

Por defecto, `reservations_db` escucha en el host en el puerto **5434** (usuario `root`, contraseña `root`, base `reservations_db`). El servicio de reservas suele exponerse en **http://localhost:8002**.

### 2) IDS (PostgreSQL en 5432)

En paralelo o antes del bloque seguridad:

```powershell
docker compose -f docker-compose.ids.yml up -d
```

Cargue esquema y datos semilla (PowerShell, desde la raiz del repo):

```powershell
Get-Content scripts/ids_postgres_schema.sql | docker exec -i ids_postgres psql -U postgres -d postgres
Get-Content scripts/ids_postgres_seed.sql | docker exec -i ids_postgres psql -U postgres -d postgres
```

La API IDS debe estar en ejecucion (por defecto el script usa `http://127.0.0.1:8000`).

## Variables de entorno (opcional)

| Variable | Uso |
|----------|-----|
| `RSV_BASE_URL` | URL del servicio de reservas (default `http://localhost:8002`) |
| `V2_RSV_DB_HOST`, `V2_RSV_DB_PORT`, `V2_RSV_DB_NAME`, `V2_RSV_DB_USER`, `V2_RSV_DB_PASSWORD` | Conexion directa a la BD de reservas para ajustar stock antes de conflictos (2a/2b). Defaults alineados con `registers/docker-compose.yml` (puerto host **5434**). |
| `V2_CONFLICT_STOCK` | `stock_id` para el escenario dos clientes (default `STK00001`) |
| `IDS_BASE_URL` | URL de la API IDS |
| `IDS_DB_HOST`, `IDS_DB_PORT`, `IDS_DB_NAME`, `IDS_DB_USER`, `IDS_DB_PASSWORD` | Conexion usada por los scripts para `TRUNCATE`/`INSERT` de usuarios de prueba (default: localhost:5432, `postgres`/`1234`) |
| `V2_IDS_STOCK_REF` | Valor fijo escrito en `stock_id_referencia` en los CSV de detalle de seguridad (default: igual a `V2_CONFLICT_STOCK` o `STK00001`) |

Si PostgreSQL IDS no esta levantado, el bloque seguridad fallara con un mensaje que indica `docker-compose.ids.yml` y los scripts SQL.

## Ejecucion

Desde la raiz del repositorio:

```powershell
python -m scripts.disponibilidad.run_test_v2

# Solo un bloque
python -m scripts.disponibilidad.run_test_v2 --solo concurrencia
python -m scripts.disponibilidad.run_test_v2 --solo disponibilidad
python -m scripts.disponibilidad.run_test_v2 --solo seguridad
```

## Pruebas incluidas

### Bloque 1 — Concurrencia sin conflictos
Envia 10, 100, 1000, 5000, 10000, 50000, 100000 solicitudes POST /reserve a productos distintos (sin conflicto).

### Bloque 2 — Disponibilidad / Rollback
- **2a**: Dos clientes reservan el mismo producto simultaneamente. Antes de la prueba se deja **exactamente 1 unidad disponible** en `warehouse_stock` para ese `stock_id`. Medicion en nanosegundos. Rollback exitoso = uno HTTP 200 + otro HTTP 409.
- **2b**: Mezcla de solicitudes con 1% de conflicto en parejas. Cada pareja apunta a un producto distinto; antes de cada nivel se ajusta el stock de esos productos a una unidad disponible. Se verifica que cada pareja tenga un rollback exitoso.

### Bloque 3 — Seguridad IDS
- **3a**: Deteccion de 1 usuario peligroso en menos de 300ms (geo+dispositivo = 80 >= 75).
- **3b**: 1% de usuarios peligrosos a escala (10 a 100,000 solicitudes).
- **3c**: 1 condicion individual (geo, dispositivo, tasa) — ninguna sola alcanza el umbral de fraude.
- **3d**: 2 condiciones combinadas — solo geo+dispositivo (50+30=80) alcanza fraude; las demas no.

Los CSV de detalle de seguridad incluyen la columna **`stock_id_referencia`** (trazabilidad con el mismo identificador de producto de referencia en todas las filas).

## Resultados

- CSVs de resumen y detalle por prueba en cada subcarpeta `/results/`
- Graficas en `results/plots/`
