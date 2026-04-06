"""Preparacion idempotente de stock para escenarios G de alta carga."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time

import httpx

# region agent log
def _dbg(hypothesis_id: str, message: str, data: dict) -> None:
    try:
        payload = {
            "sessionId": "8346ff",
            "runId": "run1",
            "hypothesisId": hypothesis_id,
            "location": "scripts/disponibilidad/prepare_g_test_data.py",
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        with open("debug-8346ff.log", "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


_dbg(
    "H1",
    "module_import_start",
    {
        "cwd": os.getcwd(),
        "file": __file__,
        "argv0": sys.argv[0] if sys.argv else "",
        "sys_path_head": sys.path[:5],
    },
)
# endregion

try:
    from scripts.disponibilidad.common import env_int, env_str
except ModuleNotFoundError as e:
    # region agent log
    _dbg(
        "H1",
        "module_import_failed",
        {
            "error": str(e),
            "cwd": os.getcwd(),
            "file_parent": str(Path(__file__).resolve().parent),
            "repo_root_guess": str(Path(__file__).resolve().parents[2]),
            "sys_path_head": sys.path[:8],
        },
    )
    # endregion
    raise

RSV_DEFAULT = "http://localhost:8002"


def _base() -> str:
    return env_str("RSV_BASE_URL", RSV_DEFAULT).rstrip("/")


def _fetch_stock() -> list[dict]:
    with httpx.Client() as c:
        r = c.get(f"{_base()}/stock", timeout=60.0)
        r.raise_for_status()
        return r.json()


def _update_stock(stock_id: str, qty_on_hand: int, qty_reserved: int) -> None:
    # Endpoint administrativo no existe en API publica; se deja como opcion SQL externa.
    # El script cumple validacion/preparacion detectando faltantes para que se corrija antes del test.
    _ = (stock_id, qty_on_hand, qty_reserved)


def run_validate_only(min_available: int, required: list[str]) -> tuple[int, list[str], list[tuple[str, int]], dict[str, dict]]:
    rows = _fetch_stock()
    by_id = {str(r.get("stock_id")): r for r in rows}
    missing = [sid for sid in required if sid not in by_id]
    low = []
    for sid in required:
        row = by_id.get(sid)
        if not row:
            continue
        avail = int(row.get("available_quantity", 0) or 0)
        if avail < min_available:
            low.append((sid, avail))

    print({"required_ids": len(required), "missing": missing, "low_available": low, "min_available": min_available})
    rc = 0 if (not missing and not low) else 1
    return rc, missing, low, by_id


def build_restock_sql(min_available: int, low: list[tuple[str, int]], by_id: dict[str, dict]) -> str:
    lines = [
        "-- SQL sugerido para reponer stock en pruebas G",
        "-- Ejecutar contra reservations_db antes de la corrida de carga.",
    ]
    for sid, avail in low:
        row = by_id.get(sid, {})
        qty_on_hand = int(row.get("qty_on_hand", 0) or 0)
        qty_reserved = int(row.get("qty_reserved", 0) or 0)
        delta = max(0, min_available - avail)
        new_qoh = qty_on_hand + delta
        lines.append(
            "UPDATE warehouse_stock "
            f"SET qty_on_hand = {new_qoh}, qty_reserved = {qty_reserved} "
            f"WHERE stock_id = '{sid}';"
        )
    return "\n".join(lines) + "\n"


def run_prepare(emit_sql_path: str) -> int:
    min_available = env_int("G_PREP_MIN_AVAILABLE", 500)
    hot_ids = [s.strip() for s in env_str("G_PREP_HOT_IDS", "STK00001,STK00002,STK00003").split(",") if s.strip()]
    normal_ids = [
        s.strip()
        for s in env_str("G_PREP_NORMAL_IDS", "STK00020,STK00021,STK00022,STK00023,STK00024").split(",")
        if s.strip()
    ]
    required = hot_ids + normal_ids
    rc, missing, low, by_id = run_validate_only(min_available, required)
    if emit_sql_path and low:
        sql = build_restock_sql(min_available, low, by_id)
        out = Path(emit_sql_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(sql, encoding="utf-8")
        print({"sql_written": str(out), "updates": len(low)})
    if missing:
        print({"missing_stock_ids": missing})
    return rc


def main() -> None:
    # region agent log
    _dbg(
        "H2",
        "main_entry",
        {
            "cwd": os.getcwd(),
            "argv": sys.argv,
        },
    )
    # endregion
    p = argparse.ArgumentParser(description="Valida datos base para pruebas G de alta carga")
    p.add_argument("--validate-only", action="store_true", help="Solo valida disponibilidad minima de stock")
    p.add_argument(
        "--emit-restock-sql",
        default="",
        help="Ruta de salida para generar SQL de reposicion sugerida si hay stock bajo",
    )
    args = p.parse_args()
    rc = run_prepare(args.emit_restock_sql)
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
