import os
import httpx
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from scalar_fastapi import get_scalar_api_reference
from sqlalchemy import text

from app.db import engine

app = FastAPI()

ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders_service:8000")
RESERVATIONS_SERVICE_URL = os.getenv("RESERVATIONS_SERVICE_URL", "http://reservations_service:8000")


def next_run_id(conn) -> str:
    row = conn.execute(
        text("""
            SELECT run_id
            FROM reconciliation_runs
            WHERE run_id ~ '^RUN[0-9]+$'
            ORDER BY CAST(SUBSTRING(run_id FROM 4) AS INTEGER) DESC
            LIMIT 1
        """)
    ).mappings().first()

    if not row:
        return "RUN00001"

    current = int(row["run_id"][3:])
    return f"RUN{current + 1:05d}"


@app.get("/health")
def health():
    return {"status": "ok", "service": "conciliator"}


@app.post("/conciliator/reconcile")
async def reconcile():
    async with httpx.AsyncClient(timeout=10.0) as client:
        orders_resp = await client.get(f"{ORDERS_SERVICE_URL}/orders")
        reservations_resp = await client.get(f"{RESERVATIONS_SERVICE_URL}/reservations")

        if orders_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Orders service unavailable")

        if reservations_resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Reservations service unavailable")

        orders = orders_resp.json()
        reservations = reservations_resp.json()

    orders_by_id = {o["order_id"]: o for o in orders}
    reservations_by_order = {r["order_id"]: r for r in reservations}

    anomalies_found = 0
    reservas_fantasma = 0

    # ghost reservations
    for reservation in reservations:
        order = orders_by_id.get(reservation["order_id"])
        if not order or order["status"] == "REJECTED":
            reservas_fantasma += 1
            anomalies_found += 1

    # confirmed orders without reservation
    for order in orders:
        if order["status"] == "CONFIRMED":
            reservation = reservations_by_order.get(order["order_id"])
            if not reservation:
                anomalies_found += 1

    # negative stock
    stock_negativo = False
    async with httpx.AsyncClient(timeout=10.0) as client:
        # if you later add GET /stock, use it here
        pass

    # lightweight stock check through DB owned by conciliator? no
    # better: query reservations DB through API extension or direct connector
    # for now keep false unless you add a stock-list endpoint
    action_taken = "none" if anomalies_found == 0 else "alert"

    executed_at = datetime.now(UTC)

    with engine.begin() as conn:
        run_id = next_run_id(conn)
        conn.execute(
            text("""
                INSERT INTO reconciliation_runs (
                    run_id,
                    executed_at,
                    anomalies_found,
                    stock_negativo,
                    reservas_fantasma,
                    action_taken
                )
                VALUES (
                    :run_id,
                    :executed_at,
                    :anomalies_found,
                    :stock_negativo,
                    :reservas_fantasma,
                    :action_taken
                )
            """),
            {
                "run_id": run_id,
                "executed_at": executed_at,
                "anomalies_found": anomalies_found,
                "stock_negativo": stock_negativo,
                "reservas_fantasma": reservas_fantasma,
                "action_taken": action_taken,
            },
        )

    return {
        "run_id": run_id,
        "executed_at": executed_at.isoformat(),
        "anomalies_found": anomalies_found,
        "stock_negativo": stock_negativo,
        "reservas_fantasma": reservas_fantasma,
        "action_taken": action_taken,
    }


@app.get("/conciliator/runs")
def get_runs():
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT *
                FROM reconciliation_runs
                ORDER BY executed_at DESC
            """)
        ).mappings().all()
    return rows


@app.get("/scalar", include_in_schema=False)
def get_scalar_docs() -> Response:
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API",
    )