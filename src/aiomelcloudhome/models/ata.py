"""Air-to-Air (ATA) models for Melcloud Home."""

import re
from datetime import datetime
from enum import StrEnum
from typing import Any, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_T = TypeVar("_T", bound=StrEnum)
_UnitT = TypeVar("_UnitT", bound=BaseModel)

_CAMEL_TO_SNAKE = re.compile(r"(?<!^)(?=[A-Z])")


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


# WebSocketunitStateChanged frames encode enum settings as integer codes, whereas
# the REST context endpoint returns their string names.
# So yeah, we need to map it...
_ATA_OPERATION_MODE_BY_CODE: dict[int, ATAOperationMode] = {
    1: ATAOperationMode.HEAT,
    2: ATAOperationMode.DRY,
    3: ATAOperationMode.COOL,
    4: ATAOperationMode.FAN,
    5: ATAOperationMode.AUTOMATIC,
}
_ATA_FAN_SPEED_BY_CODE: dict[int, ATAFanSpeed] = {
    0: ATAFanSpeed.AUTO,
    1: ATAFanSpeed.ONE,
    2: ATAFanSpeed.TWO,
    3: ATAFanSpeed.THREE,
    4: ATAFanSpeed.FOUR,
    5: ATAFanSpeed.FIVE,
}
_ATA_VANE_VERTICAL_BY_CODE: dict[int, ATAVaneVertical] = {
    0: ATAVaneVertical.AUTO,
    1: ATAVaneVertical.ONE,
    2: ATAVaneVertical.TWO,
    3: ATAVaneVertical.THREE,
    4: ATAVaneVertical.FOUR,
    5: ATAVaneVertical.FIVE,
    6: ATAVaneVertical.SWING,
}
_ATA_VANE_HORIZONTAL_BY_CODE: dict[int, ATAVaneHorizontal] = {
    0: ATAVaneHorizontal.AUTO,
    1: ATAVaneHorizontal.LEFT,
    2: ATAVaneHorizontal.LEFT_CENTRE,
    3: ATAVaneHorizontal.CENTRE,
    4: ATAVaneHorizontal.RIGHT_CENTRE,
    5: ATAVaneHorizontal.RIGHT,
    7: ATAVaneHorizontal.SWING,
}

_ATA_BOOL_SETTINGS = frozenset({"Power", "InStandbyMode", "IsInError"})
_ATA_FLOAT_SETTINGS = frozenset({"SetTemperature", "RoomTemperature"})
_ATA_ENUM_SETTINGS: dict[str, tuple[type[StrEnum], dict[int, Any]]] = {
    "OperationMode": (ATAOperationMode, _ATA_OPERATION_MODE_BY_CODE),
    "SetFanSpeed": (ATAFanSpeed, _ATA_FAN_SPEED_BY_CODE),
    "ActualFanSpeed": (ATAFanSpeed, _ATA_FAN_SPEED_BY_CODE),
    "VaneVerticalDirection": (ATAVaneVertical, _ATA_VANE_VERTICAL_BY_CODE),
    "VaneHorizontalDirection": (ATAVaneHorizontal, _ATA_VANE_HORIZONTAL_BY_CODE),
}


def _coerce_bool_value(value: Any) -> bool | None:
    """Coerce a REST string or WebSocket bool into a bool."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def _coerce_float_value(value: Any) -> float | None:
    """Coerce a REST string or WebSocket number into a float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _decode_enum_value(enum_cls: type[_T], code_map: dict[int, _T], value: Any) -> _T | None:  # noqa: UP047  # PEP 695 syntax needs Python 3.12; library targets 3.11
    """Decode a setting value that may arrive as an integer code (WebSocket) or a name (REST)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return code_map.get(value)
    text = str(value).strip()
    if text.lstrip("-").isdigit():
        return code_map.get(int(text))
    try:
        return enum_cls(text)
    except ValueError:
        return None


def decode_ata_setting(name: str, value: Any) -> Any:
    """Decode a single ATA setting value into its typed form."""
    if name in _ATA_BOOL_SETTINGS:
        return _coerce_bool_value(value)
    if name in _ATA_FLOAT_SETTINGS:
        return _coerce_float_value(value)
    enum_spec = _ATA_ENUM_SETTINGS.get(name)
    if enum_spec is not None:
        enum_cls, code_map = enum_spec
        return _decode_enum_value(enum_cls, code_map, value)
    return value


def _apply_unit_changes(unit: _UnitT, settings: dict[str, Any], changes: dict[str, Any]) -> _UnitT:  # noqa: UP047
    """Return a copy of ``unit`` with decoded realtime changes applied, or ``unit`` itself if none apply."""
    applied = {name: value for name, value in changes.items() if value is not None}
    if not applied:
        return unit
    updates: dict[str, Any] = {
        field: value for name, value in applied.items() if (field := _CAMEL_TO_SNAKE.sub("_", name).lower()) in type(unit).model_fields
    }
    return unit.model_copy(update={**updates, "settings": {**settings, **applied}})


class HolidayMode(BaseModel):
    """Holiday mode state and schedule for a unit."""

    active: bool = False
    enabled: bool = False
    start_date: datetime | None = Field(default=None, alias="startDate")
    end_date: datetime | None = Field(default=None, alias="endDate")

    model_config = ConfigDict(populate_by_name=True)


class FrostProtection(BaseModel):
    """Frost protection state and settings for an ATA unit."""

    active: bool = False
    enabled: bool = False
    min: float = 0.0
    max: float = 0.0


class OverheatProtection(BaseModel):
    """Overheat protection state and settings for an ATA unit."""

    active: bool = False
    enabled: bool = False
    min: float = 0.0
    max: float = 0.0


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
    frost_protection: FrostProtection | None = None
    overheat_protection: OverheatProtection | None = None
    holiday_mode: HolidayMode | None = None

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

        # type known keys in-place so the exported settings dict is typed
        _typed_keys = (
            "Power",
            "InStandbyMode",
            "IsInError",
            "OperationMode",
            "SetFanSpeed",
            "ActualFanSpeed",
            "VaneVerticalDirection",
            "VaneHorizontalDirection",
        )
        for _key in _typed_keys:
            if _key in settings:
                settings[_key] = decode_ata_setting(_key, settings[_key])

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
            "frost_protection": FrostProtection.model_validate(data["frostProtection"]) if data.get("frostProtection") else None,
            "overheat_protection": OverheatProtection.model_validate(data["overheatProtection"]) if data.get("overheatProtection") else None,
            "holiday_mode": HolidayMode.model_validate(data["holidayMode"]) if data.get("holidayMode") else None,
        }

    def apply_delta(self, changes: dict[str, Any]) -> Self:
        """Return a copy of this unit with decoded realtime setting changes applied.

        ``changes`` is the decoded mapping carried by a ``UnitStateDelta``.
        ``None`` values (undecodable codes) are skipped so they never wipe known
        state; unknown setting names are only merged into ``settings``. Returns
        the unit itself when nothing applies.
        """
        return _apply_unit_changes(self, self.settings, changes)
