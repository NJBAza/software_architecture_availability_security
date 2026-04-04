# F1 — Consultas parametrizadas

**Referencia:** plan de pruebas Reto 2, sección F.

## Objetivo

Confirmar ausencia de concatenación insegura obvia en SQL de `apps/services/IDS.py` y `apps/database.py` mediante revisión estática automatizada.

## Respuesta esperada

- Uso de placeholders `%s` (psycopg2) o `:name` / `?` (SQLite); filas marcadas como revisadas en el CSV.

## Resultados

- `results/f1_sql_audit.csv`: archivo, tipo de hallazgo, línea, descripción.

## Ejecución manual

```bash
uv run python scripts/disponibilidad/f1_parametrized_audit.py
```

No requiere HTTP ni PostgreSQL en ejecución.
