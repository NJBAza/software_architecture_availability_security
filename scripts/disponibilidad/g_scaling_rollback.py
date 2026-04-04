"""Escenarios G nuevos: escalado de latencia y rollback bajo carga."""

from __future__ import annotations

import argparse
import random
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Optional

import httpx

from scripts.disponibilidad.common import TEST_DATA_ROOT, append_csv_row, ensure_csv_header, env_int, env_str, now_iso

RSV_DEFAULT = "http://localhost:8002"
DEFAULT_LEVELS = "10,100,1000,10000,100000,1000000"
# G_rollback_carga: empieza en 200 para que 1% = 2 conflictos exactos
DEFAULT_LEVELS_ROLLBACK = "200,2000,20000,200000"
DEFAULT_LEVELS_ROLLBACK_NEW = "10,100,1000,5000,10000,20000"
DEFAULT_LEVELS_LAT_STEPPED = (
    "10,100,200,300,400,500,600,700,800,900,1000,"
    "2000,3000,4000,5000,6000,7000,8000,9000,10000,"
    "11000,12000,13000,14000,15000,16000,17000,18000,19000,20000"
)
DEFAULT_LEVELS_ESTOCASTICO = "100,1000,5000,10000,50000,200000"

# Campos del CSV de resumen por nivel
RESULT_FIELDS = [
    "timestamp_utc",
    "escenario",
    "users",
    "total_requests",
    "conflict_requests",
    "success",
    "errors",
    "error_pct",
    "avg_ms",
    "p95_ms",
    "max_ms",
    "avg_ms_per_user",
    "rollback_409_count",
    "duracion_s",
    "stop_reason",
]

# Campos del CSV de detalle por solicitud individual
DETAIL_FIELDS = [
    "timestamp_utc",
    "escenario",
    "vus_nivel",
    "order_id",
    "stock_id",
    "tipo",
    "http_status",
    "duracion_ms",
    "es_409",
]

# Campos del CSV del test estocástico
ESTOCASTICO_FIELDS = [
    "timestamp_utc",
    "escenario",
    "rpm_objetivo",
    "rpm_real",
    "duracion_s",
    "success",
    "errors",
    "error_pct",
    "avg_ms",
    "p95_ms",
    "max_ms",
]


def _base() -> str:
    return env_str("RSV_BASE_URL", RSV_DEFAULT).rstrip("/")


def _levels(var_name: str, default: str) -> list[int]:
    raw = env_str(var_name, default)
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


def _pct(num: int, den: int) -> float:
    return (num / den * 100.0) if den else 0.0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    vals = sorted(values)
    if len(vals) == 1:
        return vals[0]
    return vals[int(0.95 * (len(vals) - 1))]


@dataclass
class DetailRow:
    order_id: str
    stock_id: str
    tipo: str           # "conflicto" | "normal"
    http_status: int
    duracion_ms: float
    es_409: bool


@dataclass
class RunMetrics:
    requests: int
    success: int
    errors: int
    rollback_409: int
    avg_ms: float
    p95_ms: float
    max_ms: float
    duration_s: float
    detail_rows: list[DetailRow] = field(default_factory=list)

    @property
    def error_pct(self) -> float:
        return _pct(self.errors, self.requests)


