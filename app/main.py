from typing import Any

from fastapi import FastAPI, HTTPException, status
from scalar_fastapi import get_scalar_api_reference

app = FastAPI()

shipments = {
    73904: {"weight": 0.5, "content": "wine", "state": "arriving"},
    73905: {"weight": 3.2, "content": "smartphones", "state": "in transit"},
    73906: {"weight": 7.8, "content": "garden tools", "state": "delivered"},
    73907: {"weight": 0.9, "content": "cosmetics", "state": "preparing"},
    73908: {"weight": 15.0, "content": "industrial parts", "state": "on hold"},
    73909: {"weight": 2.3, "content": "coffee beans", "state": "arriving"},
    73910: {"weight": 18.7, "content": "sports equipment", "state": "in transit"},
}


@app.get("/shipment/latest")
def get_last_shipment() -> dict[str, Any]:
    """Get the details of the latest shipment."""
    id = max(shipments.keys())
    return shipments[id]


@app.get("/shipment/")
def get_shipment(id: int = None, status_code: int = status.HTTP_200_OK) -> dict[str, Any]:
    """Get the details of a shipment by its ID."""
    if not id:
        id = min(shipments.keys())
        return shipments[id]

    if id not in shipments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
        return {"error": "Shipment not found"}
    return shipments[id]


@app.post("/shipment/")
def submit_shipment(data: dict[str, Any]) -> dict[str, Any]:
    """Create a new shipment with the given details."""
    weight = data.get("weight")
    content = data.get("content")
    state = data.get("state")
    if weight > 25 or weight <= 0:
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE, detail="Invalid weight. Must be between 0 kg and 25 kgs."
        )

    new_id = max(shipments.keys()) + 1

    shipments[new_id] = {"weight": weight, "content": content, "state": state}
    return {"id": new_id, "message": "Shipment created successfully"}


@app.get("/shipment/{field}")
def get_shipment_field(field: str, id: int) -> dict[str, Any]:
    """Get the details of a shipment by a specific field and value."""
    return {field: shipments[id][field]}


@app.put("/shipment")
def update_shipment(id: int, data: dict[str, Any]) -> dict[str, Any]:
    """Update the details of a shipment by its ID."""
    if id not in shipments:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found")
    shipments[id].update(data)
    return {"message": "Shipment updated successfully"}


@app.get("/scalar", include_in_schema=False)
def get_scalar_docs() -> dict[str, Any]:
    """Get the documentation for the scalar-fastapi package."""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar FastAPI API Reference",
    )
