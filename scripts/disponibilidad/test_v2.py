"""Test suite v2: concurrencia, disponibilidad (rollback parejas) y seguridad IDS."""

from __future__ import annotations

import random
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import httpx
import psycopg2

from scripts.disponibilidad.common import REPO_ROOT, append_csv_row, ensure_csv_header, env_int, env_str, now_iso

V2_ROOT = REPO_ROOT / "registers" / "data" / "test_v2"
RSV_BASE = "http://localhost:8002"
IDS_BASE = "http://127.0.0.1:8000"

CONCURRENCIA_LEVELS = [10, 100, 1000, 5000, 10000, 50000, 100000]
ROLLBACK_LEVELS = [200, 2000, 20000, 200000]
#SECURITY_LEVELS = [10, 100, 1000, 10000, 20000, 100000]
SECURITY_LEVELS = [10, 100, 1000, 10000]

RESUMEN_FIELDS = ["timestamp_utc", "escenario", "nivel", "total_solicitudes", "success", "errors", "error_pct", "avg_ms", "p95_ms", "max_ms", "duracion_s"]
DETALLE_FIELDS = ["timestamp_utc", "escenario", "nivel", "order_id", "stock_id", "tipo", "pareja_id", "http_status", "duracion_ms"]
DOS_CLIENTES_FIELDS = ["timestamp_utc", "escenario", "order_id", "stock_id", "http_status", "duracion_ns", "es_rollback_exitoso"]
ROLLBACK_RESUMEN_FIELDS = ["timestamp_utc", "escenario", "nivel", "total_solicitudes", "parejas_conflicto", "solicitudes_normales", "rollback_exitosos", "rollback_fallidos", "avg_ms", "p95_ms", "max_ms", "duracion_s"]
ROLLBACK_DETALLE_FIELDS = ["timestamp_utc", "escenario", "nivel", "order_id", "stock_id", "tipo", "pareja_id", "http_status", "duracion_ms"]
SEC_RESUMEN_FIELDS = ["timestamp_utc", "escenario", "condiciones", "nivel", "total", "detecciones_correctas", "deteccion_correcta_pct", "falsos_positivos", "avg_ms", "p95_ms", "max_ms", "en_menos_300ms", "en_menos_300ms_pct"]
SEC_DETALLE_FIELDS = [
    "timestamp_utc", "escenario", "condiciones", "nivel", "stock_id_referencia",
    "id_usuario", "tipo_usuario", "http_status", "es_fraude_obtenido", "riesgo", "duracion_ms", "en_menos_300ms",
]


def _rsv_base() -> str:
    return env_str("RSV_BASE_URL", RSV_BASE).rstrip("/")


def _ids_base() -> str:
    return env_str("IDS_BASE_URL", IDS_BASE).rstrip("/")


def _ids_db_params() -> dict:
    return {
        "dbname": env_str("IDS_DB_NAME", "postgres"),
        "user": env_str("IDS_DB_USER", "postgres"),
        "password": env_str("IDS_DB_PASSWORD", "1234"),
        "host": env_str("IDS_DB_HOST", "localhost"),
        "port": env_str("IDS_DB_PORT", "5432"),
    }


def _rsv_db_params() -> dict:
    return {
        "dbname": env_str("V2_RSV_DB_NAME", "reservations_db"),
        "user": env_str("V2_RSV_DB_USER", "root"),
        "password": env_str("V2_RSV_DB_PASSWORD", "root"),
        "host": env_str("V2_RSV_DB_HOST", "localhost"),
        "port": env_str("V2_RSV_DB_PORT", "5434"),
    }


def _sec_stock_ref() -> str:
    return env_str("V2_IDS_STOCK_REF", env_str("V2_CONFLICT_STOCK", "STK00001"))


