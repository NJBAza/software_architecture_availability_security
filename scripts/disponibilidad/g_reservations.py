"""Escenarios G: concurrencia y capacidad sobre reservations_service."""

from __future__ import annotations

import argparse
import asyncio
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from scripts.disponibilidad.common import TEST_DATA_ROOT, append_csv_row, ensure_csv_header, env_int, env_str, now_iso

RSV_DEFAULT = "http://localhost:8002"


def _base() -> str:
    return env_str("RSV_BASE_URL", RSV_DEFAULT).rstrip("/")


def _post_reserve(client: httpx.Client, stock_id: str, quantity: int, order_id: str | None = None) -> tuple[int, float, str]:
    oid = order_id or f"ORD-TST-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()
    try:
        r = client.post(
            f"{_base()}/reservations/reserve",
            json={"order_id": oid, "stock_id": stock_id, "quantity": quantity},
            timeout=60.0,
        )
        ms = (time.perf_counter() - t0) * 1000
        body = ""
        try:
            body = r.text[:500]
        except Exception:
            body = ""
        return r.status_code, ms, body
    except httpx.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000
        return -1, ms, type(e).__name__


def _get_stock(client: httpx.Client, stock_id: str) -> dict[str, Any] | None:
    try:
        r = client.get(f"{_base()}/stock/{stock_id}", timeout=30.0)
        if r.status_code == 200:
            return r.json()
    except httpx.HTTPError:
        return None
    return None


def cmd_mismo_stock() -> None:
    out = TEST_DATA_ROOT / "G_concurrencia_mismo_stock" / "results" / "g_concurrencia_mismo_stock.csv"
    detail_out = TEST_DATA_ROOT / "G_concurrencia_mismo_stock" / "results" / "g_mismo_detalle.csv"
    fields = ["timestamp_utc", "order_id", "http_status", "duracion_ms", "body_snippet"]
    detail_fields = ["timestamp_utc", "escenario", "order_id", "stock_id", "http_status", "duracion_ms"]
    ensure_csv_header(detail_out, detail_fields)
    stock_id = env_str("G_STOCK_ID", "STK00001")
    qty = env_int("G_RESERVE_QTY", 1)

    def task() -> tuple[str, int, float, str]:
        oid = f"ORD-TST-{uuid.uuid4().hex[:12]}"
        with httpx.Client() as c:
            code, ms, body = _post_reserve(c, stock_id, qty, oid)
        return oid, code, ms, body

    print(f"[G_mismo] 2 solicitudes concurrentes al producto {stock_id}")
    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(task), ex.submit(task)]
        results = [f.result() for f in futs]

    ts = now_iso()
    for oid, code, ms, body in results:
        append_csv_row(
            out,
            fields,
            {
                "timestamp_utc": ts,
                "order_id": oid,
                "http_status": str(code),
                "duracion_ms": f"{ms:.2f}",
                "body_snippet": body.replace("\n", " ")[:400],
            },
        )
        append_csv_row(
            detail_out,
            detail_fields,
            {
                "timestamp_utc": ts,
                "escenario": "g_mismo_stock",
                "order_id": oid,
                "stock_id": stock_id,
                "http_status": str(code),
                "duracion_ms": f"{ms:.2f}",
            },
        )
    print(f"G mismo-stock: {results}")
    print(f"CSV detalle: {detail_out}")


