# G — Latencia escalonada por usuarios

Niveles de usuarios:
- `10`, `100`
- `200..1000` en pasos de `100`
- `2000..20000` en pasos de `1000`

Metrica principal:
- tiempo promedio de respuesta por nivel (`avg_ms`).

Resultados:
- `results/latencia_escalonada.csv`
- Graficas en `registers/data/test/results`.

Ejecucion:

```bash
uv run python -m scripts.disponibilidad.g_scaling_rollback test-latencia-escalonada
```
