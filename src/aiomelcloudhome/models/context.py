"""Context models for Melcloud Home."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ata import ATAUnit
from .atw import ATWUnit


class Building(BaseModel):
    """Represents a building containing Melcloud Home units."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    air_to_air_units: list[ATAUnit] = Field(default_factory=list, alias="airToAirUnits")
    air_to_water_units: list[ATWUnit] = Field(default_factory=list, alias="airToWaterUnits")


class UserContext(BaseModel):
    """Represents the full user context returned by GET /context."""

    buildings: list[Building]

    @model_validator(mode="before")
    @classmethod
    def _merge_buildings(cls, data: dict[str, Any]) -> dict[str, Any]:
        buildings = list(data.get("buildings", []))
        buildings.extend(data.get("guestBuildings", []))
        return {"buildings": buildings}
