# G — Escalado de tiempo de respuesta por usuarios

## Objetivo

Medir el tiempo promedio de respuesta conforme crece la concurrencia
(10, 100, 1000, ...), y detener en el primer punto donde:

- `avg_ms >= 5000`, o
- ocurre error (`error_pct > 0`).

## Resultado

- `results/escalado_respuesta.csv`
- `results/plots/test1_avg_ms_vs_vus.png`

## Ejecucion

```bash
uv run python scripts/disponibilidad/g_scaling_rollback.py test1-escalado
```

Variables utiles:
- `G_SCALE_LEVELS` (por defecto: `10,100,1000,10000,100000,1000000,2000000`)
- `G_CAPACIDAD_URL` (por defecto: `/health`)
- `G_STOP_MS` (por defecto: `5000`)
