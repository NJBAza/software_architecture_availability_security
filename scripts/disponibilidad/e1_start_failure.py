"""E1: fallo al importar IDS cuando PostgreSQL no está disponible."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from scripts.disponibilidad.common import (
    REPO_ROOT,
    TEST_DATA_ROOT,
    append_csv_row,
    now_iso,
)

IDS_CONTAINER = "ids_postgres"
OUT_CSV = TEST_DATA_ROOT / "E1_postgresql_caido_arranque" / "results" / "e1_arranque.csv"
FIELDS = [
    "timestamp_utc",
    "postgres_detenido",
    "import_exit_code",
    "exito_documentado",
    "stderr_snippet",
]


def _docker(args: list[str], timeout: float = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )


def run(*, use_docker: bool) -> int:
    postgres_stopped = False
    stderr_snippet = ""
    code = 1

    try:
        if use_docker:
            st = _docker(["stop", IDS_CONTAINER], timeout=60)
            postgres_stopped = st.returncode == 0

        env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
        proc = subprocess.run(
            [sys.executable, "-c", "import apps.services.IDS"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=45,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
        code = proc.returncode
        stderr_snippet = (proc.stderr or proc.stdout or "")[:2000]
    except subprocess.TimeoutExpired:
        stderr_snippet = "timeout_import"
        code = 124
    finally:
        if use_docker and postgres_stopped:
            _docker(["start", IDS_CONTAINER], timeout=120)

    # Documented success: import must fail when PG is down
    exito = code != 0
    append_csv_row(
        OUT_CSV,
        FIELDS,
        {
            "timestamp_utc": now_iso(),
            "postgres_detenido": str(postgres_stopped),
            "import_exit_code": str(code),
            "exito_documentado": "si" if exito else "no",
            "stderr_snippet": stderr_snippet.replace("\n", " ")[:1500],
        },
    )
    print(f"E1: import_exit_code={code} exito_documentado={'si' if exito else 'no'}")
    return 0 if exito else 1


def main() -> None:
    p = argparse.ArgumentParser(description="E1 PostgreSQL caído al arranque")
    p.add_argument(
        "--no-docker",
        action="store_true",
        help="No detener ids_postgres; asume PG ya inaccesible en :5432",
    )
    args = p.parse_args()
    raise SystemExit(run(use_docker=not args.no_docker))


if __name__ == "__main__":
    main()
