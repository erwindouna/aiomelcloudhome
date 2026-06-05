"""Tests for Melcloud Home data models."""

from __future__ import annotations

from typing import Any, cast

import pytest

from aiomelcloudhome.models.ata import ATAFanSpeed, ATAOperationMode, ATAUnit, ATAVaneHorizontal, ATAVaneVertical
from aiomelcloudhome.models.atw import ATWOperationMode, ATWUnit, ATWZoneMode
from aiomelcloudhome.models.context import Building, UserContext
from tests import load_fixture


@pytest.fixture(name="context_data")
def context_data_fixture() -> dict[str, Any]:
    """Return the context fixture data."""
    return load_fixture("context.json")


def test_user_context_from_api(context_data: dict[str, Any]) -> None:
    """Test building a UserContext from the API response."""
    ctx = UserContext.from_api(context_data)
    assert len(ctx.buildings) == 1
    building = ctx.buildings[0]
    assert building.id == "building-uuid-1"
    assert building.name == "My Home"
    assert len(building.air_to_air_units) == 1
    assert len(building.air_to_water_units) == 1


def test_ata_unit_from_api(context_data: dict[str, Any]) -> None:
    """Test parsing an ATA unit from the API settings array."""
    raw = context_data["buildings"][0]["airToAirUnits"][0]
    unit = ATAUnit.from_api(raw)

    assert unit.id == "ata-unit-uuid-1"
    assert unit.name == "Living Room AC"
    assert unit.power is True
    assert unit.operation_mode == ATAOperationMode.HEAT
    assert unit.set_temperature == 21.0
    assert unit.room_temperature == 20.0
    assert unit.set_fan_speed == ATAFanSpeed.AUTO
    assert unit.vane_vertical_direction == ATAVaneVertical.AUTO
    assert unit.vane_horizontal_direction == ATAVaneHorizontal.CENTRE
    assert unit.in_standby_mode is False
    assert unit.is_in_error is False
    assert unit.rssi == -45


def test_ata_unit_capabilities(context_data: dict[str, Any]) -> None:
    """Test that ATA unit capabilities are parsed correctly."""
    raw = context_data["buildings"][0]["airToAirUnits"][0]
    unit = ATAUnit.from_api(raw)
    caps = unit.capabilities
    assert caps is not None
    assert caps.number_of_fan_speeds == 5
    assert caps.min_temp_heat == 10.0
    assert caps.max_temp_heat == 31.0
    assert caps.has_half_degree_increments is True
    assert caps.has_cool_operation_mode is True
    assert caps.has_outdoor_temperature_sensor is False


def test_atw_unit_from_api(context_data: dict[str, Any]) -> None:
    """Test parsing an ATW unit from the API settings array."""
    raw = context_data["buildings"][0]["airToWaterUnits"][0]
    unit = ATWUnit.from_api(raw)

    assert unit.id == "atw-unit-uuid-1"
    assert unit.name == "Heat Pump"
    assert unit.power is True
    assert unit.operation_mode == ATWOperationMode.HEAT_ZONES
    assert unit.operation_mode_zone1 == ATWZoneMode.HEAT_ROOM_TEMPERATURE
    assert unit.set_temperature_zone1 == 21.0
    assert unit.room_temperature_zone1 == 20.0
    assert unit.set_tank_water_temperature == 50.0
    assert unit.tank_water_temperature == 48.0
    assert unit.forced_hot_water_mode is False
    assert unit.has_zone2 is False
    assert unit.in_standby_mode is False
    assert unit.is_in_error is False
    assert unit.rssi == -52


def test_atw_unit_capabilities(context_data: dict[str, Any]) -> None:
    """Test that ATW unit capabilities are parsed correctly."""
    raw = context_data["buildings"][0]["airToWaterUnits"][0]
    unit = ATWUnit.from_api(raw)
    caps = unit.capabilities
    assert caps is not None
    assert caps.has_hot_water is True
    assert caps.has_zone2 is False
    assert caps.has_cooling_mode is False
    assert caps.min_set_tank_temperature == 40.0
    assert caps.max_set_tank_temperature == 60.0


def test_user_context_guest_buildings() -> None:
    """Test that guest buildings are included in the UserContext."""
    data = {
        "buildings": [],
        "guestBuildings": [
            {
                "id": "guest-building-1",
                "name": "Guest Home",
                "airToAirUnits": [],
                "airToWaterUnits": [],
            }
        ],
    }
    ctx = UserContext.from_api(cast("dict[str, object]", data))
    assert len(ctx.buildings) == 1
    assert ctx.buildings[0].id == "guest-building-1"


def test_building_from_api() -> None:
    """Test building a Building model with mixed unit types."""
    data = {
        "id": "test-building",
        "name": "Test Building",
        "airToAirUnits": [],
        "airToWaterUnits": [],
    }
    building = Building.from_api(cast("dict[str, object]", data))
    assert building.id == "test-building"
    assert not building.air_to_air_units
    assert not building.air_to_water_units


def test_ata_operation_mode_values() -> None:
    """Test that all ATA operation mode enum values are correct."""
    assert ATAOperationMode.HEAT == "Heat"
    assert ATAOperationMode.COOL == "Cool"
    assert ATAOperationMode.AUTOMATIC == "Automatic"
    assert ATAOperationMode.DRY == "Dry"
    assert ATAOperationMode.FAN == "Fan"


def test_atw_zone_mode_values() -> None:
    """Test that all ATW zone mode enum values are correct."""
    assert ATWZoneMode.HEAT_ROOM_TEMPERATURE == "HeatRoomTemperature"
    assert ATWZoneMode.HEAT_FLOW_TEMPERATURE == "HeatFlowTemperature"
    assert ATWZoneMode.HEAT_CURVE == "HeatCurve"
    assert ATWZoneMode.COOL_ROOM_TEMPERATURE == "CoolRoomTemperature"
    assert ATWZoneMode.COOL_FLOW_TEMPERATURE == "CoolFlowTemperature"


def test_ata_unit_missing_optional_settings() -> None:
    """Test that an ATA unit with minimal settings is handled gracefully."""
    raw = {
        "id": "minimal-unit",
        "givenDisplayName": "Minimal AC",
        "settings": [
            {"name": "Power", "value": "False"},
        ],
    }
    unit = ATAUnit.from_api(cast("dict[str, object]", raw))
    assert unit.id == "minimal-unit"
    assert unit.power is False
    assert unit.operation_mode is None
    assert unit.set_temperature is None
    assert unit.rssi is None
    assert unit.capabilities is None
