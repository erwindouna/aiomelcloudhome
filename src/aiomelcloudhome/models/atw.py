"""Air-to-Water (ATW) models for Melcloud Home."""

from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .ata import FrostProtection, HolidayMode, OverheatProtection

_T = TypeVar("_T", bound=StrEnum)


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


class ATWUnitControl(BaseModel):
    """Control parameters for an Air-to-Water unit."""

    power: bool | None = None
    operation_mode_zone1: ATWZoneMode | None = None
    operation_mode_zone2: ATWZoneMode | None = None
    set_temperature_zone1: float | None = None
    set_temperature_zone2: float | None = None
    set_tank_water_temperature: float | None = None
    forced_hot_water_mode: bool | None = None
    in_standby_mode: bool | None = None
    set_heat_flow_temperature_zone1: float | None = None
    set_cool_flow_temperature_zone1: float | None = None
    set_heat_flow_temperature_zone2: float | None = None
    set_cool_flow_temperature_zone2: float | None = None

    def to_api_payload(self) -> dict[str, Any]:
        """Serialize to the API request body."""
        return {
            "power": self.power,
            "setTemperatureZone1": self.set_temperature_zone1,
            "setTemperatureZone2": self.set_temperature_zone2,
            "operationModeZone1": self.operation_mode_zone1,
            "operationModeZone2": self.operation_mode_zone2,
            "setTankWaterTemperature": self.set_tank_water_temperature,
            "forcedHotWaterMode": self.forced_hot_water_mode,
            "inStandbyMode": self.in_standby_mode,
            "setHeatFlowTemperatureZone1": self.set_heat_flow_temperature_zone1,
            "setCoolFlowTemperatureZone1": self.set_cool_flow_temperature_zone1,
            "setHeatFlowTemperatureZone2": self.set_heat_flow_temperature_zone2,
            "setCoolFlowTemperatureZone2": self.set_cool_flow_temperature_zone2,
        }


class ATWCapabilities(BaseModel):
    """Capabilities of an Air-to-Water unit."""

    model_config = ConfigDict(populate_by_name=True)

    has_hot_water: bool | None = Field(default=None, alias="hasHotWater")
    has_zone2: bool | None = Field(default=None, alias="hasZone2")
    has_half_degrees: bool | None = Field(default=None, alias="hasHalfDegrees")
    has_cooling_mode: bool | None = Field(default=None, alias="hasCoolingMode")
    min_set_tank_temperature: float | None = Field(default=None, alias="minSetTankTemperature")
    max_set_tank_temperature: float | None = Field(default=None, alias="maxSetTankTemperature")
    min_set_temperature_zone1: float | None = Field(default=None, alias="minSetTemperatureZone1")
    max_set_temperature_zone1: float | None = Field(default=None, alias="maxSetTemperatureZone1")
    min_set_temperature_zone2: float | None = Field(default=None, alias="minSetTemperatureZone2")
    max_set_temperature_zone2: float | None = Field(default=None, alias="maxSetTemperatureZone2")
    has_standby_mode: bool | None = Field(default=None, alias="hasStandbyMode")
    has_energy_consumed_meter: bool | None = Field(default=None, alias="hasEnergyConsumedMeter")


class ATWUnit(BaseModel):
    """Represents an Air-to-Water unit."""

    id: str
    name: str
    power: bool | None = None
    in_standby_mode: bool | None = None
    operation_mode: ATWOperationMode | None = None
    operation_mode_zone1: ATWZoneMode | None = None
    set_temperature_zone1: float | None = None
    room_temperature_zone1: float | None = None
    has_zone2: bool | None = None
    operation_mode_zone2: ATWZoneMode | None = None
    set_temperature_zone2: float | None = None
    room_temperature_zone2: float | None = None
    set_tank_water_temperature: float | None = None
    tank_water_temperature: float | None = None
    forced_hot_water_mode: bool | None = None
    is_in_error: bool | None = None
    raw_settings: list[dict[str, str]] = Field(default_factory=list, repr=False)
    settings: dict[str, Any] = Field(default_factory=dict, repr=False)
    rssi: int | None = None
    capabilities: ATWCapabilities | None = None
    frost_protection: FrostProtection | None = None
    overheat_protection: OverheatProtection | None = None
    holiday_mode: HolidayMode | None = None

    @field_validator(
        "set_temperature_zone1",
        "room_temperature_zone1",
        "set_temperature_zone2",
        "room_temperature_zone2",
        "set_tank_water_temperature",
        "tank_water_temperature",
        mode="before",
    )
    @classmethod
    def _coerce_float(cls, v: Any) -> Any:
        if v is None:
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator("rssi", mode="before")
    @classmethod
    def _coerce_int(cls, v: Any) -> Any:
        if v is None:
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    @model_validator(mode="before")
    @classmethod
    def _from_api(cls, data: dict[str, Any]) -> dict[str, Any]:
        raw_settings: list[dict[str, str]] = [{"name": str(s["name"]), "value": str(s["value"])} for s in data.get("settings", [])]
        settings: dict[str, Any] = {s["name"]: s["value"] for s in raw_settings}

        def _bool(key: str) -> bool | None:
            v = settings.get(key)
            return None if v is None else str(v).lower() == "true"

        def _enum(enum_cls: type[_T], key: str) -> _T | None:
            v = settings.get(key)
            if v is None:
                return None
            try:
                return enum_cls(v)
            except ValueError:
                return None

        for _key, _val in {
            "Power": _bool("Power"),
            "InStandbyMode": _bool("InStandbyMode"),
            "HasZone2": _bool("HasZone2"),
            "ForcedHotWaterMode": _bool("ForcedHotWaterMode"),
            "IsInError": _bool("IsInError"),
            "OperationMode": _enum(ATWOperationMode, "OperationMode"),
            "OperationModeZone1": _enum(ATWZoneMode, "OperationModeZone1"),
            "OperationModeZone2": _enum(ATWZoneMode, "OperationModeZone2"),
        }.items():
            if _key in settings:
                settings[_key] = _val

        return {
            "id": str(data["id"]),
            "name": data.get("givenDisplayName", ""),
            "power": settings.get("Power"),
            "in_standby_mode": settings.get("InStandbyMode"),
            "operation_mode": settings.get("OperationMode"),
            "operation_mode_zone1": settings.get("OperationModeZone1"),
            "set_temperature_zone1": settings.get("SetTemperatureZone1"),
            "room_temperature_zone1": settings.get("RoomTemperatureZone1"),
            "has_zone2": settings.get("HasZone2"),
            "operation_mode_zone2": settings.get("OperationModeZone2"),
            "set_temperature_zone2": settings.get("SetTemperatureZone2"),
            "room_temperature_zone2": settings.get("RoomTemperatureZone2"),
            "set_tank_water_temperature": settings.get("SetTankWaterTemperature"),
            "tank_water_temperature": settings.get("TankWaterTemperature"),
            "forced_hot_water_mode": settings.get("ForcedHotWaterMode"),
            "is_in_error": settings.get("IsInError"),
            "raw_settings": raw_settings,
            "settings": settings,
            "rssi": data.get("rssi"),
            "capabilities": ATWCapabilities.model_validate(data.get("capabilities")) if data.get("capabilities") else None,
            "frost_protection": FrostProtection.model_validate(data["frostProtection"]) if data.get("frostProtection") else None,
            "overheat_protection": OverheatProtection.model_validate(data["overheatProtection"]) if data.get("overheatProtection") else None,
            "holiday_mode": HolidayMode.model_validate(data["holidayMode"]) if data.get("holidayMode") else None,
        }