def cmd_con_carga() -> None:
    out = TEST_DATA_ROOT / "G_concurrencia_con_carga_base" / "results" / "g_concurrencia_con_carga.csv"
    fields = [
        "timestamp_utc",
        "fase",
        "metrica",
        "valor",
        "detalle",
    ]
    usuarios = env_int("G_CARGA_USUARIOS", 200)
    iteraciones = env_int("G_CARGA_ITERACIONES", 3)
    stock_id = env_str("G_STOCK_ID", "STK00001")
    qty = env_int("G_RESERVE_QTY", 1)

    async def run_all() -> None:
        ok = err = 0

        async def one_health() -> None:
            nonlocal ok, err
            try:
                async with httpx.AsyncClient() as c:
                    r = await c.get(f"{_base()}/health", timeout=10.0)
                    if r.status_code == 200:
                        ok += 1
                    else:
                        err += 1
            except httpx.HTTPError:
                err += 1

        total_health = usuarios * iteraciones
        health_task = asyncio.gather(*(one_health() for _ in range(total_health)))

        def sync_reserve() -> tuple[str, int, float, str]:
            oid = f"ORD-TST-{uuid.uuid4().hex[:12]}"
            with httpx.Client() as c:
                code, ms, body = _post_reserve(c, stock_id, qty, oid)
            return oid, code, ms, body

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=2) as ex:
            reserves_coro = asyncio.gather(
                loop.run_in_executor(ex, sync_reserve),
                loop.run_in_executor(ex, sync_reserve),
            )
            res, _ = await asyncio.gather(reserves_coro, health_task)

        append_csv_row(
            out,
            fields,
            {
                "timestamp_utc": now_iso(),
                "fase": "carga_fondo",
                "metrica": "health_ok",
                "valor": str(ok),
                "detalle": f"peticiones_health_totales={total_health} solapadas_con_2_reservas",
            },
        )
        append_csv_row(
            out,
            fields,
            {
                "timestamp_utc": now_iso(),
                "fase": "carga_fondo",
                "metrica": "health_err",
                "valor": str(err),
                "detalle": "",
            },
        )
        for oid, code, ms, body in res:
            append_csv_row(
                out,
                fields,
                {
                    "timestamp_utc": now_iso(),
                    "fase": "reserva_conflictiva",
                    "metrica": f"http_{code}",
                    "valor": f"{ms:.2f}",
                    "detalle": f"order_id={oid} {body[:200]}",
                },
            )

    asyncio.run(run_all())
    print("G con-carga: ver CSV")


def cmd_diez_parejas() -> None:
    out = TEST_DATA_ROOT / "G_diez_parejas_diez_productos" / "results" / "g_diez_parejas.csv"
    detail_out = TEST_DATA_ROOT / "G_diez_parejas_diez_productos" / "results" / "g_diez_detalle.csv"
    fields = [
        "timestamp_utc",
        "stock_id",
        "solicitudes",
        "success",
        "errors",
        "rollback_409_count",
        "avg_ms",
        "p95_ms",
        "max_ms",
    ]
    detail_fields = ["timestamp_utc", "escenario", "solicitudes_nivel", "order_id", "stock_id", "http_status", "duracion_ms"]
    ensure_csv_header(out, fields)
    ensure_csv_header(detail_out, detail_fields)
    sid = env_str("G_STOCK_ID", "STK00001")
    qty = env_int("G_RESERVE_QTY", 1)
    levels_raw = env_str("G_DIEZ_LEVELS", "2,10,100,1000,5000,10000,20000")
    levels = [int(x.strip()) for x in levels_raw.split(",") if x.strip()]

    with httpx.Client() as client:
        row = _get_stock(client, sid)
        if not row:
            raise RuntimeError(f"stock_id_no_disponible:{sid}")

    for reqs in levels:
        latencies: list[float] = []
        detail_rows: list[tuple[str, int, float]] = []
        ok = err = conflicts = 0
        workers = min(max(1, reqs), env_int("G_SCALE_MAX_WORKERS", 2000))
        per_worker = max(1, reqs // workers)
        actual_total = workers * per_worker
        print(f"[G_diez] {actual_total} solicitudes al mismo producto {sid} (sin tráfico de fondo)")

        def one() -> tuple[str, int, float]:
            oid = f"ORD-TST-{uuid.uuid4().hex[:12]}"
            with httpx.Client() as c:
                code, ms, _ = _post_reserve(c, sid, qty, oid)
            return oid, code, ms

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(one) for _ in range(actual_total)]
            for f in futs:
                oid, code, ms = f.result()
                latencies.append(ms)
                detail_rows.append((oid, code, ms))
                if code == 200:
                    ok += 1
                else:
                    err += 1
                if code == 409:
                    conflicts += 1

        lat_sorted = sorted(latencies)
        p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if len(lat_sorted) > 1 else (lat_sorted[0] if lat_sorted else 0.0)
        avg = (sum(latencies) / len(latencies)) if latencies else 0.0
        max_ms = max(latencies) if latencies else 0.0
        ts = now_iso()
        append_csv_row(
            out,
            fields,
            {
                "timestamp_utc": ts,
                "stock_id": sid,
                "solicitudes": str(actual_total),
                "success": str(ok),
                "errors": str(err),
                "rollback_409_count": str(conflicts),
                "avg_ms": f"{avg:.2f}",
                "p95_ms": f"{p95:.2f}",
                "max_ms": f"{max_ms:.2f}",
            },
        )
        for oid, code, ms in detail_rows:
            append_csv_row(
                detail_out,
                detail_fields,
                {
                    "timestamp_utc": ts,
                    "escenario": "g_diez_mismo_producto",
                    "solicitudes_nivel": str(actual_total),
                    "order_id": oid,
                    "stock_id": sid,
                    "http_status": str(code),
                    "duracion_ms": f"{ms:.4f}",
                },
            )
    print("G diez (mismo producto): ver CSV")
    print(f"CSV detalle: {detail_out}")


