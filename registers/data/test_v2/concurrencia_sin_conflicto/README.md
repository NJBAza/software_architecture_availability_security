# Concurrencia sin conflictos

Envia solicitudes POST /reservations/reserve a productos distintos (rotando entre 5000 stock_ids) para medir la capacidad del sistema sin conflictos.

Niveles: 10, 100, 1000, 5000, 10000, 50000, 100000 solicitudes.

## Resultados
- `results/resumen.csv` — metricas agregadas por nivel
- `results/detalle.csv` — una fila por solicitud (order_id, stock_id, http_status, duracion_ms)
