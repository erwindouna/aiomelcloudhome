"""Air-to-Water (ATW) models for Melcloud Home."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from mashumaro import field_options
from mashumaro.mixins.orjson import DataClassORJSONMixin


class ATWOperationMode(StrEnum):
    """Overall operation mode for Air-to-Water units."""

    STOP = "Stop"
    HOT_WATER = "HotWater"
    HEAT_ZONES = "HeatZones"
    COOL = "Cool"


class ATWZoneMode(StrEnum):
    """Zone heating/cooling strategy for Air-to-Water units."""

    HEAT_ROOM_TEMPERATURE = "HeatRoomTemperature"
    HEAT_FLOW_TEMPERATURE = "HeatFlowTemperature"
    HEAT_CURVE = "HeatCurve"
    COOL_ROOM_TEMPERATURE = "CoolRoomTemperature"
    COOL_FLOW_TEMPERATURE = "CoolFlowTemperature"


@dataclass(slots=True, kw_only=True)
class ATWCapabilities(DataClassORJSONMixin):
    """Capabilities of an Air-to-Water unit."""

    has_hot_water: bool | None = field(default=None, metadata=field_options(alias="hasHotWater"))
    has_zone2: bool | None = field(default=None, metadata=field_options(alias="hasZone2"))
    has_half_degrees: bool | None = field(default=None, metadata=field_options(alias="hasHalfDegrees"))
    has_cooling_mode: bool | None = field(default=None, metadata=field_options(alias="hasCoolingMode"))
    min_set_tank_temperature: float | None = field(default=None, metadata=field_options(alias="minSetTankTemperature"))
    max_set_tank_temperature: float | None = field(default=None, metadata=field_options(alias="maxSetTankTemperature"))
    min_set_temperature_zone1: float | None = field(default=None, metadata=field_options(alias="minSetTemperatureZone1"))
    max_set_temperature_zone1: float | None = field(default=None, metadata=field_options(alias="maxSetTemperatureZone1"))
    min_set_temperature_zone2: float | None = field(default=None, metadata=field_options(alias="minSetTemperatureZone2"))
    max_set_temperature_zone2: float | None = field(default=None, metadata=field_options(alias="maxSetTemperatureZone2"))
    has_standby_mode: bool | None = field(default=None, metadata=field_options(alias="hasStandbyMode"))
    has_energy_consumed_meter: bool | None = field(default=None, metadata=field_options(alias="hasEnergyConsumedMeter"))


@dataclass(slots=True, kw_only=True)
class ATWUnit:
    """Represents an Air-to-Water unit."""

    id: str
    name: str
    power: bool | None = None
    in_standby_mode: bool | None = None
    operation_mode: ATWOperationMode | None = None
    # Zone 1
    operation_mode_zone1: ATWZoneMode | None = None
    set_temperature_zone1: float | None = None
    room_temperature_zone1: float | None = None
    # Zone 2
    has_zone2: bool | None = None
    operation_mode_zone2: ATWZoneMode | None = None
    set_temperature_zone2: float | None = None
    room_temperature_zone2: float | None = None
    # Domestic hot water
    set_tank_water_temperature: float | None = None
    tank_water_temperature: float | None = None
    forced_hot_water_mode: bool | None = None
    # Status
    is_in_error: bool | None = None
    rssi: int | None = None
    capabilities: ATWCapabilities | None = None

    @classmethod
    def from_api(cls, data: dict[str, object]) -> ATWUnit:
        """Construct an ATWUnit from the raw API context response."""
        settings: dict[str, str] = {s["name"]: s["value"] for s in cast("list[dict[str, str]]", data.get("settings", []))}

        capabilities: ATWCapabilities | None = None
        if raw_caps := data.get("capabilities"):
            capabilities = ATWCapabilities.from_dict(raw_caps)  # type: ignore[arg-type]

        def _bool(val: str | None) -> bool | None:
            if val is None:
                return None
            return val.lower() == "true"

        def _float(val: str | None) -> float | None:
            if val is None:
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        def _int(val: str | None) -> int | None:
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        def _zone_mode(val: str | None) -> ATWZoneMode | None:
            if val is None:
                return None
            try:
                return ATWZoneMode(val)
            except ValueError:
                return None

        has_zone2_raw = settings.get("HasZone2")
        has_zone2 = has_zone2_raw not in (None, "0", "False", "false") if has_zone2_raw is not None else None

        return cls(
            id=str(data["id"]),
            name=str(data.get("givenDisplayName", "")),
            power=_bool(settings.get("Power")),
            in_standby_mode=_bool(settings.get("InStandbyMode")),
            operation_mode=ATWOperationMode(settings["OperationMode"]) if "OperationMode" in settings else None,
            operation_mode_zone1=_zone_mode(settings.get("OperationModeZone1")),
            set_temperature_zone1=_float(settings.get("SetTemperatureZone1")),
            room_temperature_zone1=_float(settings.get("RoomTemperatureZone1")),
            has_zone2=has_zone2,
            operation_mode_zone2=_zone_mode(settings.get("OperationModeZone2")),
            set_temperature_zone2=_float(settings.get("SetTemperatureZone2")),
            room_temperature_zone2=_float(settings.get("RoomTemperatureZone2")),
            set_tank_water_temperature=_float(settings.get("SetTankWaterTemperature")),
            tank_water_temperature=_float(settings.get("TankWaterTemperature")),
            forced_hot_water_mode=_bool(settings.get("ForcedHotWaterMode")),
            is_in_error=_bool(settings.get("IsInError")),
            rssi=_int(str(data["rssi"])) if "rssi" in data else None,
            capabilities=capabilities,
        )
