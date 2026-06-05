"""Air-to-Air (ATA) models for Melcloud Home."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import cast

from mashumaro import field_options
from mashumaro.mixins.orjson import DataClassORJSONMixin


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


@dataclass(slots=True, kw_only=True)
class ATACapabilities(DataClassORJSONMixin):
    """Capabilities of an Air-to-Air unit."""

    number_of_fan_speeds: int | None = field(default=None, metadata=field_options(alias="numberOfFanSpeeds"))
    min_temp_heat: float | None = field(default=None, metadata=field_options(alias="minTempHeat"))
    max_temp_heat: float | None = field(default=None, metadata=field_options(alias="maxTempHeat"))
    min_temp_cool: float | None = field(default=None, metadata=field_options(alias="minTempCool"))
    max_temp_cool: float | None = field(default=None, metadata=field_options(alias="maxTempCool"))
    min_temp_auto: float | None = field(default=None, metadata=field_options(alias="minTempAutomatic"))
    max_temp_auto: float | None = field(default=None, metadata=field_options(alias="maxTempAutomatic"))
    has_half_degree_increments: bool | None = field(default=None, metadata=field_options(alias="hasHalfDegreeIncrements"))
    has_cool_operation_mode: bool | None = field(default=None, metadata=field_options(alias="hasCoolOperationMode"))
    has_dry_operation_mode: bool | None = field(default=None, metadata=field_options(alias="hasDryOperationMode"))
    has_fan_operation_mode: bool | None = field(default=None, metadata=field_options(alias="hasFanOperationMode"))
    has_auto_operation_mode: bool | None = field(default=None, metadata=field_options(alias="hasAutoOperationMode"))
    has_outdoor_temperature_sensor: bool | None = field(default=None, metadata=field_options(alias="hasOutdoorTemperatureSensor"))
    has_energy_consumed_meter: bool | None = field(default=None, metadata=field_options(alias="hasEnergyConsumedMeter"))
    has_vane_vertical: bool | None = field(default=None, metadata=field_options(alias="hasVaneVertical"))
    has_vane_horizontal: bool | None = field(default=None, metadata=field_options(alias="hasVaneHorizontal"))
    has_standby_mode: bool | None = field(default=None, metadata=field_options(alias="hasStandbyMode"))


@dataclass(slots=True, kw_only=True)
class ATAUnit:
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

    @classmethod
    def from_api(cls, data: dict[str, object]) -> ATAUnit:
        """Construct an ATAUnit from the raw API context response."""
        settings: dict[str, str] = {s["name"]: s["value"] for s in cast("list[dict[str, str]]", data.get("settings", []))}

        capabilities: ATACapabilities | None = None
        if raw_caps := data.get("capabilities"):
            capabilities = ATACapabilities.from_dict(raw_caps)  # type: ignore[arg-type]

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

        return cls(
            id=str(data["id"]),
            name=str(data.get("givenDisplayName", "")),
            power=_bool(settings.get("Power")),
            operation_mode=ATAOperationMode(settings["OperationMode"]) if "OperationMode" in settings else None,
            set_temperature=_float(settings.get("SetTemperature")),
            room_temperature=_float(settings.get("RoomTemperature")),
            set_fan_speed=ATAFanSpeed(settings["SetFanSpeed"]) if "SetFanSpeed" in settings else None,
            vane_vertical_direction=ATAVaneVertical(settings["VaneVerticalDirection"]) if "VaneVerticalDirection" in settings else None,
            vane_horizontal_direction=ATAVaneHorizontal(settings["VaneHorizontalDirection"]) if "VaneHorizontalDirection" in settings else None,
            in_standby_mode=_bool(settings.get("InStandbyMode")),
            is_in_error=_bool(settings.get("IsInError")),
            rssi=_int(str(data["rssi"])) if "rssi" in data else None,
            capabilities=capabilities,
        )
