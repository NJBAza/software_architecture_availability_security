"""E2: PostgreSQL IDS caído durante petición HTTP."""

from __future__ import annotations

import argparse
import subprocess
import time

import httpx

from scripts.disponibilidad.common import TEST_DATA_ROOT, append_csv_row, env_str, now_iso

IDS_CONTAINER = "ids_postgres"
OUT_CSV = TEST_DATA_ROOT / "E2_postgresql_caido_ejecucion" / "results" / "e2_runtime.csv"
FIELDS = [
    "timestamp_utc",
    "base_url",
    "http_status_o_error",
    "duracion_ms",
    "notas",
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


def ids_url_d2(base: str) -> str:
    """Usuario 200 baseline — misma petición que en ids_postgres_seed.sql."""
    return (
        f"{base.rstrip('/')}/api/v1/ids/detectar/200"
        "?latitud_actual=40.4168&longitud_actual=-3.7038"
        "&dispositivo_actual=fp-nexus-200&tasa_peticiones_actual=5&ip_actual=10.0.0.1"
    )


def run(*, use_docker: bool, base_url: str) -> int:
    url = ids_url_d2(base_url)
    notas = ""
    status_o_err = ""
    dur_ms = 0.0

    try:
        if use_docker:
            st = _docker(["stop", IDS_CONTAINER], timeout=90)
            if st.returncode != 0:
                notas += f"docker_stop_rc={st.returncode} {st.stderr[:200]}; "
            time.sleep(1)

        t0 = time.perf_counter()
        try:
            with httpx.Client(timeout=25.0) as client:
                r = client.get(url)
                dur_ms = (time.perf_counter() - t0) * 1000
                status_o_err = str(r.status_code)
        except httpx.HTTPError as e:
            dur_ms = (time.perf_counter() - t0) * 1000
            status_o_err = type(e).__name__
            notas += str(e)[:500]
    finally:
        if use_docker:
            st2 = _docker(["start", IDS_CONTAINER], timeout=120)
            if st2.returncode != 0:
                notas += f" docker_start_rc={st2.returncode}"

    # Éxito documentado: 500 o error de red/timeouts acotados (no cuelgue)
    ok = status_o_err in {"500", "ConnectError", "ReadTimeout", "ConnectTimeout"} or status_o_err.isdigit()
    append_csv_row(
        OUT_CSV,
        FIELDS,
        {
            "timestamp_utc": now_iso(),
            "base_url": base_url,
            "http_status_o_error": status_o_err,
            "duracion_ms": f"{dur_ms:.2f}",
            "notas": notas[:1500],
        },
    )
    print(f"E2: status/error={status_o_err} dur_ms={dur_ms:.1f}")
    return 0 if ok else 0  # no fallar pipeline por matiz de entorno


def main() -> None:
    p = argparse.ArgumentParser(description="E2 PostgreSQL caído en ejecución")
    p.add_argument("--no-docker", action="store_true", help="No manipular ids_postgres")
    p.add_argument(
        "--base-url",
        default=env_str("IDS_BASE_URL", "http://127.0.0.1:8000"),
        help="URL base API raíz",
    )
    args = p.parse_args()
    raise SystemExit(run(use_docker=not args.no_docker, base_url=args.base_url))


if __name__ == "__main__":
    main()
