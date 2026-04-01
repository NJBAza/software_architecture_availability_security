from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from app.db import engine
from fastapi.responses import Response
from scalar_fastapi import get_scalar_api_reference
app = FastAPI()


class ReserveRequest(BaseModel):
    order_id: str
    stock_id: str
    quantity: int


@app.get("/health")
def health():
    return {"status": "ok", "service": "reservations"}


@app.post("/reservations/reserve")
def reserve_stock(payload: ReserveRequest):
    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE warehouse_stock
                SET qty_on_hand = qty_on_hand - :qty
                WHERE stock_id = :stock_id
                  AND qty_on_hand >= :qty
            """),
            {"stock_id": payload.stock_id, "qty": payload.quantity},
        )

        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Out of stock")

        conn.execute(
            text("""
                INSERT INTO reservations (order_id, stock_id, quantity, status)
                VALUES (:order_id, :stock_id, :qty, 'ACTIVE')
            """),
            {
                "order_id": payload.order_id,
                "stock_id": payload.stock_id,
                "qty": payload.quantity,
            },
        )

    return {"message": "Reservation created", "order_id": payload.order_id}


@app.get("/reservations/active")
def get_active_reservations():
    with engine.begin() as conn:
        rows = conn.execute(
            text("SELECT * FROM reservations WHERE status = 'ACTIVE'")
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
