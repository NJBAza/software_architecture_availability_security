# E3 — Carga concurrente IDS

**Referencia:** plan de pruebas Reto 2, sección E (complementa capacidad / pool).

## Objetivo

Comprobar que bajo paralelismo las conexiones se devuelven al pool (`putconn`) y no hay degradación inaceptable en el endpoint IDS con usuario semilla **200** (baseline D2).

## Prerrequisitos

- PostgreSQL IDS sembrado (`scripts/ids_postgres_seed.sql`).
- API raíz en `IDS_BASE_URL` (por defecto `http://127.0.0.1:8000`).

## Parámetros (variables de entorno)

| Variable | Significado | Por defecto |
|----------|-------------|-------------|
| `E3_CONCURRENCY` | Peticiones concurrentes (async) | `50` |
| `E3_REQUESTS` | Total de peticiones | `500` |
| `E3_TIMEOUT` | Timeout por petición (s) | `30` |

## Respuesta esperada

- Tasa de error &lt; umbral documentado (p. ej. 1 %); latencias registradas en CSV.

## Resultados

- `results/e3_carga_ids.csv`: por petición o resumen agregado (p95, errores %).

## Ejecución manual

```bash
uv run python scripts/disponibilidad/e3_load_ids.py
```
