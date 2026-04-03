import os
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from scalar_fastapi import get_scalar_api_reference
from sqlalchemy import text

from app.db import engine

app = FastAPI()

RESERVATION_TTL_MINUTES = int(os.getenv("RESERVATION_TTL_MINUTES", "30"))


class ReserveStockRequest(BaseModel):
    order_id: str
    stock_id: str
    quantity: int


@app.get("/health")
def health():
    return {"status": "ok", "service": "reservations"}


@app.post("/reservations/reserve")
def reserve_stock(payload: ReserveStockRequest):
    if payload.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be greater than 0")

    with engine.begin() as conn:
        stock_row = conn.execute(
            text("""
                SELECT stock_id, qty_on_hand, qty_reserved
                FROM warehouse_stock
                WHERE stock_id = :stock_id
                FOR UPDATE
            """),
            {"stock_id": payload.stock_id},
        ).mappings().first()

        if not stock_row:
            raise HTTPException(status_code=404, detail="Stock not found")

        available_quantity = stock_row["qty_on_hand"] - stock_row["qty_reserved"]

        if available_quantity < payload.quantity:
            raise HTTPException(status_code=409, detail="Insufficient stock")

        expires_at = datetime.now(UTC) + timedelta(minutes=RESERVATION_TTL_MINUTES)
        idempotency_key = str(uuid.uuid4())
        outbox_event_id = f"EVT{uuid.uuid4().int % 1000000:06d}"

        reservation_row = conn.execute(
            text("""
                INSERT INTO reservations (
                    idempotency_key,
                    stock_id,
                    quantity,
                    status,
                    order_id,
                    expires_at,
                    outbox_event_id
                )
                VALUES (
                    :idempotency_key,
                    :stock_id,
                    :quantity,
                    'ACTIVE',
                    :order_id,
                    :expires_at,
                    :outbox_event_id
                )
                RETURNING reservation_id
            """),
            {
                "idempotency_key": idempotency_key,
                "stock_id": payload.stock_id,
                "quantity": payload.quantity,
                "order_id": payload.order_id,
                "expires_at": expires_at,
                "outbox_event_id": outbox_event_id,
            },
        ).mappings().first()

        conn.execute(
            text("""
                UPDATE warehouse_stock
                SET qty_reserved = qty_reserved + :quantity
                WHERE stock_id = :stock_id
            """),
            {
                "quantity": payload.quantity,
                "stock_id": payload.stock_id,
            },
        )

    return {
        "message": "Reservation created",
        "reservation_id": reservation_row["reservation_id"],
        "order_id": payload.order_id,
        "stock_id": payload.stock_id,
        "quantity": payload.quantity,
        "status": "ACTIVE",
        "expires_at": expires_at.isoformat(),
    }

@app.get("/stock")
def list_stock():
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT *,
                       (qty_on_hand - qty_reserved) AS available_quantity
                FROM warehouse_stock
                ORDER BY stock_id
            """)
        ).mappings().all()
    return rows

@app.get("/reservations")
def get_reservations():
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT *
                FROM reservations
                ORDER BY expires_at DESC, reservation_id DESC
            """)
        ).mappings().all()
    return rows


@app.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: str):
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT *
                FROM reservations
                WHERE reservation_id = :reservation_id
            """),
            {"reservation_id": reservation_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Reservation not found")

    return row


@app.get("/stock/{stock_id}")
def get_stock(stock_id: str):
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT *,
                       (qty_on_hand - qty_reserved) AS available_quantity
                FROM warehouse_stock
                WHERE stock_id = :stock_id
            """),
            {"stock_id": stock_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Stock not found")

    return row


@app.get("/scalar", include_in_schema=False)
def get_scalar_docs() -> Response:
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API",
    )