"""Context models for Melcloud Home."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .ata import ATAUnit
from .atw import ATWUnit


@dataclass(slots=True, kw_only=True)
class Building:
    """Represents a building containing Melcloud Home units."""

    id: str
    name: str
    air_to_air_units: list[ATAUnit]
    air_to_water_units: list[ATWUnit]

    @classmethod
    def from_api(cls, data: dict[str, object]) -> Building:
        """Construct a Building from the raw API context response."""
        ata_units = [ATAUnit.from_api(u) for u in cast("list[dict[str, object]]", data.get("airToAirUnits", []))]
        atw_units = [ATWUnit.from_api(u) for u in cast("list[dict[str, object]]", data.get("airToWaterUnits", []))]
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "")),
            air_to_air_units=ata_units,
            air_to_water_units=atw_units,
        )


@dataclass(slots=True, kw_only=True)
class UserContext:
    """Represents the full user context returned by GET /context."""

    buildings: list[Building]

    @classmethod
    def from_api(cls, data: dict[str, object]) -> UserContext:
        """Construct a UserContext from the raw API context response."""
        all_buildings: list[dict[str, object]] = list(cast("list[dict[str, object]]", data.get("buildings", [])))
        all_buildings.extend(cast("list[dict[str, object]]", data.get("guestBuildings", [])))
        return cls(buildings=[Building.from_api(b) for b in all_buildings])
