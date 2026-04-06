# G — Prueba estocástica de tasa de llegada de usuarios

## Objetivo

Simular un escenario realista donde los usuarios llegan al sistema a una **tasa constante** (rpm = requests por minuto), en lugar de lanzar todos los usuarios simultáneamente.

Esto se asemeja más al comportamiento real de un sistema en producción donde los usuarios llegan de forma distribuida en el tiempo.

## Metodología

Para cada nivel de `rpm_objetivo`:

1. Se calcula el intervalo entre requests: `intervalo = 60s / rpm`
2. Se lanzan requests a esa tasa usando intervalos uniformes durante **60 segundos**
3. Se capturan las métricas de todos los requests completados en esa ventana

El endpoint medido es `GET /health` (no consume stock).

## Niveles

| rpm_objetivo | Intervalo entre requests |
|---|---|
| 100 | 600 ms |
| 1000 | 60 ms |
| 5000 | 12 ms |
| 10000 | 6 ms |
| 50000 | 1.2 ms |
| 200000 | 0.3 ms |

## Resultado

- `results/estocastico.csv`: métricas por nivel (rpm_objetivo, rpm_real, avg_ms, p95_ms, error_pct)
- Gráfica: `registers/data/test/results/plots/g_estocastico_rpm_vs_latencia.png`

## Ejecución

```bash
uv run python -m scripts.disponibilidad.run_all --solo G_estocastico
```

O directamente:

```bash
uv run python -m scripts.disponibilidad.g_scaling_rollback test-estocastico
```

## Interpretación

- `rpm_real` cercano a `rpm_objetivo` → el sistema pudo atender la tasa pedida
- `rpm_real` mucho menor → el sistema está saturado y no puede procesar a esa velocidad
- `avg_ms` creciente con el rpm → latencia bajo carga real
- `error_pct` > 0 → el sistema empieza a fallar a esa tasa
