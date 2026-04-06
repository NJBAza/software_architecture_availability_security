# G — Rollback bajo carga con conflicto 1%

Niveles de usuarios: `10,100,1000,5000,10000,20000`.

Regla:
- 1% de solicitudes disputa el mismo `stock_id`.
- 99% restante usa trafico normal.

Resultados:
- `results/rollback_1pct.csv`
- Graficas en `registers/data/test/results`.

Ejecucion:

```bash
uv run python -m scripts.disponibilidad.g_scaling_rollback test-rollback-1pct
```
