# Rollback 1% conflicto en parejas

Mezcla de solicitudes normales y conflictivas (1% de conflicto). Los conflictos se organizan en parejas de 2 usuarios, donde cada pareja apunta a un producto distinto.

Niveles: 200, 2000, 20000, 200000 solicitudes.

Un rollback exitoso significa que para cada pareja, un usuario recibio HTTP 200 y el otro HTTP 409.

## Resultados
- `results/resumen.csv` — nivel, parejas_conflicto, rollback_exitosos, rollback_fallidos, latencias
- `results/detalle.csv` — order_id, stock_id, tipo (conflicto/normal), pareja_id, http_status, duracion_ms
