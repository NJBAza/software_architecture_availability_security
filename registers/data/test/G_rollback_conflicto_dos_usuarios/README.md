# G — Rollback con conflicto fijo de 2 usuarios

Niveles de usuarios: `10,100,1000,5000,10000,20000`.

Regla:
- En cada nivel, exactamente 2 solicitudes disputan el mismo `stock_id`.
- El resto del trafico usa `stock_id` normal.

Resultados:
- `results/rollback_dos_usuarios.csv`
- Graficas en `registers/data/test/results`.

Ejecucion:

```bash
uv run python -m scripts.disponibilidad.g_scaling_rollback test-rollback-dos-usuarios
```
