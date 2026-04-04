# E1 — PostgreSQL caído al arranque

**Referencia:** plan de pruebas Reto 2, sección E (disponibilidad).

## Objetivo

Medir el impacto en disponibilidad cuando el pool `ThreadedConnectionPool` en `apps/services/IDS.py` no puede conectar al iniciar la aplicación: la importación del módulo IDS falla si PostgreSQL no está disponible.

## Elementos a configurar

- PostgreSQL IDS **detenido** (por ejemplo `docker stop ids_postgres`) o puerto `5432` sin servicio.
- Ejecutar el script `e1_start_failure` vía `run_all.py` o manualmente.

## Respuesta esperada

- Fallo al importar `apps.services.IDS` o al arrancar `uvicorn` con mensaje de error de conexión documentado.
- Sin bloqueo indefinido (timeout acotado en el script).

## Resultados

- `results/e1_arranque.csv`: timestamp, `exito_documentado` (sí/no), código de salida, fragmento de error.

## Ejecución manual

```bash
uv run python scripts/disponibilidad/e1_start_failure.py
```
