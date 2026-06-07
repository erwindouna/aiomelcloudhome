"""Air-to-Air (ATA) models for Melcloud Home."""

from enum import StrEnum
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_T = TypeVar("_T", bound=StrEnum)


class ATAOperationMode(StrEnum):
    """Operation mode for Air-to-Air units."""

    HEAT = "Heat"
    COOL = "Cool"
    AUTOMATIC = "Automatic"
    DRY = "Dry"
    FAN = "Fan"


class ATAFanSpeed(StrEnum):
    """Fan speed for Air-to-Air units."""

    OFF = "Off"
    AUTO = "Auto"
    ONE = "One"
    TWO = "Two"
    THREE = "Three"
    FOUR = "Four"
    FIVE = "Five"


class ATAVaneVertical(StrEnum):
    """Vertical vane direction for Air-to-Air units."""

    AUTO = "Auto"
    SWING = "Swing"
    ONE = "One"
    TWO = "Two"
    THREE = "Three"
    FOUR = "Four"
    FIVE = "Five"


class ATAVaneHorizontal(StrEnum):
    """Horizontal vane direction for Air-to-Air units."""

    AUTO = "Auto"
    SWING = "Swing"
    LEFT = "Left"
    LEFT_CENTRE = "LeftCentre"
    CENTRE = "Centre"
    RIGHT_CENTRE = "RightCentre"
    RIGHT = "Right"


class ATAUnitControl(BaseModel):
    """Control parameters for an Air-to-Air unit."""

    power: bool | None = None
    operation_mode: ATAOperationMode | None = None
    set_temperature: float | None = None
    set_fan_speed: ATAFanSpeed | None = None
    vane_vertical_direction: ATAVaneVertical | None = None
    vane_horizontal_direction: ATAVaneHorizontal | None = None
    in_standby_mode: bool | None = None

    def to_api_payload(self) -> dict[str, Any]:
        """Serialize to the API request body."""
        return {
            "power": self.power,
            "operationMode": self.operation_mode,
            "setTemperature": self.set_temperature,
            "setFanSpeed": self.set_fan_speed,
            "vaneVerticalDirection": self.vane_vertical_direction,
            "vaneHorizontalDirection": self.vane_horizontal_direction,
            "temperatureIncrementOverride": None,
            "inStandbyMode": self.in_standby_mode,
        }


class ATACapabilities(BaseModel):
    """Capabilities of an Air-to-Air unit."""

    model_config = ConfigDict(populate_by_name=True)

    number_of_fan_speeds: int | None = Field(default=None, alias="numberOfFanSpeeds")
    min_temp_heat: float | None = Field(default=None, alias="minTempHeat")
    max_temp_heat: float | None = Field(default=None, alias="maxTempHeat")
    min_temp_cool: float | None = Field(default=None, alias="minTempCool")
    max_temp_cool: float | None = Field(default=None, alias="maxTempCool")
    min_temp_auto: float | None = Field(default=None, alias="minTempAutomatic")
    max_temp_auto: float | None = Field(default=None, alias="maxTempAutomatic")
    has_half_degree_increments: bool | None = Field(default=None, alias="hasHalfDegreeIncrements")
    has_cool_operation_mode: bool | None = Field(default=None, alias="hasCoolOperationMode")
    has_dry_operation_mode: bool | None = Field(default=None, alias="hasDryOperationMode")
    has_fan_operation_mode: bool | None = Field(default=None, alias="hasFanOperationMode")
    has_auto_operation_mode: bool | None = Field(default=None, alias="hasAutoOperationMode")
    has_outdoor_temperature_sensor: bool | None = Field(default=None, alias="hasOutdoorTemperatureSensor")
    has_energy_consumed_meter: bool | None = Field(default=None, alias="hasEnergyConsumedMeter")
    has_vane_vertical: bool | None = Field(default=None, alias="hasVaneVertical")
    has_vane_horizontal: bool | None = Field(default=None, alias="hasVaneHorizontal")
    has_standby_mode: bool | None = Field(default=None, alias="hasStandbyMode")


class ATAUnit(BaseModel):
    """Represents an Air-to-Air unit."""

    id: str
    name: str
    power: bool | None = None
    operation_mode: ATAOperationMode | None = None
    set_temperature: float | None = None
    room_temperature: float | None = None
    set_fan_speed: ATAFanSpeed | None = None
    actual_fan_speed: ATAFanSpeed | None = None
    vane_vertical_direction: ATAVaneVertical | None = None
    vane_horizontal_direction: ATAVaneHorizontal | None = None
    in_standby_mode: bool | None = None
    is_in_error: bool | None = None
    raw_settings: list[dict[str, str]] = Field(default_factory=list, repr=False)
    settings: dict[str, Any] = Field(default_factory=dict, repr=False)
    rssi: int | None = None
    capabilities: ATACapabilities | None = None

    @field_validator("set_temperature", "room_temperature", mode="before")
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

        # type known keys in-place so the exported settings dict is typed
        for _key, _val in {
            "Power": _bool("Power"),
            "InStandbyMode": _bool("InStandbyMode"),
            "IsInError": _bool("IsInError"),
            "OperationMode": _enum(ATAOperationMode, "OperationMode"),
            "SetFanSpeed": _enum(ATAFanSpeed, "SetFanSpeed"),
            "ActualFanSpeed": _enum(ATAFanSpeed, "ActualFanSpeed"),
            "VaneVerticalDirection": _enum(ATAVaneVertical, "VaneVerticalDirection"),
            "VaneHorizontalDirection": _enum(ATAVaneHorizontal, "VaneHorizontalDirection"),
        }.items():
            if _key in settings:
                settings[_key] = _val

        capabilities_payload = data.get("capabilities")
        if isinstance(capabilities_payload, dict):
            capabilities_payload = dict(capabilities_payload)
            if "minTempCool" not in capabilities_payload and "minTempCoolDry" in capabilities_payload:
                capabilities_payload["minTempCool"] = capabilities_payload["minTempCoolDry"]
            if "maxTempCool" not in capabilities_payload and "maxTempCoolDry" in capabilities_payload:
                capabilities_payload["maxTempCool"] = capabilities_payload["maxTempCoolDry"]
            if "hasStandbyMode" not in capabilities_payload and "hasStandby" in capabilities_payload:
                capabilities_payload["hasStandbyMode"] = capabilities_payload["hasStandby"]
            if "hasVaneVertical" not in capabilities_payload and (
                "VaneVerticalDirection" in settings or capabilities_payload.get("hasAirDirection") is True
            ):
                capabilities_payload["hasVaneVertical"] = True
            if "hasVaneHorizontal" not in capabilities_payload and "VaneHorizontalDirection" in settings:
                capabilities_payload["hasVaneHorizontal"] = True

        return {
            "id": str(data["id"]),
            "name": data.get("givenDisplayName", ""),
            "power": settings.get("Power"),
            "operation_mode": settings.get("OperationMode"),
            "set_temperature": settings.get("SetTemperature"),
            "room_temperature": settings.get("RoomTemperature"),
            "set_fan_speed": settings.get("SetFanSpeed"),
            "actual_fan_speed": settings.get("ActualFanSpeed"),
            "vane_vertical_direction": settings.get("VaneVerticalDirection"),
            "vane_horizontal_direction": settings.get("VaneHorizontalDirection"),
            "in_standby_mode": settings.get("InStandbyMode"),
            "is_in_error": settings.get("IsInError"),
            "raw_settings": raw_settings,
            "settings": settings,
            "rssi": data.get("rssi"),
            "capabilities": ATACapabilities.model_validate(capabilities_payload) if capabilities_payload else None,
        }