def _ensure_single_unit_available(stock_ids: list[str]) -> None:
    """Deja qty_on_hand - qty_reserved = 1 para cada stock_id (conflicto 200+409 en reservas concurrentes)."""
    ids_unique = list(dict.fromkeys(stock_ids))
    if not ids_unique:
        return
    p = _rsv_db_params()
    try:
        conn = psycopg2.connect(**p)
    except psycopg2.OperationalError as e:
        raise RuntimeError(
            f"No se pudo conectar a PostgreSQL de reservas ({p['host']}:{p['port']}, db={p['dbname']}): {e}\n"
            "Desde la raiz del repo: cd registers && docker compose up -d\n"
            "(reservations_db expone el puerto 5434 en el host por defecto.)"
        ) from e
    try:
        cur = conn.cursor()
        for sid in ids_unique:
            cur.execute(
                """
                UPDATE warehouse_stock
                SET qty_on_hand = GREATEST(qty_on_hand, 1),
                    qty_reserved = GREATEST(qty_on_hand, 1) - 1
                WHERE stock_id = %s
                """,
                (sid,),
            )
            if cur.rowcount == 0:
                raise RuntimeError(
                    f"warehouse_stock no tiene fila para stock_id={sid!r}. "
                    "Cargue datos en reservations_db (docker compose en registers/)."
                )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def _p95(vals: list[float]) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[int(0.95 * (len(s) - 1))] if len(s) > 1 else s[0]


def _post_reserve(stock_id: str, qty: int = 1) -> tuple[str, int, float]:
    oid = f"ORD-V2-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter()
    try:
        with httpx.Client() as c:
            r = c.post(f"{_rsv_base()}/reservations/reserve",
                       json={"order_id": oid, "stock_id": stock_id, "quantity": qty}, timeout=60.0)
        ms = (time.perf_counter() - t0) * 1000
        return oid, r.status_code, ms
    except httpx.HTTPError:
        ms = (time.perf_counter() - t0) * 1000
        return oid, -1, ms


