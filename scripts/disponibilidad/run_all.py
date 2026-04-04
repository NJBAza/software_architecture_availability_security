"""Orquestador: E1–E3, F1 y escenarios G; escribe resumen_global.csv."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import httpx

from scripts.disponibilidad.common import GLOBAL_SUMMARY_CSV, REPO_ROOT, append_csv_row, now_iso
from scripts.disponibilidad.e1_start_failure import run as e1_run
from scripts.disponibilidad.e2_runtime_failure import run as e2_run
from scripts.disponibilidad.e3_load_ids import run_e3
from scripts.disponibilidad.f1_parametrized_audit import main as f1_main
from scripts.disponibilidad.g_reservations import (
    cmd_capacidad,
    cmd_capacidad_sweep,
    cmd_diez_parejas,
    cmd_mismo_stock,
    cmd_rollback_tiempo,
)
from scripts.disponibilidad.g_scaling_rollback import (
    cmd_rollback_carga_unificado,
    cmd_test_estocastico,
    cmd_test_latencia_escalonada,
    cmd_test_rollback_1pct,
    cmd_test1_escalado,
    cmd_test2_2_rollback_10pct,
)
from scripts.disponibilidad.plot_all_g import main as plot_all_g_main

SUMMARY_FIELDS = [
    "timestamp_utc",
    "escenario",
    "exito",
    "duracion_s",
    "notas",
]


def _wait_api(base: str, timeout: float = 90.0) -> bool:
    url = f"{base.rstrip('/')}/"
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            r = httpx.get(url, timeout=3.0)
            if r.status_code == 200:
                return True
        except httpx.HTTPError:
            pass
        time.sleep(0.4)
    return False


def _start_uvicorn() -> subprocess.Popen[bytes]:
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_timed(name: str, fn: Callable[[], None]) -> tuple[bool, float, str]:
    t0 = time.perf_counter()
    try:
        fn()
        ok = True
        msg = "ok"
    except Exception as e:
        ok = False
        msg = str(e)[:500]
    return ok, time.perf_counter() - t0, msg


def main() -> None:
    p = argparse.ArgumentParser(description="Ejecutar batería de disponibilidad")
    p.add_argument("--solo", type=str, default="", help="Solo un escenario (ej. E3, F1, G_mismo)")
    p.add_argument("--skip", type=str, default="", help="Lista separada por coma a omitir")
    p.add_argument("--no-docker-e1e2", action="store_true", help="No usar docker stop/start ids_postgres")
    p.add_argument(
        "--start-api",
        action="store_true",
        help="Levantar uvicorn apps.main en :8000 para E2/E3",
    )
    p.add_argument("--api-base", default=os.environ.get("IDS_BASE_URL", "http://127.0.0.1:8000"))
    p.add_argument(
        "--with-capacidad-sweep",
        action="store_true",
        help="Incluir barrido 10,100,1000,100000 (puede ser muy pesado)",
    )
    args = p.parse_args()

    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    solo = args.solo.strip()

    scenarios_order = [
        "E1",
        "E2",
        "E3",
        "F1",
        "G_mismo",
        "G_rollback_carga",
        "G_diez",
        "G_rollback",
        "G_capacidad",
        "G_escalado_tiempo_respuesta",
        "G_rollback_carga_10pct_parejas",
        "G_rollback_carga_1pct",
        "G_latencia_escalonada",
        "G_estocastico",
    ]
    if args.with_capacidad_sweep:
        scenarios_order.append("G_capacidad_sweep")

    if solo:
        scenarios_order = [solo]

    proc: subprocess.Popen[bytes] | None = None
    use_docker = not args.no_docker_e1e2

    def summarize(name: str, ok: bool, dur: float, notes: str = "") -> None:
        append_csv_row(
            GLOBAL_SUMMARY_CSV,
            SUMMARY_FIELDS,
            {
                "timestamp_utc": now_iso(),
                "escenario": name,
                "exito": "si" if ok else "no",
                "duracion_s": f"{dur:.3f}",
                "notas": notes[:800],
            },
        )

    try:
        for sc in scenarios_order:
            if sc in skip:
                summarize(sc, True, 0.0, "omitido_por_skip")
                continue

            if sc in {"E2", "E3"} and args.start_api and proc is None:
                proc = _start_uvicorn()
                if not _wait_api(args.api_base):
                    summarize("uvicorn_start", False, 0.0, "API no respondio a tiempo")
                    break

            if sc == "E1":
                t0 = time.perf_counter()
                rc = e1_run(use_docker=use_docker)
                ok = rc == 0
                summarize("E1", ok, time.perf_counter() - t0, "import_IDS_con_PG_detenido")
            elif sc == "E2":
                t0 = time.perf_counter()
                rc = e2_run(use_docker=use_docker, base_url=args.api_base)
                summarize("E2", True, time.perf_counter() - t0, "ver_e2_runtime_csv")
            elif sc == "E3":
                t0 = time.perf_counter()
                try:
                    run_e3(base_url=args.api_base)
                    summarize("E3", True, time.perf_counter() - t0, "ver_e3_carga_csv")
                except Exception as e:
                    summarize("E3", False, time.perf_counter() - t0, str(e))
            elif sc == "F1":
                t0 = time.perf_counter()
                try:
                    f1_main()
                    summarize("F1", True, time.perf_counter() - t0, "ver_f1_csv")
                except Exception as e:
                    summarize("F1", False, time.perf_counter() - t0, str(e))
            elif sc == "G_mismo":
                ok, dur, msg = _run_timed("G_mismo", cmd_mismo_stock)
                summarize("G_mismo", ok, dur, msg)
            elif sc == "G_rollback_carga":
                ok, dur, msg = _run_timed("G_rollback_carga", cmd_rollback_carga_unificado)
                summarize("G_rollback_carga", ok, dur, msg)
            elif sc == "G_diez":
                ok, dur, msg = _run_timed("G_diez", cmd_diez_parejas)
                summarize("G_diez", ok, dur, msg)
            elif sc == "G_rollback":
                ok, dur, msg = _run_timed("G_rollback", cmd_rollback_tiempo)
                summarize("G_rollback", ok, dur, msg)
            elif sc == "G_capacidad":
                ok, dur, msg = _run_timed("G_capacidad", cmd_capacidad)
                summarize("G_capacidad", ok, dur, msg)
            elif sc == "G_escalado_tiempo_respuesta":
                ok, dur, msg = _run_timed("G_escalado_tiempo_respuesta", cmd_test1_escalado)
                summarize("G_escalado_tiempo_respuesta", ok, dur, msg)
            elif sc == "G_rollback_carga_10pct_parejas":
                ok, dur, msg = _run_timed("G_rollback_carga_10pct_parejas", cmd_test2_2_rollback_10pct)
                summarize("G_rollback_carga_10pct_parejas", ok, dur, msg)
            elif sc == "G_rollback_carga_1pct":
                ok, dur, msg = _run_timed("G_rollback_carga_1pct", cmd_test_rollback_1pct)
                summarize("G_rollback_carga_1pct", ok, dur, msg)
            elif sc == "G_latencia_escalonada":
                ok, dur, msg = _run_timed("G_latencia_escalonada", cmd_test_latencia_escalonada)
                summarize("G_latencia_escalonada", ok, dur, msg)
            elif sc == "G_estocastico":
                ok, dur, msg = _run_timed("G_estocastico", cmd_test_estocastico)
                summarize("G_estocastico", ok, dur, msg)
            elif sc == "G_capacidad_sweep":
                ok, dur, msg = _run_timed("G_capacidad_sweep", cmd_capacidad_sweep)
                summarize("G_capacidad_sweep", ok, dur, msg)
            else:
                summarize(sc, False, 0.0, "escenario_desconocido")

    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    print(f"Resumen global: {GLOBAL_SUMMARY_CSV}")

    if not solo or solo.startswith("G_"):
        try:
            plot_all_g_main()
        except Exception as e:
            print(f"[plots] Error al generar graficas: {e}")


if __name__ == "__main__":
    main()
