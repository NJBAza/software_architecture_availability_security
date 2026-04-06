"""F1: auditoría estática de consultas parametrizadas (IDS + SQLite)."""

from __future__ import annotations

import re
from pathlib import Path

from scripts.disponibilidad.common import REPO_ROOT, TEST_DATA_ROOT, append_csv_row, now_iso

OUT_CSV = TEST_DATA_ROOT / "F1_consultas_parametrizadas" / "results" / "f1_sql_audit.csv"
FIELDS = ["timestamp_utc", "archivo", "linea", "categoria", "detalle"]

TARGETS = [
    REPO_ROOT / "apps" / "services" / "IDS.py",
    REPO_ROOT / "apps" / "database.py",
]


def audit_file(path: Path) -> list[dict[str, str]]:
    rel = path.relative_to(REPO_ROOT).as_posix()
    rows: list[dict[str, str]] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if "execute(" not in line and "executemany(" not in line:
            continue

        # Heurística: f-string o .format en la misma línea del execute
        if re.search(r'\bf["\']', line) or ".format(" in line:
            rows.append(
                {
                    "timestamp_utc": now_iso(),
                    "archivo": rel,
                    "linea": str(i),
                    "categoria": "revisar",
                    "detalle": "Posible interpolación en SQL; revisar manualmente.",
                },
            )
            continue

        window = "\n".join(lines[max(0, i - 8) : i + 1])
        if "%s" in window or ":id" in window or ":stock_id" in window or "?" in window:
            rows.append(
                {
                    "timestamp_utc": now_iso(),
                    "archivo": rel,
                    "linea": str(i),
                    "categoria": "parametrizada",
                    "detalle": "Placeholders %s, :named o ? detectados cerca de execute.",
                },
            )
        else:
            rows.append(
                {
                    "timestamp_utc": now_iso(),
                    "archivo": rel,
                    "linea": str(i),
                    "categoria": "revisar",
                    "detalle": "execute sin placeholder obvio en ventana local; revisar query multilínea.",
                },
            )

    return rows


def main() -> None:
    all_rows: list[dict[str, str]] = []
    for p in TARGETS:
        if not p.exists():
            continue
        found = audit_file(p)
        all_rows.extend(found)
        cats = {r["categoria"] for r in found}
        all_rows.append(
            {
                "timestamp_utc": now_iso(),
                "archivo": p.relative_to(REPO_ROOT).as_posix(),
                "linea": "0",
                "categoria": "resumen",
                "detalle": f"lineas_execute={len(found)} categorias={cats}",
            },
        )

    for r in all_rows:
        append_csv_row(OUT_CSV, FIELDS, r)

    print(f"F1: {len(all_rows)} filas escritas en {OUT_CSV}")


if __name__ == "__main__":
    main()