def _post_reserve_ns(stock_id: str, qty: int = 1) -> tuple[str, int, int]:
    """Reserve with nanosecond timing."""
    oid = f"ORD-V2-{uuid.uuid4().hex[:12]}"
    t0 = time.perf_counter_ns()
    try:
        with httpx.Client() as c:
            r = c.post(f"{_rsv_base()}/reservations/reserve",
                       json={"order_id": oid, "stock_id": stock_id, "quantity": qty}, timeout=60.0)
        ns = time.perf_counter_ns() - t0
        return oid, r.status_code, ns
    except httpx.HTTPError:
        ns = time.perf_counter_ns() - t0
        return oid, -1, ns


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 1 — Concurrencia sin conflictos
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_concurrencia_sin_conflicto() -> None:
    out_resumen = V2_ROOT / "concurrencia_sin_conflicto" / "results" / "resumen.csv"
    out_detalle = V2_ROOT / "concurrencia_sin_conflicto" / "results" / "detalle.csv"
    ensure_csv_header(out_resumen, RESUMEN_FIELDS)
    ensure_csv_header(out_detalle, DETALLE_FIELDS)
    max_stock = env_int("V2_MAX_STOCK_ID", 5000)

    for nivel in CONCURRENCIA_LEVELS:
        plan = [f"STK{((i % max_stock) + 1):05d}" for i in range(nivel)]
        random.shuffle(plan)
        workers = min(nivel, env_int("V2_MAX_WORKERS", 2000))
        per_worker = max(1, nivel // workers)

        print(f"\n[Concurrencia] {nivel} solicitudes sin conflicto (rotando entre {max_stock} productos)")
        chunks = [plan[i * per_worker:(i + 1) * per_worker] for i in range(workers)]
        chunks = [c for c in chunks if c]

        all_results: list[tuple[str, str, int, float]] = []
        t0 = time.perf_counter()

        def work(chunk: list[str]) -> list[tuple[str, str, int, float]]:
            out = []
            for sid in chunk:
                oid, status, ms = _post_reserve(sid)
                out.append((oid, sid, status, ms))
            return out

        with ThreadPoolExecutor(max_workers=len(chunks)) as ex:
            for batch in ex.map(work, chunks):
                all_results.extend(batch)

        dur = time.perf_counter() - t0
        latencies = [r[3] for r in all_results]
        ok = sum(1 for r in all_results if r[2] == 200)
        err = len(all_results) - ok
        avg = sum(latencies) / len(latencies) if latencies else 0.0
        max_ms = max(latencies) if latencies else 0.0

        ts = now_iso()
        append_csv_row(out_resumen, RESUMEN_FIELDS, {
            "timestamp_utc": ts, "escenario": "concurrencia_sin_conflicto", "nivel": str(nivel),
            "total_solicitudes": str(len(all_results)), "success": str(ok), "errors": str(err),
            "error_pct": f"{(err / len(all_results) * 100) if all_results else 0:.2f}",
            "avg_ms": f"{avg:.2f}", "p95_ms": f"{_p95(latencies):.2f}", "max_ms": f"{max_ms:.2f}",
            "duracion_s": f"{dur:.3f}",
        })
        for oid, sid, status, ms in all_results:
            append_csv_row(out_detalle, DETALLE_FIELDS, {
                "timestamp_utc": ts, "escenario": "concurrencia_sin_conflicto", "nivel": str(nivel),
                "order_id": oid, "stock_id": sid, "tipo": "normal", "pareja_id": "",
                "http_status": str(status), "duracion_ms": f"{ms:.4f}",
            })

        print(f"  -> success={ok}, errors={err}, avg_ms={avg:.2f}, max_ms={max_ms:.2f}, dur={dur:.1f}s")

    print(f"CSV resumen: {out_resumen}")
    print(f"CSV detalle: {out_detalle}")


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2a — Dos clientes mismo producto
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_dos_clientes_conflicto() -> None:
    out = V2_ROOT / "dos_clientes_conflicto" / "results" / "detalle.csv"
    ensure_csv_header(out, DOS_CLIENTES_FIELDS)
    sid = env_str("V2_CONFLICT_STOCK", "STK00001")

    print(f"\n[Dos clientes] 2 solicitudes concurrentes al producto {sid} (medicion en nanosegundos)")

    _ensure_single_unit_available([sid])

    with ThreadPoolExecutor(max_workers=2) as ex:
        futs = [ex.submit(_post_reserve_ns, sid), ex.submit(_post_reserve_ns, sid)]
        results = [f.result() for f in futs]

    statuses = [r[1] for r in results]
    rollback_ok = (200 in statuses and 409 in statuses)
    ts = now_iso()

    for oid, status, ns in results:
        append_csv_row(out, DOS_CLIENTES_FIELDS, {
            "timestamp_utc": ts, "escenario": "dos_clientes_conflicto",
            "order_id": oid, "stock_id": sid, "http_status": str(status),
            "duracion_ns": str(ns), "es_rollback_exitoso": str(rollback_ok),
        })
        print(f"  -> {oid}: HTTP {status}, {ns:,} ns ({ns / 1_000_000:.2f} ms)")

    print(f"  -> Rollback exitoso: {rollback_ok}")
    print(f"CSV detalle: {out}")


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 2b — Rollback 1% conflicto en parejas
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_rollback_1pct_parejas() -> None:
    out_resumen = V2_ROOT / "rollback_1pct_parejas" / "results" / "resumen.csv"
    out_detalle = V2_ROOT / "rollback_1pct_parejas" / "results" / "detalle.csv"
    ensure_csv_header(out_resumen, ROLLBACK_RESUMEN_FIELDS)
    ensure_csv_header(out_detalle, ROLLBACK_DETALLE_FIELDS)
    max_stock = env_int("V2_MAX_STOCK_ID", 5000)

    for nivel in ROLLBACK_LEVELS:
        conflict_total = max(2, int(nivel * 0.01))
        if conflict_total % 2 == 1:
            conflict_total += 1
        n_parejas = conflict_total // 2
        normal_n = nivel - conflict_total

        conflict_stocks = [f"STK{(i % max_stock) + 1:05d}" for i in range(n_parejas)]
        normal_pool = [f"STK{(i % max_stock) + 1:05d}" for i in range(n_parejas, n_parejas + normal_n)]

        _ensure_single_unit_available(list(dict.fromkeys(conflict_stocks)))

        @dataclass
        class RequestSpec:
            stock_id: str
            tipo: str
            pareja_id: str

        plan: list[RequestSpec] = []
        for p_idx, sid in enumerate(conflict_stocks):
            pid = f"P{p_idx:04d}"
            plan.append(RequestSpec(sid, "conflicto", pid))
            plan.append(RequestSpec(sid, "conflicto", pid))
        for sid in normal_pool:
            plan.append(RequestSpec(sid, "normal", ""))
        random.shuffle(plan)

        print(f"\n[Rollback 1% parejas] nivel={nivel} → {nivel} solicitudes, {n_parejas} parejas de conflicto, {normal_n} normales")

        workers = min(nivel, env_int("V2_MAX_WORKERS", 2000))
        per_worker = max(1, len(plan) // workers)
        chunks = [plan[i * per_worker:(i + 1) * per_worker] for i in range(workers)]
        chunks = [c for c in chunks if c]

        all_results: list[tuple[str, str, str, str, int, float]] = []
        t0 = time.perf_counter()

        def work(chunk: list[RequestSpec]) -> list[tuple[str, str, str, str, int, float]]:
            out = []
            for spec in chunk:
                oid, status, ms = _post_reserve(spec.stock_id)
                out.append((oid, spec.stock_id, spec.tipo, spec.pareja_id, status, ms))
            return out

        with ThreadPoolExecutor(max_workers=len(chunks)) as ex:
            for batch in ex.map(work, chunks):
                all_results.extend(batch)

        dur = time.perf_counter() - t0
        latencies = [r[5] for r in all_results]
        avg = sum(latencies) / len(latencies) if latencies else 0.0
        max_ms = max(latencies) if latencies else 0.0

        parejas: dict[str, list[int]] = defaultdict(list)
        for _, _, tipo, pid, status, _ in all_results:
            if tipo == "conflicto" and pid:
                parejas[pid].append(status)

        rollback_ok = 0
        rollback_fail = 0
        for pid, statuses in parejas.items():
            if 200 in statuses and 409 in statuses:
                rollback_ok += 1
            else:
                rollback_fail += 1

        ts = now_iso()
        append_csv_row(out_resumen, ROLLBACK_RESUMEN_FIELDS, {
            "timestamp_utc": ts, "escenario": "rollback_1pct_parejas", "nivel": str(nivel),
            "total_solicitudes": str(len(all_results)), "parejas_conflicto": str(n_parejas),
            "solicitudes_normales": str(normal_n),
            "rollback_exitosos": str(rollback_ok), "rollback_fallidos": str(rollback_fail),
            "avg_ms": f"{avg:.2f}", "p95_ms": f"{_p95(latencies):.2f}", "max_ms": f"{max_ms:.2f}",
            "duracion_s": f"{dur:.3f}",
        })
        for oid, sid, tipo, pid, status, ms in all_results:
            append_csv_row(out_detalle, ROLLBACK_DETALLE_FIELDS, {
                "timestamp_utc": ts, "escenario": "rollback_1pct_parejas", "nivel": str(nivel),
                "order_id": oid, "stock_id": sid, "tipo": tipo, "pareja_id": pid,
                "http_status": str(status), "duracion_ms": f"{ms:.4f}",
            })

        print(f"  -> rollback exitosos={rollback_ok}/{n_parejas}, fallidos={rollback_fail}, avg_ms={avg:.2f}, max_ms={max_ms:.2f}")

    print(f"CSV resumen: {out_resumen}")
    print(f"CSV detalle: {out_detalle}")


# ═══════════════════════════════════════════════════════════════════════════════
# BLOQUE 3 — Seguridad IDS: generacion de usuarios
# ═══════════════════════════════════════════════════════════════════════════════

def _ids_conn():
    p = _ids_db_params()
    try:
        return psycopg2.connect(**p)
    except psycopg2.OperationalError as e:
        raise RuntimeError(
            f"No se pudo conectar a PostgreSQL IDS ({p['host']}:{p['port']}, db={p['dbname']}): {e}\n"
            "Levante el contenedor: docker compose -f docker-compose.ids.yml up -d\n"
            "Cargue esquema y datos (desde la raiz del repo):\n"
            "  Get-Content scripts/ids_postgres_schema.sql | docker exec -i ids_postgres psql -U postgres -d postgres\n"
            "  Get-Content scripts/ids_postgres_seed.sql | docker exec -i ids_postgres psql -U postgres -d postgres"
        ) from e


def _setup_ids_users(n: int, dangerous_pct: float, conditions: list[str]) -> tuple[list[int], list[int]]:
    """
    Genera n usuarios en la BD IDS. dangerous_pct fraccion son peligrosos.
    conditions: subset de ["geo", "dispositivo", "tasa"]
    Retorna (ids_normales, ids_peligrosos).
    """
    n_dangerous = max(0, int(n * dangerous_pct))
    n_normal = n - n_dangerous
    conn = _ids_conn()
    cur = conn.cursor()

    cur.execute("TRUNCATE incidente RESTART IDENTITY CASCADE;")
    cur.execute("DELETE FROM dispositivo_usuario;")
    cur.execute("DELETE FROM perfile_seguridad_usuario;")
    cur.execute("DELETE FROM usuario;")
    conn.commit()

    all_normal: list[int] = []
    all_dangerous: list[int] = []
    uid = 1000

    batch_size = 500
    for start in range(0, n_normal, batch_size):
        end = min(start + batch_size, n_normal)
        ids = list(range(uid, uid + (end - start)))
        uid += len(ids)
        all_normal.extend(ids)

        vals_usuario = ",".join(f"({i}, 'ACTIVO')" for i in ids)
        cur.execute(f"INSERT INTO usuario (id, estado) VALUES {vals_usuario};")

        vals_perfil = ",".join(f"({i}, 40.4168, -3.7038, NOW(), 10.0)" for i in ids)
        cur.execute(f"INSERT INTO perfile_seguridad_usuario (id_usuario, latitud, longitud, inicio_sesion, promedio_pxm) VALUES {vals_perfil};")

        vals_disp = ",".join(f"({i}, 'fp-trusted-{i}', TRUE)" for i in ids)
        cur.execute(f"INSERT INTO dispositivo_usuario (id_usuario, dispositivo, confiable) VALUES {vals_disp};")

    for start in range(0, n_dangerous, batch_size):
        end = min(start + batch_size, n_dangerous)
        ids = list(range(uid, uid + (end - start)))
        uid += len(ids)
        all_dangerous.extend(ids)

        vals_usuario = ",".join(f"({i}, 'ACTIVO')" for i in ids)
        cur.execute(f"INSERT INTO usuario (id, estado) VALUES {vals_usuario};")

        use_geo = "geo" in conditions
        use_disp = "dispositivo" in conditions
        use_tasa = "tasa" in conditions

        lat = 0.0 if use_geo else 40.4168
        lon = 0.0 if use_geo else -3.7038
        sesion = "NOW() - INTERVAL '1 hour'" if use_geo else "NOW()"
        promedio = 10.0 if use_tasa else 0.0

        vals_perfil = ",".join(f"({i}, {lat}, {lon}, {sesion}, {promedio})" for i in ids)
        cur.execute(f"INSERT INTO perfile_seguridad_usuario (id_usuario, latitud, longitud, inicio_sesion, promedio_pxm) VALUES {vals_perfil};")

        if not use_disp:
            vals_disp = ",".join(f"({i}, 'fp-trusted-{i}', TRUE)" for i in ids)
            cur.execute(f"INSERT INTO dispositivo_usuario (id_usuario, dispositivo, confiable) VALUES {vals_disp};")
        else:
            vals_disp = ",".join(f"({i}, 'fp-trusted-{i}', TRUE)" for i in ids)
            cur.execute(f"INSERT INTO dispositivo_usuario (id_usuario, dispositivo, confiable) VALUES {vals_disp};")

    conn.commit()
    cur.close()
    conn.close()
    return all_normal, all_dangerous


def _build_ids_params(user_id: int, is_dangerous: bool, conditions: list[str]) -> dict:
    """Build query params for IDS endpoint depending on conditions to trigger."""
    params = {
        "latitud_actual": 40.4168,
        "longitud_actual": -3.7038,
        "dispositivo_actual": f"fp-trusted-{user_id}",
        "tasa_peticiones_actual": 5.0,
        "ip_actual": "10.0.0.1",
    }
    if is_dangerous:
        if "geo" in conditions:
            params["latitud_actual"] = 10.0
            params["longitud_actual"] = 10.0
        if "dispositivo" in conditions:
            params["dispositivo_actual"] = f"fp-attacker-{uuid.uuid4().hex[:6]}"
        if "tasa" in conditions:
            params["tasa_peticiones_actual"] = 999.0
    return params


def _call_ids(user_id: int, params: dict) -> tuple[int, dict, float]:
    t0 = time.perf_counter()
    try:
        with httpx.Client() as c:
            r = c.get(f"{_ids_base()}/api/v1/ids/detectar/{user_id}", params=params, timeout=30.0)
        ms = (time.perf_counter() - t0) * 1000
        body = r.json() if r.status_code == 200 else {}
        return r.status_code, body, ms
    except Exception:
        ms = (time.perf_counter() - t0) * 1000
        return -1, {}, ms


def _run_ids_test(
    escenario: str,
    conditions_label: str,
    conditions: list[str],
    nivel: int,
    dangerous_pct: float,
    out_resumen: Path,
    out_detalle: Path,
    fraude_esperado: bool,
) -> None:
    print(f"  Generando {nivel} usuarios ({dangerous_pct * 100:.0f}% peligrosos, condiciones={conditions})...")
    normals, dangerous = _setup_ids_users(nivel, dangerous_pct, conditions)

    user_plan: list[tuple[int, bool]] = [(uid, False) for uid in normals] + [(uid, True) for uid in dangerous]
    random.shuffle(user_plan)

    print(f"  Enviando {len(user_plan)} solicitudes al IDS...")
    all_results: list[tuple[int, bool, int, dict, float]] = []
    workers = min(len(user_plan), env_int("V2_MAX_WORKERS", 200))
    per_worker = max(1, len(user_plan) // workers)
    chunks = [user_plan[i * per_worker:(i + 1) * per_worker] for i in range(workers)]
    chunks = [c for c in chunks if c]

    def work(chunk: list[tuple[int, bool]]) -> list[tuple[int, bool, int, dict, float]]:
        out = []
        for uid, is_d in chunk:
            params = _build_ids_params(uid, is_d, conditions)
            status, body, ms = _call_ids(uid, params)
            out.append((uid, is_d, status, body, ms))
        return out

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=len(chunks)) as ex:
        for batch in ex.map(work, chunks):
            all_results.extend(batch)
    dur = time.perf_counter() - t0

    latencies = [r[4] for r in all_results]
    avg = sum(latencies) / len(latencies) if latencies else 0.0
    max_ms_val = max(latencies) if latencies else 0.0
    detecciones_correctas = 0
    falsos_positivos = 0
    en_300 = 0

    stock_ref = _sec_stock_ref()
    ts = now_iso()
    for uid, is_d, status, body, ms in all_results:
        fraude_obtenido = body.get("es_incidente_fraude", False) if status == 200 else False
        riesgo = body.get("riesgo", 0.0) if status == 200 else 0.0

        if is_d:
            if fraude_obtenido == fraude_esperado:
                detecciones_correctas += 1
            if ms < 300:
                en_300 += 1
        else:
            if fraude_obtenido:
                falsos_positivos += 1

        append_csv_row(out_detalle, SEC_DETALLE_FIELDS, {
            "timestamp_utc": ts, "escenario": escenario, "condiciones": conditions_label,
            "nivel": str(nivel), "stock_id_referencia": stock_ref,
            "id_usuario": str(uid),
            "tipo_usuario": "peligroso" if is_d else "normal",
            "http_status": str(status), "es_fraude_obtenido": str(fraude_obtenido),
            "riesgo": f"{riesgo:.1f}", "duracion_ms": f"{ms:.4f}",
            "en_menos_300ms": str(ms < 300),
        })

    n_dangerous = len(dangerous)
    append_csv_row(out_resumen, SEC_RESUMEN_FIELDS, {
        "timestamp_utc": ts, "escenario": escenario, "condiciones": conditions_label,
        "nivel": str(nivel), "total": str(len(all_results)),
        "detecciones_correctas": str(detecciones_correctas),
        "deteccion_correcta_pct": f"{(detecciones_correctas / n_dangerous * 100) if n_dangerous else 0:.2f}",
        "falsos_positivos": str(falsos_positivos),
        "avg_ms": f"{avg:.2f}", "p95_ms": f"{_p95(latencies):.2f}", "max_ms": f"{max_ms_val:.2f}",
        "en_menos_300ms": str(en_300),
        "en_menos_300ms_pct": f"{(en_300 / n_dangerous * 100) if n_dangerous else 0:.2f}",
    })

    print(f"  -> correctas={detecciones_correctas}/{n_dangerous}, falsos_pos={falsos_positivos}, avg_ms={avg:.2f}, <300ms={en_300}/{n_dangerous}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3a — Un usuario peligroso en <300ms
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_deteccion_un_peligroso() -> None:
    out = V2_ROOT / "deteccion_un_peligroso" / "results" / "detalle.csv"
    ensure_csv_header(out, SEC_DETALLE_FIELDS)

    print("\n[Seguridad 3a] Deteccion de un usuario peligroso (geo+dispositivo=80) en <300ms")
    _, dangerous = _setup_ids_users(1, 1.0, ["geo", "dispositivo"])
    uid = dangerous[0]
    params = _build_ids_params(uid, True, ["geo", "dispositivo"])
    status, body, ms = _call_ids(uid, params)
    fraude = body.get("es_incidente_fraude", False) if status == 200 else False
    riesgo = body.get("riesgo", 0.0) if status == 200 else 0.0

    ts = now_iso()
    append_csv_row(out, SEC_DETALLE_FIELDS, {
        "timestamp_utc": ts, "escenario": "deteccion_un_peligroso", "condiciones": "geo+dispositivo",
        "nivel": "1", "stock_id_referencia": _sec_stock_ref(),
        "id_usuario": str(uid), "tipo_usuario": "peligroso",
        "http_status": str(status), "es_fraude_obtenido": str(fraude),
        "riesgo": f"{riesgo:.1f}", "duracion_ms": f"{ms:.4f}",
        "en_menos_300ms": str(ms < 300),
    })
    print(f"  -> HTTP {status}, fraude={fraude}, riesgo={riesgo}, {ms:.2f}ms, <300ms={ms < 300}")
    print(f"CSV detalle: {out}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3b — 1% peligrosos a escala
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_deteccion_1pct_peligrosos() -> None:
    out_resumen = V2_ROOT / "deteccion_1pct_peligrosos" / "results" / "resumen.csv"
    out_detalle = V2_ROOT / "deteccion_1pct_peligrosos" / "results" / "detalle.csv"
    ensure_csv_header(out_resumen, SEC_RESUMEN_FIELDS)
    ensure_csv_header(out_detalle, SEC_DETALLE_FIELDS)

    print("\n[Seguridad 3b] 1% peligrosos (geo+dispositivo) a escala")
    for nivel in SECURITY_LEVELS:
        print(f"\n  --- Nivel {nivel} usuarios ---")
        _run_ids_test("deteccion_1pct", "geo+dispositivo", ["geo", "dispositivo"],
                      nivel, 0.01, out_resumen, out_detalle, fraude_esperado=True)

    print(f"CSV resumen: {out_resumen}")
    print(f"CSV detalle: {out_detalle}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3c — 1 condicion individual (3 variantes)
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_deteccion_1_condicion() -> None:
    out_resumen = V2_ROOT / "deteccion_1_condicion" / "results" / "resumen.csv"
    out_detalle = V2_ROOT / "deteccion_1_condicion" / "results" / "detalle.csv"
    ensure_csv_header(out_resumen, SEC_RESUMEN_FIELDS)
    ensure_csv_header(out_detalle, SEC_DETALLE_FIELDS)

    variantes = [
        ("geo", ["geo"], False),
        ("dispositivo", ["dispositivo"], False),
        ("tasa", ["tasa"], False),
    ]

    for label, conds, fraude_esperado in variantes:
        print(f"\n[Seguridad 3c] 1 condicion: {label} (riesgo>0 pero NO fraude)")
        for nivel in SECURITY_LEVELS:
            print(f"\n  --- {label} | Nivel {nivel} ---")
            _run_ids_test("deteccion_1_condicion", label, conds,
                          nivel, 1.0, out_resumen, out_detalle, fraude_esperado=fraude_esperado)

    print(f"CSV resumen: {out_resumen}")
    print(f"CSV detalle: {out_detalle}")


# ═══════════════════════════════════════════════════════════════════════════════
# 3d — 2 condiciones combinadas (3 combinatorias)
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_deteccion_2_condiciones() -> None:
    out_resumen = V2_ROOT / "deteccion_2_condiciones" / "results" / "resumen.csv"
    out_detalle = V2_ROOT / "deteccion_2_condiciones" / "results" / "detalle.csv"
    ensure_csv_header(out_resumen, SEC_RESUMEN_FIELDS)
    ensure_csv_header(out_detalle, SEC_DETALLE_FIELDS)

    combos = [
        ("geo+dispositivo", ["geo", "dispositivo"], True),    # 50+30=80 >= 75
        ("geo+tasa", ["geo", "tasa"], False),                 # 50+20=70 < 75
        ("dispositivo+tasa", ["dispositivo", "tasa"], False),  # 30+20=50 < 75
    ]

    for label, conds, fraude_esperado in combos:
        print(f"\n[Seguridad 3d] 2 condiciones: {label} (fraude esperado={fraude_esperado})")
        for nivel in SECURITY_LEVELS:
            print(f"\n  --- {label} | Nivel {nivel} ---")
            _run_ids_test("deteccion_2_condiciones", label, conds,
                          nivel, 1.0, out_resumen, out_detalle, fraude_esperado=fraude_esperado)

    print(f"CSV resumen: {out_resumen}")
    print(f"CSV detalle: {out_detalle}")
