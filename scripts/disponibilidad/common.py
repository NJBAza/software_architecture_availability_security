"""Rutas del repositorio y utilidades CSV."""

from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_DATA_ROOT = REPO_ROOT / "registers" / "data" / "test"
GLOBAL_SUMMARY_CSV = TEST_DATA_ROOT / "results" / "resumen_global.csv"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def ensure_csv_header(path: Path, fieldnames: list[str]) -> None:
    """Crea o reinicia el CSV si los headers no coinciden con fieldnames."""
    ensure_parent(path)
    expected = ",".join(fieldnames)
    if path.exists() and path.stat().st_size > 0:
        with path.open(encoding="utf-8") as f:
            existing = f.readline().strip()
        if existing != expected:
            path.write_text(expected + "\n", encoding="utf-8")
        return
    path.write_text(expected + "\n", encoding="utf-8")


def append_csv_row(path: Path, fieldnames: list[str], row: dict[str, object]) -> None:
    ensure_parent(path)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            w.writeheader()
        w.writerow(row)


def env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v == "":
        return default
    return int(v)


def env_str(name: str, default: str) -> str:
    v = os.environ.get(name)
    return default if v is None or v == "" else v
