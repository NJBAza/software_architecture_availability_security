from fastapi import FastAPI, HTTPException, status
from fastapi.responses import Response
from scalar_fastapi import get_scalar_api_reference

from .database import Database
from .schemas import ShipmentCreate, ShipmentRead, ShipmentUpdate
from apps.services import IDS

app = FastAPI()

db = Database()
db.connect_to_db()
db.create_table()

# In-memory shipments datastore
shipments = {
    12701: {"weight": 8.2, "content": "aluminum sheets", "status": "placed", "destination": 11002},
    12702: {"weight": 14.7, "content": "steel rods", "status": "shipped", "destination": 11003},
    12703: {
        "weight": 11.4,
        "content": "copper wires",
        "status": "delivered",
        "destination": 11002,
    },
    12704: {
        "weight": 17.8,
        "content": "iron plates",
        "status": "in transit",
        "destination": 11005,
    },
    12705: {
        "weight": 10.3,
        "content": "brass fittings",
        "status": "returned",
        "destination": 11008,
    },
}

app.include_router(IDS.router)

@app.get("/")
def raiz():
    return {"estado": "API funcionando"}

@app.get("/shipment", response_model=ShipmentRead)
def get_shipment(id: int) -> ShipmentRead:
    """Retrieve a shipment by its ID."""
    if id not in shipments:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Given id doesn't exist!",
        )
    return shipments[id]


@app.post("/shipment", response_model=None)
def submit_shipment(shipment: ShipmentCreate) -> dict[str, int]:
    """Create a new shipment.

    Generates a new unique ID and stores the shipment in the in‑memory datastore.

    """
    new_id = db.create(shipment)
    return {"id": new_id}


@app.patch("/shipment", response_model=ShipmentRead)
def update_shipment(id: int, shipment: ShipmentUpdate) -> ShipmentRead:
    """Update an existing shipment."""
    updated = db.update(id, shipment)
    return updated


@app.delete("/shipment", response_model=dict[str, str])
def delete_shipment(id: int) -> dict[str, str]:
    """Delete a shipment by ID."""
    db.delete(id)
    return {"detail": f"Shipment with id #{id} is deleted!"}


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
