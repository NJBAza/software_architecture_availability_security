# G — Diez parejas, diez productos distintos

## Objetivo

Ejecutar **10 pares** de reservas concurrentes; **cada par** disputa un `stock_id` distinto (10 productos). Se valida que en cada producto solo una reserva gane cuando el stock disponible para el escenario es 1 unidad por SKU de prueba.

## Configuración

- Lista de `stock_id` configurable en el script (por defecto `STK00001` … `STK00010` en sentido lógico: se usan los primeros 10 IDs del CSV si existen con stock suficiente, o los definidos por `G_MULTI_STOCK_IDS` separados por coma).

## Resultados

- `results/g_diez_parejas.csv`: stock_id, ganador (200) vs perdedor (409), latencias.

## Ejecución manual

```bash
uv run python scripts/disponibilidad/g_reservations.py diez-parejas
```

**Nota:** Si algún SKU no tiene disponibilidad 1 tras ingest inicial, ajuste `G_MULTI_STOCK_IDS` o reinicie volúmenes y vuelva a cargar datos.
