"""Air-to-Air (ATA) models for Melcloud Home."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ATAOperationMode(StrEnum):
    """Operation mode for Air-to-Air units."""

    HEAT = "Heat"
    COOL = "Cool"
    AUTOMATIC = "Automatic"
    DRY = "Dry"
    FAN = "Fan"


class ATAFanSpeed(StrEnum):
    """Fan speed for Air-to-Air units."""

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
    vane_vertical_direction: ATAVaneVertical | None = None
    vane_horizontal_direction: ATAVaneHorizontal | None = None
    in_standby_mode: bool | None = None
    is_in_error: bool | None = None
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
        settings: dict[str, str] = {setting["name"]: setting["value"] for setting in data.get("settings", [])}
        return {
            "id": str(data["id"]),
            "name": data.get("givenDisplayName", ""),
            "power": settings.get("Power"),
            "operation_mode": settings.get("OperationMode"),
            "set_temperature": settings.get("SetTemperature"),
            "room_temperature": settings.get("RoomTemperature"),
            "set_fan_speed": settings.get("SetFanSpeed"),
            "vane_vertical_direction": settings.get("VaneVerticalDirection"),
            "vane_horizontal_direction": settings.get("VaneHorizontalDirection"),
            "in_standby_mode": settings.get("InStandbyMode"),
            "is_in_error": settings.get("IsInError"),
            "rssi": data.get("rssi"),
            "capabilities": ATACapabilities.model_validate(data.get("capabilities")) if data.get("capabilities") else None,
        }
