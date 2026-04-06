# G — Concurrencia: mismo elemento (stock)

## Objetivo

Determinar si el sistema detecta correctamente cuando **dos o más** clientes intentan reservar la **misma** unidad de stock disponible: una petición debe tener éxito (200) y las demás conflicto (409 Insufficient stock), sin corrupción de `qty_reserved` / `qty_on_hand`.

## Prerrequisitos

- `reservations_service` en `http://localhost:8002` (Docker Compose en `registers/`).
- Datos ingestados. El script usa por defecto `STK00001` con **1** unidad disponible y cantidad de reserva **1** para forzar exclusión mutua.

## Resultados

- `results/g_concurrencia_mismo_stock.csv`: orden_id, código HTTP, duración_ms, cuerpo resumido.

## Ejecución manual

```bash
uv run python scripts/disponibilidad/g_reservations.py mismo-stock
```

Variables: `RSV_BASE_URL`, `G_STOCK_ID`, `G_RESERVE_QTY`.
