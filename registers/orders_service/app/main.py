import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.db import engine
from fastapi.responses import Response
from scalar_fastapi import get_scalar_api_reference

app = FastAPI()
RESERVATIONS_SERVICE_URL = os.getenv("RESERVATIONS_SERVICE_URL", "http://reservations_service:8000")


class CreateOrderRequest(BaseModel):
    order_id: str
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
        conn.execute(
            text("""
                INSERT INTO sales_orders (order_id, seller_id, store_id, status, total_amount)
                VALUES (:order_id, :seller_id, :store_id, 'PENDING', :total_amount)
            """),
            {
                "order_id": payload.order_id,
                "seller_id": payload.seller_id,
                "store_id": payload.store_id,
                "total_amount": payload.total_amount,
            },
        )

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(
            f"{RESERVATIONS_SERVICE_URL}/reservations/reserve",
            json={
                "order_id": payload.order_id,
                "stock_id": payload.stock_id,
                "quantity": payload.quantity,
            },
        )

    with engine.begin() as conn:
        if response.status_code == 200:
            conn.execute(
                text("""
                    UPDATE sales_orders
                    SET status = 'CONFIRMED'
                    WHERE order_id = :order_id
                """),
                {"order_id": payload.order_id},
            )
            return {"message": "Order confirmed", "order_id": payload.order_id}

        conn.execute(
            text("""
                UPDATE sales_orders
                SET status = 'REJECTED'
                WHERE order_id = :order_id
            """),
            {"order_id": payload.order_id},
        )

    raise HTTPException(status_code=409, detail="Reservation failed")


@app.get("/orders/pending")
def get_pending_orders():
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT * FROM sales_orders WHERE status = 'PENDING'")
        ).mappings().all()
    return rows

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
