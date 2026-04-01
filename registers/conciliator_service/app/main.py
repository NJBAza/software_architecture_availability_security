import os
import uuid
import httpx
from fastapi import FastAPI
from sqlalchemy import text
from app.db import engine
from fastapi.responses import Response
from scalar_fastapi import get_scalar_api_reference
app = FastAPI()

ORDERS_SERVICE_URL = os.getenv("ORDERS_SERVICE_URL", "http://orders_service:8000")
RESERVATIONS_SERVICE_URL = os.getenv("RESERVATIONS_SERVICE_URL", "http://reservations_service:8000")


@app.get("/health")
def health():
    return {"status": "ok", "service": "conciliator"}


@app.post("/conciliator/reconcile")
async def reconcile():
    async with httpx.AsyncClient(timeout=5.0) as client:
        pending_orders_resp = await client.get(f"{ORDERS_SERVICE_URL}/orders/pending")
        active_res_resp = await client.get(f"{RESERVATIONS_SERVICE_URL}/reservations/active")

    pending_orders = pending_orders_resp.json()
    active_reservations = active_res_resp.json()

    anomalies_found = len(pending_orders)
    action_taken = "alert" if anomalies_found else "none"

    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO reconciliation_runs (run_id, anomalies_found, action_taken)
                VALUES (:run_id, :anomalies_found, :action_taken)
            """),
            {
                "run_id": str(uuid.uuid4()),
                "anomalies_found": anomalies_found,
                "action_taken": action_taken,
            },
        )

    return {
        "pending_orders": pending_orders,
        "active_reservations": active_reservations,
        "anomalies_found": anomalies_found,
        "action_taken": action_taken,
    }
    
@app.get("/scalar", include_in_schema=False)
def get_scalar_docs() -> Response:
    """Return Scalar API reference documentation.

    Returns:
        Response: Scalar API reference UI.

    """
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API",
    )
