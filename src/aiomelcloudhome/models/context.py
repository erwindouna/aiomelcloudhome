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

    id: str | None = Field(default=None, alias="id")
    first_name: str | None = Field(default=None, alias="firstname")
    last_name: str | None = Field(default=None, alias="lastname")
    email: str | None = Field(default=None, alias="email")
    number_of_devices_allowed: int | None = Field(default=None, alias="numberOfDevicesAllowed")
    number_of_buildings_allowed: int | None = Field(default=None, alias="numberOfBuildingsAllowed")
    number_of_guests_allowed_per_unit: int | None = Field(default=None, alias="numberOfGuestUsersAllowedPerUnit")
    number_of_guest_devices_allowed: int | None = Field(default=None, alias="numberOfGuestDevicesAllowed")

    buildings: list[Building]

    @model_validator(mode="before")
    @classmethod
    def _merge_buildings(cls, data: dict[str, Any]) -> dict[str, Any]:
        buildings = list(data.get("buildings", []))
        buildings.extend(data.get("guestBuildings", []))
        return {**data, "buildings": buildings}
