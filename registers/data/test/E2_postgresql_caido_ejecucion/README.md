# E2 — PostgreSQL caído en tiempo de ejecución

**Referencia:** plan de pruebas Reto 2, sección E.

## Objetivo

Observar el comportamiento cuando PostgreSQL IDS deja de estar disponible **durante** el servicio (petición al endpoint IDS).

## Prerrequisitos

- Contenedor `ids_postgres` en ejecución (compose IDS).
- API raíz en marcha: `uvicorn apps.main:app --host 127.0.0.1 --port 8000`
- El script **detiene** temporalmente `ids_postgres`, envía una petición `GET /api/v1/ids/detectar/200` y **reinicia** el contenedor.

## Respuesta esperada

- HTTP **500** o error de cliente (timeout / conexión) según manejo en `IDS.py`; sin cuelgue indefinido del worker.

## Resultados

- `results/e2_runtime.csv`: código HTTP o tipo de error, duración ms, notas.

## Ejecución manual

```bash
uv run python scripts/disponibilidad/e2_runtime_failure.py
```

Variable opcional: `IDS_BASE_URL` (por defecto `http://127.0.0.1:8000`).
