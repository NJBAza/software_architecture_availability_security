# G — Rollback / tiempo de conflicto e integridad

## Objetivo

Ante un conflicto de reserva por concurrencia (HTTP **409**), documentar:

1. **Latencia** percibida por el cliente en la petición fallida (aproximación al coste de rollback transaccional del servidor).
2. **Cero pérdida de datos**: `qty_on_hand` y `qty_reserved` coherentes vía `GET /stock/{stock_id}` antes y después del intento.

## Criterio de referencia

- Objetivo de negocio citado en el enunciado: rollback **&lt; 300 ms** (medido como tiempo de respuesta HTTP del 409 en este entorno). Si el hardware no lo cumple, el CSV deja constancia del **p95** y si se cumple el umbral.

## Resultados

- `results/g_rollback_tiempo.csv`: timestamps, latencias ms, `qty_on_hand`, `qty_reserved`, `available_quantity`, cumple_300ms (sí/no).

## Ejecución manual

```bash
uv run python scripts/disponibilidad/g_reservations.py rollback-tiempo
```
