from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference
from typing import Any

app = FastAPI()

shipments ={
    73904: {
        "weight": 0.5,
        "content": "wine",
        "status": "arriving"
    },
    73905: {
        "weight": 3.2,
        "content": "smartphones",
        "status": "in transit"
    },
    73906: {
        "weight": 7.8,
        "content": "garden tools",
        "status": "delivered"
    },
    73907: {
        "weight": 0.9,
        "content": "cosmetics",
        "status": "preparing"
    },
    73908: {
        "weight": 15.0,
        "content": "industrial parts",
        "status": "on hold"
    },
    73909: {
        "weight": 2.3,
        "content": "coffee beans",
        "status": "arriving"
    },
    73910: {
        "weight": 18.7,
        "content": "sports equipment",
        "status": "in transit"
    },
}

@app.get("/shipment/latest")
def get_last_shipment() -> dict[str, Any]:
    """Get the details of the latest shipment."""
    id = max(shipments.keys())
    return shipments[id]

@app.get("/shipment/")
def get_shipment(id: int | None = None) -> dict[str, Any]:
    """Get the details of a shipment by its ID."""
    if not id:
        id = min(shipments.keys())
        return shipments[id]

    if id not in shipments:
        return {"error": "Shipment not found"}
    return shipments[id]

@app.get("/scalar", include_in_schema=False)
def get_scalar_docs() -> dict[str, Any]:
    """Get the documentation for the scalar-fastapi package."""
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar FastAPI API Reference",
    )