def _run_health_load(vus: int, total_requests: int) -> RunMetrics:
    """Carga usando GET /health — no consume stock."""
    latencies: list[float] = []
    ok = 0
    err = 0
    t0 = time.perf_counter()
    max_workers = env_int("G_SCALE_MAX_WORKERS", 2000)
    workers = min(max(1, vus), max_workers)
    per_worker = max(1, total_requests // workers)

    def worker() -> tuple[list[float], int, int]:
        local_lat: list[float] = []
        local_ok = 0
        local_err = 0
        for _ in range(per_worker):
            s_ok, ms, _ = _get_health()
            local_lat.append(ms)
            if s_ok:
                local_ok += 1
            else:
                local_err += 1
        return local_lat, local_ok, local_err

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for local_lat, local_ok, local_err in ex.map(lambda _: worker(), range(workers)):
            latencies.extend(local_lat)
            ok += local_ok
            err += local_err

    dur = time.perf_counter() - t0
    avg = (sum(latencies) / len(latencies)) if latencies else 0.0
    max_ms = max(latencies) if latencies else 0.0
    return RunMetrics(
        requests=ok + err,
        success=ok,
        errors=err,
        rollback_409=0,
        avg_ms=avg,
        p95_ms=_p95(latencies),
        max_ms=max_ms,
        duration_s=dur,
    )


def _run_load(
    vus: int,
    stock_plan: list[str],
    qty: int,
    hot_set: Optional[set[str]] = None,
    collect_detail: bool = False,
) -> RunMetrics:
    """
    Carga usando POST /reserve con plan de stock_ids (ya intercalado).
    Si collect_detail=True, captura una DetailRow por cada solicitud.
    hot_set: conjunto de stock_ids considerados "conflicto" para etiquetar tipo.
    """
    latencies: list[float] = []
    ok = 0
    err = 0
    rollback_409 = 0
    all_details: list[DetailRow] = []
    t0 = time.perf_counter()
    total_requests = len(stock_plan)
    if total_requests == 0:
        return RunMetrics(0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0)

    max_workers = env_int("G_SCALE_MAX_WORKERS", 2000)
    workers = min(max(1, vus), max_workers)
    per_worker = max(1, total_requests // workers)

    chunks: list[list[str]] = []
    for i in range(workers):
        start = i * per_worker
        end = start + per_worker
        chunk = stock_plan[start:end] if start < len(stock_plan) else []
        if chunk:
            chunks.append(chunk)

    def worker(chunk: list[str]) -> tuple[list[float], int, int, int, list[DetailRow]]:
        local_lat: list[float] = []
        local_ok = 0
        local_err = 0
        local_409 = 0
        local_detail: list[DetailRow] = []
        for sid in chunk:
            s_ok, ms, status, oid = _post_reserve_detail(sid, qty)
            local_lat.append(ms)
            if s_ok:
                local_ok += 1
            else:
                local_err += 1
            if status == 409:
                local_409 += 1
            if collect_detail:
                tipo = "conflicto" if (hot_set and sid in hot_set) else "normal"
                local_detail.append(DetailRow(
                    order_id=oid,
                    stock_id=sid,
                    tipo=tipo,
                    http_status=status,
                    duracion_ms=round(ms, 4),
                    es_409=(status == 409),
                ))
        return local_lat, local_ok, local_err, local_409, local_detail

    with ThreadPoolExecutor(max_workers=len(chunks)) as ex:
        for local_lat, local_ok, local_err, local_409, local_detail in ex.map(worker, chunks):
            latencies.extend(local_lat)
            ok += local_ok
            err += local_err
            rollback_409 += local_409
            all_details.extend(local_detail)

    dur = time.perf_counter() - t0
    avg = (sum(latencies) / len(latencies)) if latencies else 0.0
    max_ms = max(latencies) if latencies else 0.0
    return RunMetrics(
        requests=ok + err,
        success=ok,
        errors=err,
        rollback_409=rollback_409,
        avg_ms=avg,
        p95_ms=_p95(latencies),
        max_ms=max_ms,
        duration_s=dur,
        detail_rows=all_details,
    )


def _build_interleaved_plan(hot_stock: str, normal_stock: str, conflict_n: int, normal_n: int) -> list[str]:
    """Distribuye hot_stock uniformemente en el plan para evitar que todos queden en los primeros workers."""
    total = conflict_n + normal_n
    if total == 0:
        return []
    plan = [normal_stock] * total
    if conflict_n == 0:
        return plan
    step = max(1, total // conflict_n)
    placed = 0
    for i in range(0, total, step):
        if placed >= conflict_n:
            break
        plan[i] = hot_stock
        placed += 1
    for i in range(total):
        if placed >= conflict_n:
            break
        if plan[i] == normal_stock:
            plan[i] = hot_stock
            placed += 1
    return plan


def _write_row(
    out_csv,
    escenario: str,
    users: int,
    total_requests: int,
    conflict_requests: int,
    metrics: RunMetrics,
    stop_reason: str,
) -> None:
    rollback_409 = min(metrics.rollback_409, max(0, conflict_requests)) if conflict_requests > 0 else metrics.rollback_409
    avg_per_user = (metrics.avg_ms / users) if users > 0 else 0.0
    append_csv_row(
        out_csv,
        RESULT_FIELDS,
        {
            "timestamp_utc": now_iso(),
            "escenario": escenario,
            "users": str(users),
            "total_requests": str(total_requests),
            "conflict_requests": str(conflict_requests),
            "success": str(metrics.success),
            "errors": str(metrics.errors),
            "error_pct": f"{metrics.error_pct:.4f}",
            "avg_ms": f"{metrics.avg_ms:.2f}",
            "p95_ms": f"{metrics.p95_ms:.2f}",
            "max_ms": f"{metrics.max_ms:.2f}",
            "avg_ms_per_user": f"{avg_per_user:.6f}",
            "rollback_409_count": str(rollback_409),
            "duracion_s": f"{metrics.duration_s:.3f}",
            "stop_reason": stop_reason,
        },
    )


def _write_detail_rows(detail_csv, escenario: str, vus_nivel: int, rows: list[DetailRow]) -> None:
    """Escribe una fila por solicitud individual al CSV de detalle."""
    ts = now_iso()
    for r in rows:
        append_csv_row(
            detail_csv,
            DETAIL_FIELDS,
            {
                "timestamp_utc": ts,
                "escenario": escenario,
                "vus_nivel": str(vus_nivel),
                "order_id": r.order_id,
                "stock_id": r.stock_id,
                "tipo": r.tipo,
                "http_status": str(r.http_status),
                "duracion_ms": f"{r.duracion_ms:.4f}",
                "es_409": str(r.es_409),
            },
        )


def _ensure_csv(path, fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    expected_header = ",".join(fields)
    if path.exists() and path.stat().st_size > 0:
        with open(path, encoding="utf-8") as f:
            existing = f.readline().strip()
        if existing != expected_header:
            path.write_text(expected_header + "\n", encoding="utf-8")
        return
    path.write_text(expected_header + "\n", encoding="utf-8")


def _get_health() -> tuple[bool, float, int]:
    url = f"{_base()}/health"
    t0 = time.perf_counter()
    try:
        with httpx.Client() as c:
            r = c.get(url, timeout=60.0)
        ms = (time.perf_counter() - t0) * 1000
        return r.status_code == 200, ms, r.status_code
    except httpx.HTTPError:
        ms = (time.perf_counter() - t0) * 1000
        return False, ms, -1


def _post_reserve_detail(stock_id: str, qty: int) -> tuple[bool, float, int, str]:
    """Igual a _post_reserve pero también devuelve el order_id generado."""
    t0 = time.perf_counter()
    order_id = f"ORD-TST-{uuid.uuid4().hex[:12]}"
    try:
        with httpx.Client() as c:
            r = c.post(
                f"{_base()}/reservations/reserve",
                json={"order_id": order_id, "stock_id": stock_id, "quantity": qty},
                timeout=60.0,
            )
        ms = (time.perf_counter() - t0) * 1000
        return r.status_code == 200, ms, r.status_code, order_id
    except httpx.HTTPError:
        ms = (time.perf_counter() - t0) * 1000
        return False, ms, -1, order_id


def _post_reserve(stock_id: str, qty: int) -> tuple[bool, float, int]:
    ok, ms, status, _ = _post_reserve_detail(stock_id, qty)
    return ok, ms, status


def _validate_stock_ids(stock_ids: list[str]) -> None:
    with httpx.Client() as c:
        for sid in stock_ids:
            r = c.get(f"{_base()}/stock/{sid}", timeout=30.0)
            if r.status_code != 200:
                raise RuntimeError(f"stock_id_no_disponible:{sid}")


# ---------------------------------------------------------------------------
# Escenario: G_escalado_tiempo_respuesta — usa /health, no consume stock
# ---------------------------------------------------------------------------

def cmd_test1_escalado() -> None:
    out = TEST_DATA_ROOT / "G_escalado_tiempo_respuesta_usuarios" / "results" / "escalado_respuesta.csv"
    _ensure_csv(out, RESULT_FIELDS)
    levels = _levels("G_SCALE_LEVELS", DEFAULT_LEVELS)
    stop_ms = env_int("G_STOP_MS", 5000)

    for vus in levels:
        total = vus
        print(f"[G_escalado] vus={vus} → {total} solicitudes GET /health (sin consumo de stock)")
        metrics = _run_health_load(vus, total)
        stop_reason = ""
        if metrics.avg_ms >= float(stop_ms):
            stop_reason = f"avg_ms_ge_{stop_ms}"
        elif metrics.errors > 0 and metrics.success == 0:
            stop_reason = "errors_detected"
        _write_row(out, "test1_escalado", vus, total, 0, metrics, stop_reason)
        print({"test": "test1_escalado", "vus": vus, "avg_ms": round(metrics.avg_ms, 2), "error_pct": round(metrics.error_pct, 2)})
        if stop_reason:
            print(f"  -> Detenido: {stop_reason}")
            break
    print(f"CSV generado/actualizado: {out}")


# ---------------------------------------------------------------------------
# Escenario: G_rollback_carga — 1% conflicto, niveles 200..2000000
# ---------------------------------------------------------------------------

def cmd_rollback_carga_unificado() -> None:
    out = TEST_DATA_ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_10pct_parejas.csv"
    detail_out = TEST_DATA_ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_detalle.csv"
    _ensure_csv(out, RESULT_FIELDS)
    _ensure_csv(detail_out, DETAIL_FIELDS)
    levels = _levels("G_ROLLBACK_LEVELS", DEFAULT_LEVELS_ROLLBACK)
    hot_stock = env_str("G_HOT_STOCK_ID", "STK00001")
    normal_stock = env_str("G_NORMAL_STOCK_ID", "STK00020")
    qty = env_int("G_RESERVE_QTY", 1)
    conflict_pct = 0.01   # 1% de conflicto
    _validate_stock_ids([hot_stock, normal_stock])

    for vus in levels:
        total = vus
        conflict_n = max(2, int(total * conflict_pct))
        if conflict_n % 2 == 1:
            conflict_n += 1
        normal_n = max(0, total - conflict_n)
        plan = _build_interleaved_plan(hot_stock, normal_stock, conflict_n, normal_n)
        random.shuffle(plan)
        print(
            f"[G_rollback_carga] vus={vus} → {total} solicitudes, "
            f"{conflict_n} conflictos a {hot_stock} (1%), {normal_n} normales a {normal_stock}"
        )
        metrics = _run_load(vus, plan, qty, hot_set={hot_stock}, collect_detail=True)
        reported_409 = min(metrics.rollback_409, conflict_n)
        stop_reason = "errors_detected" if metrics.errors > 0 and metrics.rollback_409 == 0 else ""
        _write_row(out, "g_rollback_carga", vus, total, conflict_n, metrics, stop_reason)
        _write_detail_rows(detail_out, "g_rollback_carga", vus, metrics.detail_rows)
        print({"test": "g_rollback_carga", "vus": vus, "error_pct": round(metrics.error_pct, 2), "rollback_409": reported_409})
        if stop_reason:
            break
    print(f"CSV resumen: {out}")
    print(f"CSV detalle: {detail_out}")


# ---------------------------------------------------------------------------
# Escenario: G_rollback_carga_10pct_parejas — 10% en parejas por producto
# ---------------------------------------------------------------------------

def cmd_test2_2_rollback_10pct() -> None:
    out = TEST_DATA_ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_10pct_parejas.csv"
    detail_out = TEST_DATA_ROOT / "G_rollback_carga_conflicto_10pct_parejas" / "results" / "rollback_10pct_detalle.csv"
    _ensure_csv(out, RESULT_FIELDS)
    _ensure_csv(detail_out, DETAIL_FIELDS)
    levels = _levels("G_ROLLBACK_LEVELS", DEFAULT_LEVELS_ROLLBACK)
    qty = env_int("G_RESERVE_QTY", 1)
    conflict_pct = 0.10
    pair_stocks = [
        s.strip()
        for s in env_str(
            "G_PAIR_STOCK_IDS",
            "STK00001,STK00002,STK00003,STK00004,STK00005,STK00006,STK00007,STK00008,STK00009,STK00010",
        ).split(",")
        if s.strip()
    ]
    normal_stock = env_str("G_NORMAL_STOCK_ID", "STK00020")
    _validate_stock_ids([normal_stock, *pair_stocks[:3]])

    for vus in levels:
        total = vus
        conflict_n = max(2, int(total * conflict_pct))
        if conflict_n % 2 == 1:
            conflict_n += 1
        normal_n = max(0, total - conflict_n)

        sequence: list[str] = []
        for i in range(conflict_n // 2):
            sid = pair_stocks[i % len(pair_stocks)]
            sequence.append(sid)
            sequence.append(sid)
        sequence.extend([normal_stock] * normal_n)
        random.shuffle(sequence)

        pairs_used = conflict_n // 2
        print(
            f"[G_rollback_10pct_parejas] vus={vus} → {total} solicitudes, "
            f"{conflict_n} conflictos en {pairs_used} parejas ({len(pair_stocks)} productos), "
            f"{normal_n} normales a {normal_stock}"
        )
        metrics = _run_load(vus, sequence, qty, hot_set=set(pair_stocks), collect_detail=True)
        reported_409 = min(metrics.rollback_409, conflict_n)
        stop_reason = "errors_detected" if metrics.errors > 0 and metrics.rollback_409 == 0 else ""
        _write_row(out, "test2_2_rollback_10pct", vus, total, conflict_n, metrics, stop_reason)
        _write_detail_rows(detail_out, "test2_2_rollback_10pct", vus, metrics.detail_rows)
        print({"test": "test2_2", "vus": vus, "error_pct": round(metrics.error_pct, 2), "rollback_409": reported_409})
        if stop_reason:
            break
    print(f"CSV resumen: {out}")
    print(f"CSV detalle: {detail_out}")


# ---------------------------------------------------------------------------
# Escenario: G_rollback_carga_1pct — 1% conflicto con detalle por solicitud
# ---------------------------------------------------------------------------

def cmd_test_rollback_1pct() -> None:
    out = TEST_DATA_ROOT / "G_rollback_carga_conflicto_1pct" / "results" / "rollback_1pct.csv"
    detail_out = TEST_DATA_ROOT / "G_rollback_carga_conflicto_1pct" / "results" / "rollback_1pct_detalle.csv"
    _ensure_csv(out, RESULT_FIELDS)
    _ensure_csv(detail_out, DETAIL_FIELDS)
    levels = _levels("G_ROLLBACK_LEVELS_NEW", DEFAULT_LEVELS_ROLLBACK_NEW)
    hot_stock = env_str("G_HOT_STOCK_ID", "STK00001")
    normal_stock = env_str("G_NORMAL_STOCK_ID", "STK00020")
    qty = env_int("G_RESERVE_QTY", 1)
    conflict_pct = 0.01
    _validate_stock_ids([hot_stock, normal_stock])

    for vus in levels:
        total = vus
        conflict_n = max(1, int(total * conflict_pct))
        normal_n = max(0, total - conflict_n)
        plan = _build_interleaved_plan(hot_stock, normal_stock, conflict_n, normal_n)
        random.shuffle(plan)
        print(
            f"[G_rollback_1pct] vus={vus} → {total} solicitudes, "
            f"{conflict_n} conflictos a {hot_stock} (~1%), {normal_n} normales a {normal_stock}"
        )
        metrics = _run_load(vus, plan, qty, hot_set={hot_stock}, collect_detail=True)
        reported_409 = min(metrics.rollback_409, conflict_n)
        _write_row(out, "test_rollback_1pct", vus, total, conflict_n, metrics, "")
        _write_detail_rows(detail_out, "test_rollback_1pct", vus, metrics.detail_rows)
        print({"test": "rollback_1pct", "vus": vus, "error_pct": round(metrics.error_pct, 2), "rollback_409": reported_409})
    print(f"CSV resumen: {out}")
    print(f"CSV detalle: {detail_out}")


# ---------------------------------------------------------------------------
# Escenario: G_latencia_escalonada — usa /health, no consume stock
# ---------------------------------------------------------------------------

def cmd_test_latencia_escalonada() -> None:
    out = TEST_DATA_ROOT / "G_latencia_escalonada_usuarios" / "results" / "latencia_escalonada.csv"
    _ensure_csv(out, RESULT_FIELDS)
    levels = _levels("G_LAT_STEPPED_LEVELS", DEFAULT_LEVELS_LAT_STEPPED)

    for vus in levels:
        total = vus
        print(f"[G_latencia_escalonada] vus={vus} → {total} solicitudes GET /health")
        metrics = _run_health_load(vus, total)
        _write_row(out, "test_latencia_escalonada", vus, total, 0, metrics, "")
        print({"test": "latencia_escalonada", "vus": vus, "avg_ms": round(metrics.avg_ms, 2), "p95_ms": round(metrics.p95_ms, 2)})
    print(f"CSV generado/actualizado: {out}")


# ---------------------------------------------------------------------------
# Escenario: G_estocastico — tasa de llegada (usuarios/minuto) durante 60s
# ---------------------------------------------------------------------------

def cmd_test_estocastico() -> None:
    """
    Simula llegada estocástica de usuarios a distintas tasas (rpm).
    Cada nivel dura exactamente 60 segundos. Los requests se lanzan a la tasa
    indicada usando intervalos uniformes (aproximación determinista de Poisson).
    Se usa GET /health para no consumir stock.
    """
    out = TEST_DATA_ROOT / "G_estocastico_llegada_usuarios" / "results" / "estocastico.csv"
    _ensure_csv(out, ESTOCASTICO_FIELDS)
    levels = _levels("G_ESTOCASTICO_LEVELS", DEFAULT_LEVELS_ESTOCASTICO)
    window_s = float(env_int("G_ESTOCASTICO_WINDOW_S", 60))

    for rpm in levels:
        intervalo_s = window_s / rpm          # tiempo entre requests
        max_concurrent = min(rpm, env_int("G_SCALE_MAX_WORKERS", 2000))
        latencies: list[float] = []
        ok = 0
        err = 0
        t_start = time.perf_counter()
        launched = 0
        futures = []
        print(f"[G_estocastico] rpm={rpm} → 1 solicitud cada {intervalo_s*1000:.2f}ms durante {int(window_s)}s")

        with ThreadPoolExecutor(max_workers=max_concurrent) as ex:
            next_launch = t_start
            while True:
                now = time.perf_counter()
                elapsed = now - t_start
                if elapsed >= window_s:
                    break
                if now >= next_launch:
                    futures.append(ex.submit(_get_health))
                    launched += 1
                    next_launch += intervalo_s
                else:
                    sleep_time = next_launch - now
                    time.sleep(min(sleep_time, 0.001))  # granularidad 1ms

            # Recoger resultados de futures completados
            for f in futures:
                try:
                    s_ok, ms, _ = f.result(timeout=10.0)
                    latencies.append(ms)
                    if s_ok:
                        ok += 1
                    else:
                        err += 1
                except Exception:
                    err += 1

        dur = time.perf_counter() - t_start
        rpm_real = int((ok + err) / dur * 60) if dur > 0 else 0
        avg = (sum(latencies) / len(latencies)) if latencies else 0.0
        max_ms = max(latencies) if latencies else 0.0
        total_done = ok + err
        error_pct = _pct(err, total_done)

        append_csv_row(
            out,
            ESTOCASTICO_FIELDS,
            {
                "timestamp_utc": now_iso(),
                "escenario": "g_estocastico",
                "rpm_objetivo": str(rpm),
                "rpm_real": str(rpm_real),
                "duracion_s": f"{dur:.3f}",
                "success": str(ok),
                "errors": str(err),
                "error_pct": f"{error_pct:.4f}",
                "avg_ms": f"{avg:.2f}",
                "p95_ms": f"{_p95(latencies):.2f}",
                "max_ms": f"{max_ms:.2f}",
            },
        )
        print({
            "test": "g_estocastico",
            "rpm_objetivo": rpm,
            "rpm_real": rpm_real,
            "success": ok,
            "error_pct": round(error_pct, 2),
            "avg_ms": round(avg, 2),
        })

    print(f"CSV generado/actualizado: {out}")


def main() -> None:
    p = argparse.ArgumentParser(description="Nuevos escenarios G de escalado y rollback")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("test1-escalado", help="Escalar usuarios hasta 5s o error").set_defaults(fn=cmd_test1_escalado)
    sub.add_parser("rollback-carga", help="Rollback 1% conflicto con detalle por solicitud").set_defaults(fn=cmd_rollback_carga_unificado)
    sub.add_parser("test2-2-rollback-10pct", help="Rollback bajo carga 10% parejas").set_defaults(fn=cmd_test2_2_rollback_10pct)
    sub.add_parser("test-rollback-1pct", help="Rollback bajo carga con 1% conflicto + detalle").set_defaults(fn=cmd_test_rollback_1pct)
    sub.add_parser("test-latencia-escalonada", help="Latencia por usuarios en escalones").set_defaults(fn=cmd_test_latencia_escalonada)
    sub.add_parser("test-estocastico", help="Tasa de llegada 100..200000 rpm durante 60s").set_defaults(fn=cmd_test_estocastico)

    args = p.parse_args()
    args.fn()


if __name__ == "__main__":
    main()
