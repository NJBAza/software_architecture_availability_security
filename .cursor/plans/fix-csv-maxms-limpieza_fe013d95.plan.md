---
name: fix-csv-maxms-limpieza
overview: Corregir el error de CSV tokenization en g_capacidad, reemplazar min_ms por max_ms en todas las pruebas de tiempo, y eliminar carpetas de test y scripts obsoletos.
todos:
  - id: fix-csv-header-capacidad
    content: Agregar ensure_csv_header en cmd_capacidad y cmd_capacidad_sweep (g_reservations.py)
    status: completed
  - id: replace-min-max-ms
    content: Renombrar min_ms a max_ms en g_scaling_rollback.py y g_reservations.py (campos, cálculo, escritura CSV)
    status: completed
  - id: update-plots-maxms
    content: Actualizar plot_all_g.py para usar max_ms en lugar de min_ms
    status: completed
  - id: delete-obsolete-folders
    content: Eliminar carpetas G_concurrencia_con_carga_base, G_rollback_carga_conflicto_5pct, G_rollback_conflicto_dos_usuarios
    status: completed
  - id: delete-obsolete-scripts
    content: Eliminar plot_g_results.py y plot_g_new_tests.py
    status: completed
isProject: false
---

# Fix CSV, max_ms y limpieza de obsoletos

## Error 1 — CSV header mismatch en `g_capacidad`

El archivo `g_capacidad.csv` tiene header de 9 campos (formato antiguo). La nueva ejecución escribe filas de 11 campos. Pandas falla al leer: `Expected 9 fields in line 3, saw 11`.

**Fix en [scripts/disponibilidad/g_reservations.py](scripts/disponibilidad/g_reservations.py):** Agregar `ensure_csv_header(out, fields)` al inicio de `cmd_capacidad` y `cmd_capacidad_sweep`, igual a como ya se hace en `cmd_diez_parejas`. Esto resetea el CSV si el header no coincide.

## Cambio 2 — `min_ms` → `max_ms` en pruebas de tiempo

El usuario quiere ver el **tiempo máximo** observado por un usuario, no el mínimo. Afecta:

### `g_scaling_rollback.py`

- `RESULT_FIELDS`: renombrar `"min_ms"` → `"max_ms"`
- `RunMetrics` dataclass: campo `min_ms: float` → `max_ms: float`
- `_run_health_load`: `min_ms = min(latencies)` → `max_ms = max(latencies)`
- `_run_load`: ídem
- `_write_row`: `"min_ms": f"{metrics.min_ms:.2f}"` → `"max_ms": f"{metrics.max_ms:.2f}"`
- `_ensure_csv`: campo renombrado automáticamente vía `RESULT_FIELDS`

### `g_reservations.py`

- `_capacidad_once`: retornar `"max_ms"` en lugar de `"min_ms"`, calcular `max(latencies)`
- `cmd_capacidad` fields list: `"min_ms"` → `"max_ms"`
- `cmd_capacidad_sweep` fields list: ídem

### `plot_all_g.py`

- `plot_g_capacidad`: columna `"min_ms"` → `"max_ms"`, actualizar label
- `plot_g_escalado`: `_num` con `"max_ms"` en lugar de `"min_ms"` (aunque no se grafica actualmente)
- `plot_g_latencia_escalonada`: `"min_ms"` → `"max_ms"`, mostrar curva `max_ms`

## Cambio 3 — Eliminar carpetas obsoletas

Carpetas sin escenario activo en `run_all.py`:

- `registers/data/test/G_concurrencia_con_carga_base/`
- `registers/data/test/G_rollback_carga_conflicto_5pct/`
- `registers/data/test/G_rollback_conflicto_dos_usuarios/`

## Cambio 4 — Eliminar scripts de plots obsoletos

- `scripts/disponibilidad/plot_g_results.py` → reemplazado por `plot_all_g.py`
- `scripts/disponibilidad/plot_g_new_tests.py` → reemplazado por `plot_all_g.py`

