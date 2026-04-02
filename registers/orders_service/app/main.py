import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.db import engine
from fastapi.responses import Response
from scalar_fastapi import get_scalar_api_reference

app = FastAPI()
RESERVATIONS_SERVICE_URL = os.getenv(
    "RESERVATIONS_SERVICE_URL",
    "http://reservations_service:8000"
)


class CreateOrderRequest(BaseModel):
    seller_id: str
    store_id: str
    stock_id: str
    quantity: int
    total_amount: float


@app.get("/health")
def health():
    return {"status": "ok", "service": "orders"}


@app.post("/orders")
async def create_order(payload: CreateOrderRequest):
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO sales_orders (
                    seller_id,
                    store_id,
                    status,
                    total_amount
                )
                VALUES (
                    :seller_id,
                    :store_id,
                    'PENDING',
                    :total_amount
                )
                RETURNING order_id, created_at
            """),
            {
                "seller_id": payload.seller_id,
                "store_id": payload.store_id,
                "total_amount": payload.total_amount,
            },
        ).mappings().first()
        
        order_id = row["order_id"]
        created_at = row["created_at"]

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            f"{RESERVATIONS_SERVICE_URL}/reservations/reserve",
            json={
                "order_id": order_id,
                "stock_id": payload.stock_id,
                "quantity": payload.quantity,
            },
        )

    with engine.begin() as conn:
        if response.status_code == 200:
            reservation_id = None
            try:
                payload_json = response.json()
                reservation_id = payload_json.get("reservation_id")
            except Exception:
                reservation_id = None

            conn.execute(
                text("""
                    UPDATE sales_orders
                    SET status = 'CONFIRMED',
                        reservation_id = :reservation_id
                    WHERE order_id = :order_id
                """),
                {
                    "order_id": order_id,
                    "reservation_id": reservation_id,
                },
            )

            return {
                "message": "Order confirmed",
                "order_id": order_id,
                "created_at": created_at,
                "reservation_id": reservation_id,
            }

        conn.execute(
            text("""
                UPDATE sales_orders
                SET status = 'REJECTED'
                WHERE order_id = :order_id
            """),
            {"order_id": order_id},
        )

    raise HTTPException(
        status_code=409,
        detail={
            "message": "Reservation failed",
            "order_id": order_id,
            "created_at": str(created_at),
        },
    )


@app.get("/orders/pending")
def get_pending_orders():
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT *
                FROM sales_orders
                WHERE status = 'PENDING'
                ORDER BY created_at DESC
            """)
        ).mappings().all()
    return rows


@app.get("/orders")
def get_orders():
    with engine.begin() as conn:
        rows = conn.execute(
            text("""
                SELECT *
                FROM sales_orders
                ORDER BY created_at DESC
            """)
        ).mappings().all()
    return rows


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                SELECT *
                FROM sales_orders
                WHERE order_id = :order_id
            """),
            {"order_id": order_id},
        ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Order not found")

    return row


@app.get("/scalar", include_in_schema=False)
def get_scalar_docs() -> Response:
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API",
    )