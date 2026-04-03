from enum import Enum
from random import randint

from pydantic import BaseModel, Field


def random_destination() -> int:
    """Generate a random 5-digit destination zip code."""
    return randint(10000, 99999)


class ShipmentState(str, Enum):
    """Enumeration of possible shipment states."""

    arriving = "arriving"
    placed = "placed"
    in_transit = "in_transit"
    delivered = "delivered"
    out_for_delivery = "out_for_delivery"


class Shipment(BaseModel):
    """Pydantic model representing a shipment."""

    weight: float = Field(description="Weight of the shipment", gt=0, le=25)
    content: str = Field(description="Content of the shipment", min_length=1, max_length=30)
    destination: int | None = Field(
        description="Destination zip code", default_factory=random_destination
    )
    state: ShipmentState = Field(description="Current state of the shipment")
