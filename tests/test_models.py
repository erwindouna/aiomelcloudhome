"""Tests for Melcloud Home data models."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome.models.ata import (
    ATAFanSpeed,
    ATAOperationMode,
    ATAUnit,
    ATAUnitControl,
    ATAVaneHorizontal,
    ATAVaneVertical,
)
from aiomelcloudhome.models.atw import ATWUnit
from aiomelcloudhome.models.context import Building, UserContext
from tests import load_fixture


@pytest.fixture(name="context_data")
def context_data_fixture() -> dict[str, Any]:
    """Return the context fixture data."""
    return load_fixture("context.json")


def test_user_context_from_api(context_data: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Test building a UserContext from the API response."""
    context = UserContext.model_validate(context_data)
    assert context == snapshot


def test_ata_unit_from_api(context_data: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Test parsing an ATA unit from the API settings array."""
    raw = context_data["buildings"][0]["airToAirUnits"][0]
    unit = ATAUnit.model_validate(raw)
    assert unit == snapshot


def test_ata_unit_capabilities(context_data: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Test that ATA unit capabilities are parsed correctly."""
    raw = context_data["buildings"][0]["airToAirUnits"][0]
    unit = ATAUnit.model_validate(raw)
    assert unit == snapshot


def test_atw_unit_from_api(context_data: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Test parsing an ATW unit from the API settings array."""
    raw = context_data["buildings"][0]["airToWaterUnits"][0]
    unit = ATWUnit.model_validate(raw)
    assert unit == snapshot


def test_atw_unit_capabilities(context_data: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Test that ATW unit capabilities are parsed correctly."""
    raw = context_data["buildings"][0]["airToWaterUnits"][0]
    unit = ATWUnit.model_validate(raw)
    assert unit == snapshot


def test_user_context_guest_buildings(snapshot: SnapshotAssertion) -> None:
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
    context = UserContext.model_validate(data)
    assert context == snapshot


def test_building_from_api(snapshot: SnapshotAssertion) -> None:
    """Test building a Building model with mixed unit types."""
    data = {
        "id": "test-building",
        "name": "Test Building",
        "airToAirUnits": [],
        "airToWaterUnits": [],
    }
    building = Building.model_validate(data)
    assert building == snapshot


def test_ata_unit_missing_optional_settings(snapshot: SnapshotAssertion) -> None:
    """Test that an ATA unit with minimal settings is handled gracefully."""
    raw = {
        "id": "minimal-unit",
        "givenDisplayName": "Minimal AC",
        "settings": [
            {"name": "Power", "value": "False"},
        ],
    }
    unit = ATAUnit.model_validate(raw)
    assert unit == snapshot


def test_ata_control_payload_omits_unset_fields() -> None:
    """Test that an ATA control payload contains only requested changes."""
    assert ATAUnitControl(set_fan_speed=ATAFanSpeed.ONE).to_api_payload() == {"setFanSpeed": ATAFanSpeed.ONE}


@pytest.mark.parametrize(
    ("control", "expected"),
    [
        (ATAUnitControl(power=False), {"power": False}),
        (ATAUnitControl(power=True), {"power": True}),
        (ATAUnitControl(operation_mode=ATAOperationMode.COOL), {"operationMode": ATAOperationMode.COOL}),
        (ATAUnitControl(set_temperature=0), {"setTemperature": 0}),
        (ATAUnitControl(set_temperature=22.5), {"setTemperature": 22.5}),
        (ATAUnitControl(set_fan_speed=ATAFanSpeed.FIVE), {"setFanSpeed": ATAFanSpeed.FIVE}),
        (
            ATAUnitControl(vane_vertical_direction=ATAVaneVertical.SWING),
            {"vaneVerticalDirection": ATAVaneVertical.SWING},
        ),
        (
            ATAUnitControl(vane_horizontal_direction=ATAVaneHorizontal.RIGHT_CENTRE),
            {"vaneHorizontalDirection": ATAVaneHorizontal.RIGHT_CENTRE},
        ),
        (ATAUnitControl(in_standby_mode=False), {"inStandbyMode": False}),
        (ATAUnitControl(in_standby_mode=True), {"inStandbyMode": True}),
    ],
)
def test_ata_control_payload_preserves_supplied_values(control: ATAUnitControl, expected: dict[str, Any]) -> None:
    """Test that every supplied control value is retained."""
    assert control.to_api_payload() == expected


def test_ata_control_payload_preserves_multiple_supplied_values() -> None:
    """Test that multiple supplied controls remain in the same payload."""
    control = ATAUnitControl(
        power=False,
        operation_mode=ATAOperationMode.HEAT,
        set_temperature=0,
        set_fan_speed=ATAFanSpeed.OFF,
        vane_vertical_direction=ATAVaneVertical.AUTO,
        vane_horizontal_direction=ATAVaneHorizontal.LEFT,
        in_standby_mode=False,
    )
    assert control.to_api_payload() == {
        "power": False,
        "operationMode": ATAOperationMode.HEAT,
        "setTemperature": 0,
        "setFanSpeed": ATAFanSpeed.OFF,
        "vaneVerticalDirection": ATAVaneVertical.AUTO,
        "vaneHorizontalDirection": ATAVaneHorizontal.LEFT,
        "inStandbyMode": False,
    }


def test_ata_unit_exports_settings(context_data: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Test that ATA settings are exported in both raw and mapped forms."""
    raw = context_data["buildings"][0]["airToAirUnits"][0]
    unit = ATAUnit.model_validate(raw)
    assert {
        "raw_settings": unit.raw_settings,
        "settings": unit.settings,
    } == snapshot


def test_atw_unit_exports_settings(context_data: dict[str, Any], snapshot: SnapshotAssertion) -> None:
    """Test that ATW settings are exported in both raw and mapped forms."""
    raw = context_data["buildings"][0]["airToWaterUnits"][0]
    unit = ATWUnit.model_validate(raw)
    assert {
        "raw_settings": unit.raw_settings,
        "settings": unit.settings,
    } == snapshot