def cmd_rollback_tiempo() -> None:
    out = TEST_DATA_ROOT / "G_rollback_y_tiempo" / "results" / "g_rollback_tiempo.csv"
    detail_out = TEST_DATA_ROOT / "G_rollback_y_tiempo" / "results" / "g_rollback_detalle.csv"
    fields = [
        "timestamp_utc",
        "stock_id",
        "fase",
        "qty_on_hand",
        "qty_reserved",
        "available_quantity",
        "http_status",
        "duracion_ms",
        "cumple_300ms",
    ]
    detail_fields = ["timestamp_utc", "escenario", "order_id", "stock_id", "http_status", "duracion_ms"]
    ensure_csv_header(detail_out, detail_fields)
    stock_id = env_str("G_STOCK_ID", "STK00001")
    qty = env_int("G_RESERVE_QTY", 1)

    print(f"[G_rollback] 2 solicitudes concurrentes al producto {stock_id}")
    with httpx.Client() as client:
        before = _get_stock(client, stock_id)

        def one() -> tuple[str, int, float]:
            oid = f"ORD-TST-{uuid.uuid4().hex[:12]}"
            with httpx.Client() as c:
                code, ms, _ = _post_reserve(c, stock_id, qty, oid)
            return oid, code, ms

        with ThreadPoolExecutor(max_workers=2) as ex:
            futs = [ex.submit(one), ex.submit(one)]
            outcomes = [f.result() for f in futs]

        after = _get_stock(client, stock_id)

    def snap(label: str, snap_row: dict[str, Any] | None, code: str, ms: str, ok300: str) -> None:
        append_csv_row(
            out,
            fields,
            {
                "timestamp_utc": now_iso(),
                "stock_id": stock_id,
                "fase": label,
                "qty_on_hand": str(snap_row.get("qty_on_hand", "")) if snap_row else "",
                "qty_reserved": str(snap_row.get("qty_reserved", "")) if snap_row else "",
                "available_quantity": str(snap_row.get("available_quantity", "")) if snap_row else "",
                "http_status": code,
                "duracion_ms": ms,
                "cumple_300ms": ok300,
            },
        )

    snap("antes", before, "", "", "")
    ts = now_iso()
    for oid, code, ms in outcomes:
        ok300 = "si" if code == 409 and ms < 300 else ("si" if code == 200 else "n/a")
        snap("intento", after, str(code), f"{ms:.2f}", ok300)
        append_csv_row(
            detail_out,
            detail_fields,
            {
                "timestamp_utc": ts,
                "escenario": "g_rollback_tiempo",
                "order_id": oid,
                "stock_id": stock_id,
                "http_status": str(code),
                "duracion_ms": f"{ms:.2f}",
            },
        )
    snap("despues", after, "", "", "")

    print(f"G rollback-tiempo: outcomes={[(o, c, round(m, 2)) for o, c, m in outcomes]}")
    print(f"CSV detalle: {detail_out}")


