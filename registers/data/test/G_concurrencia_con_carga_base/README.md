# G — Concurrencia con carga de fondo

## Objetivo

Simular un sistema en régimen “normal” con muchas peticiones ligeras (`GET /health`) y, en paralelo, **dos** reservas simultáneas sobre el **mismo** producto con stock limitado. Permite observar detección de conflicto bajo ruido de red/servicio.

## Parámetros (entorno)

| Variable | Por defecto |
|----------|-------------|
| `G_CARGA_USUARIOS` | `200` (peticiones de fondo concurrentes) |
| `G_CARGA_ITERACIONES` | `3` ciclos de fondo mientras se lanzan las 2 reservas |

## Resultados

- `results/g_concurrencia_con_carga.csv`: métricas de fondo (éxitos/errores) y resultado de las dos reservas conflictivas.

## Ejecución manual

```bash
uv run python scripts/disponibilidad/g_reservations.py con-carga
```
