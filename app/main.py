from typing import Any

from fastapi import FastAPI, HTTPException, status
from scalar_fastapi import get_scalar_api_reference

from .schemas import Shipment, ShipmentState

app = FastAPI()

shipments = {
    73904: {"weight": 0.5, "content": "wine", "state": "arriving"},
    73905: {"weight": 3.2, "content": "smartphones", "state": "in_transit"},
    73906: {"weight": 7.8, "content": "garden tools", "state": "delivered"},
    73907: {"weight": 0.9, "content": "cosmetics", "state": "placed"},
    73908: {"weight": 15.0, "content": "industrial parts", "state": "out_for_delivery"},
    73909: {"weight": 2.3, "content": "coffee beans", "state": "arriving"},
    73910: {"weight": 18.7, "content": "sports equipment", "state": "in_transit"},
}


@app.get("/shipment/latest")
def get_last_shipment() -> dict[str, Any]:
    """Get the details of the latest shipment."""
    id = max(shipments.keys())
    return shipments[id]


@app.get("/shipment/", response_model=Shipment)
def get_shipment(id: int = None, status_code: int = status.HTTP_200_OK) -> dict[str, Any]:
    """Get the details of a shipment by its ID."""
    if not id:
        id = min(shipments.keys())
        return shipments[id]

    if id not in shipments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")

    return shipments[id]


@app.post("/shipment/")
def submit_shipment(shipment: Shipment) -> dict[str, Any]:
    """Create a new shipment with the given details."""
    if shipment.weight > 25 or shipment.weight <= 0:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail="Invalid weight. Must be between 0 kg and 25 kgs.",
        )

    new_id = max(shipments.keys()) + 1

    shipments[new_id] = {
        "weight": shipment.weight,
        "content": shipment.content,
        "state": shipment.state,
    }
    return {"id": new_id, "message": "Shipment created successfully"}


@app.get("/shipment/{field}")
def get_shipment_field(field: str, id: int) -> dict[str, Any]:
    """Get the details of a shipment by a specific field and value."""
    return {field: shipments[id][field]}


# @app.put("/shipment")
# def update_shipment(id: int, shipment: Shipment) -> dict[str, Any]:
#     """Update the details of a shipment by its ID."""
#     shipments[id] = {"weight": shipment.weight, "content": shipment.content, "state": shipment.state}
#     return shipments[id]


@app.patch("/shipment")
def update_shipment(id: int, body: dict[str, ShipmentState]) -> dict[str, Any]:
    """Update the details of a shipment by its ID. Only the fields provided in the request body will be updated."""
    shipments[id].update(body)
    return shipments[id]


@app.delete("/shipment")
def delete_shipment(id: int) -> dict[str, Any]:
    """Delete a shipment by its ID."""
    shipments.pop(id)
    return {"message": f"Shipment with ID #{id} deleted successfully"}


@app.get("/scalar", include_in_schema=False)
def get_scalar_docs() -> dict[str, Any]:
    """Get the documentation for the scalar-fastapi package."""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar FastAPI API Reference",
    )
