# G — Capacidad: usuarios concurrentes

## Objetivo

Estimar cuántas peticiones concurrentes soporta el servicio de reservas (o health) con configuraciones **10, 100, 1000, 100000** (parametrizable).

## Parámetros

| Variable | Significado |
|----------|-------------|
| `G_CAPACIDAD_VUS` | Número de usuarios virtuales concurrentes (default `100`) |
| `G_CAPACIDAD_REQUESTS` | Peticiones totales a distribuir (default `1000`) |
| `G_CAPACIDAD_URL` | Ruta relativa (default `/health`; use `/reservations/reserve` con cuidado — muta estado) |
| `G_CAPACIDAD_MAX_VUS` | Tope de seguridad para no colgar el equipo (default `5000`) |

Para simular **100000**, establezca `G_CAPACIDAD_VUS=100000` y, si aplica, suba `G_CAPACIDAD_MAX_VUS` sabiendo el riesgo en laptops.

## Resultados

- `results/g_capacidad.csv`: escenario, VUs, duración total, RPS, % errores, p95 ms.

## Ejecución manual

```bash
uv run python scripts/disponibilidad/g_reservations.py capacidad
```

Para barrer varios tamaños:

```bash
uv run python scripts/disponibilidad/g_reservations.py capacidad-sweep
```
