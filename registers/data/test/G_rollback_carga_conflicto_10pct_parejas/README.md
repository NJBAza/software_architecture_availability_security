# G — Rollback bajo carga con conflicto 10% en parejas

## Objetivo

Medir rollback bajo carga en niveles 20..2,000,000 usuarios cuando:

- 10% de usuarios conflictuan en parejas (2 en 2),
- cada pareja disputa un producto distinto.

## Resultado

- `results/rollback_10pct_parejas.csv`
- `results/plots/test2_2_metrics_vs_vus.png`

## Ejecucion

```bash
uv run python scripts/disponibilidad/g_scaling_rollback.py test2-2-rollback-10pct
```
