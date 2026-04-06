# Dos clientes mismo producto

Dos solicitudes concurrentes al mismo stock_id. Se mide en nanosegundos.

Un rollback es exitoso si un cliente recibe HTTP 200 y el otro HTTP 409.

## Resultados
- `results/detalle.csv` — order_id, stock_id, http_status, duracion_ns, es_rollback_exitoso