def _capacidad_once(vus: int, total_requests: int, path: str) -> dict[str, str]:
    base = _base()
    url = f"{base}{path if path.startswith('/') else '/' + path}"
    max_vus = env_int("G_CAPACIDAD_MAX_VUS", 5000)
    if vus > max_vus:
        vus = max_vus
    per_worker = max(1, total_requests // vus)
    latencies: list[float] = []
    errors = 0
    t0 = time.perf_counter()

    def worker() -> None:
        nonlocal errors
        with httpx.Client() as client:
            for _ in range(per_worker):
                t1 = time.perf_counter()
                try:
                    r = client.get(url, timeout=60.0)
                    ms = (time.perf_counter() - t1) * 1000
                    latencies.append(ms)
                    if r.status_code != 200:
                        errors += 1
                except httpx.HTTPError:
                    errors += 1

    with ThreadPoolExecutor(max_workers=vus) as ex:
        futs = [ex.submit(worker) for _ in range(vus)]
        for f in futs:
            f.result()

    total_s = time.perf_counter() - t0
    total_done = len(latencies) + errors
    rps = (len(latencies) / total_s) if total_s > 0 else 0.0
    err_pct = (errors / total_done * 100) if total_done else 0.0
    lat_sorted = sorted(latencies)
    p95 = lat_sorted[int(0.95 * (len(lat_sorted) - 1))] if len(lat_sorted) > 1 else (lat_sorted[0] if lat_sorted else 0.0)
    max_ms = lat_sorted[-1] if lat_sorted else 0.0
    avg_ms = (sum(latencies) / len(latencies)) if latencies else 0.0
    avg_ms_per_user = (avg_ms / vus) if vus > 0 else 0.0

    return {
        "timestamp_utc": now_iso(),
        "escenario": f"VUS={vus}",
        "vus": str(vus),
        "requests": str(total_done),
        "duracion_s": f"{total_s:.3f}",
        "rps": f"{rps:.2f}",
        "error_pct": f"{err_pct:.4f}",
        "p95_ms": f"{p95:.2f}",
        "avg_ms_per_user": f"{avg_ms_per_user:.6f}",
        "max_ms": f"{max_ms:.2f}",
        "url": url,
    }


def cmd_capacidad() -> None:
    out = TEST_DATA_ROOT / "G_capacidad_usuarios_concurrentes" / "results" / "g_capacidad.csv"
    fields = [
        "timestamp_utc",
        "escenario",
        "vus",
        "requests",
        "duracion_s",
        "rps",
        "error_pct",
        "p95_ms",
        "avg_ms_per_user",
        "max_ms",
        "url",
    ]
    ensure_csv_header(out, fields)
    vus = env_int("G_CAPACIDAD_VUS", 100)
    total = env_int("G_CAPACIDAD_REQUESTS", 1000)
    path = env_str("G_CAPACIDAD_URL", "/health")
    row = _capacidad_once(vus, total, path)
    append_csv_row(out, fields, row)
    print(row)


def cmd_capacidad_sweep() -> None:
    out = TEST_DATA_ROOT / "G_capacidad_usuarios_concurrentes" / "results" / "g_capacidad.csv"
    fields = [
        "timestamp_utc",
        "escenario",
        "vus",
        "requests",
        "duracion_s",
        "rps",
        "error_pct",
        "p95_ms",
        "avg_ms_per_user",
        "max_ms",
        "url",
    ]
    ensure_csv_header(out, fields)
    sweep = env_str("G_CAPACIDAD_SWEEP", "10,100,1000,100000")
    total_per = env_int("G_CAPACIDAD_REQUESTS", 500)
    path = env_str("G_CAPACIDAD_URL", "/health")
    for part in sweep.split(","):
        part = part.strip()
        if not part:
            continue
        vus = int(part)
        row = _capacidad_once(vus, total_per * max(1, vus // 10), path)
        row["escenario"] = f"sweep_{vus}"
        append_csv_row(out, fields, row)
        print(row)


def main() -> None:
    p = argparse.ArgumentParser(description="Pruebas G — reservations_service")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("mismo-stock", help="Dos reservas concurrentes mismo SKU").set_defaults(fn=cmd_mismo_stock)
    sub.add_parser("con-carga", help="Carga de health + dos reservas").set_defaults(fn=cmd_con_carga)
    sub.add_parser("diez-parejas", help="Diez productos, dos clientes por producto").set_defaults(fn=cmd_diez_parejas)
    sub.add_parser("rollback-tiempo", help="Medición 409 e integridad stock").set_defaults(fn=cmd_rollback_tiempo)
    sub.add_parser("capacidad", help="Un escenario VUS").set_defaults(fn=cmd_capacidad)
    sub.add_parser("capacidad-sweep", help="Barrido 10,100,1000,100000").set_defaults(fn=cmd_capacidad_sweep)

    args = p.parse_args()
    args.fn()


if __name__ == "__main__":
    main()
