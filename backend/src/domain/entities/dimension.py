from pydantic import BaseModel, Field
from ..enums.unit import Unit


class Dimension(BaseModel):
    width: float = Field(..., description="Width of the product")
    height: float = Field(..., description="Height of the product")
    depth: float = Field(..., description="Depth of the product")
    unit: Unit = Field(..., description="Unit of measurement, e.g., inches, cm")