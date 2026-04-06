"""E3: carga concurrente contra endpoint IDS usuario 200."""

from __future__ import annotations

import argparse
import asyncio
import os
import time

import httpx

from scripts.disponibilidad.common import TEST_DATA_ROOT, append_csv_row, env_int, env_str, now_iso

OUT_CSV = TEST_DATA_ROOT / "E3_carga_concurrente_ids" / "results" / "e3_carga_ids.csv"
FIELDS_SUMMARY = [
    "timestamp_utc",
    "base_url",
    "total_requests",
    "concurrency",
    "ok_count",
    "error_count",
    "error_pct",
    "duracion_total_s",
    "p50_ms",
    "p95_ms",
    "p99_ms",
]


def ids_url_d2(base: str) -> str:
    return (
        f"{base.rstrip('/')}/api/v1/ids/detectar/200"
        "?latitud_actual=40.4168&longitud_actual=-3.7038"
        "&dispositivo_actual=fp-nexus-200&tasa_peticiones_actual=5&ip_actual=10.0.0.1"
    )


async def _one(client: httpx.AsyncClient, url: str, timeout: float) -> tuple[bool, float]:
    t0 = time.perf_counter()
    try:
        r = await client.get(url, timeout=timeout)
        ok = r.status_code == 200
    except httpx.HTTPError:
        ok = False
    ms = (time.perf_counter() - t0) * 1000
    return ok, ms


async def run_load(
    base_url: str,
    total: int,
    concurrency: int,
    timeout: float,
) -> dict[str, object]:
    url = ids_url_d2(base_url)
    latencies: list[float] = []
    ok_c = 0
    err_c = 0
    t_start = time.perf_counter()

    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient() as client:

        async def bounded(i: int) -> None:
            nonlocal ok_c, err_c
            async with sem:
                ok, ms = await _one(client, url, timeout)
                latencies.append(ms)
                if ok:
                    ok_c += 1
                else:
                    err_c += 1

        await asyncio.gather(*(bounded(i) for i in range(total)))
    total_s = time.perf_counter() - t_start

    lat_sorted = sorted(latencies)
    def pct(p: float) -> float:
        if not lat_sorted:
            return 0.0
        idx = min(len(lat_sorted) - 1, int(round(p * (len(lat_sorted) - 1))))
        return lat_sorted[idx]

    err_pct = (err_c / total * 100) if total else 0.0
    return {
        "timestamp_utc": now_iso(),
        "base_url": base_url,
        "total_requests": str(total),
        "concurrency": str(concurrency),
        "ok_count": str(ok_c),
        "error_count": str(err_c),
        "error_pct": f"{err_pct:.4f}",
        "duracion_total_s": f"{total_s:.3f}",
        "p50_ms": f"{pct(0.50):.2f}",
        "p95_ms": f"{pct(0.95):.2f}",
        "p99_ms": f"{pct(0.99):.2f}",
    }


def run_e3(
    base_url: str | None = None,
    total: int | None = None,
    concurrency: int | None = None,
    timeout: float | None = None,
) -> None:
    bu = base_url if base_url is not None else env_str("IDS_BASE_URL", "http://127.0.0.1:8000")
    t = total if total is not None else env_int("E3_REQUESTS", 500)
    c = concurrency if concurrency is not None else env_int("E3_CONCURRENCY", 50)
    to = timeout if timeout is not None else float(os.environ.get("E3_TIMEOUT", "30"))
    row = asyncio.run(run_load(bu, t, c, to))
    append_csv_row(OUT_CSV, FIELDS_SUMMARY, row)
    print(
        f"E3: ok={row['ok_count']} err={row['error_count']} "
        f"p95_ms={row['p95_ms']} dur_s={row['duracion_total_s']}",
    )


def main() -> None:
    p = argparse.ArgumentParser(description="E3 carga concurrente IDS")
    p.add_argument("--base-url", default=env_str("IDS_BASE_URL", "http://127.0.0.1:8000"))
    p.add_argument("--requests", type=int, default=env_int("E3_REQUESTS", 500))
    p.add_argument("--concurrency", type=int, default=env_int("E3_CONCURRENCY", 50))
    p.add_argument("--timeout", type=float, default=float(os.environ.get("E3_TIMEOUT", "30")))
    args = p.parse_args()
    run_e3(args.base_url, args.requests, args.concurrency, args.timeout)


if __name__ == "__main__":
    main()
