"""Tests for Melcloud Home data models."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome.models.ata import ATACapabilities, ATAUnit
from aiomelcloudhome.models.atw import ATWOperationMode, ATWUnit
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


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        pytest.param("Stop", ATWOperationMode.STOP, id="stop"),
        pytest.param("HotWater", ATWOperationMode.HOT_WATER, id="hot_water"),
        pytest.param("Heat", ATWOperationMode.HEAT, id="heat"),
        pytest.param("Unknown", None, id="unknown"),
    ],
)
def test_atw_unit_operation_mode(value: str, expected: ATWOperationMode | None) -> None:
    """Test parsing the ATW operation mode reported by the unit."""
    unit = ATWUnit.model_validate(
        {
            "id": "atw-unit-uuid-1",
            "givenDisplayName": "Heat Pump",
            "settings": [{"name": "OperationMode", "value": value}],
        },
    )
    assert unit.operation_mode is expected


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


@pytest.mark.parametrize(
    "capabilities",
    [
        pytest.param({"minTempCoolDry": 16, "maxTempCoolDry": 31, "hasStandby": True}, id="api_keys"),
        pytest.param({"minTempCool": 16, "maxTempCool": 31, "hasStandbyMode": True}, id="legacy_keys"),
    ],
)
def test_ata_cool_range_and_standby(capabilities: dict[str, Any]) -> None:
    """The cool/dry range and standby flag parse from the API keys and the legacy keys."""
    caps = ATACapabilities.model_validate(capabilities)
    assert (caps.min_temp_cool, caps.max_temp_cool, caps.has_standby_mode) == (16.0, 31.0, True)


@pytest.mark.parametrize(
    ("capabilities", "settings", "expected"),
    [
        pytest.param({}, [{"name": "VaneVerticalDirection", "value": "Auto"}], (True, None), id="vertical_setting"),
        pytest.param({"hasAirDirection": True}, [], (True, None), id="air_direction"),
        pytest.param({}, [{"name": "VaneHorizontalDirection", "value": "Centre"}], (None, True), id="horizontal_setting"),
        pytest.param({"hasVaneVertical": False, "hasVaneHorizontal": False}, [], (False, False), id="explicit"),
        pytest.param({"hasAirDirection": False}, [], (None, None), id="none"),
    ],
)
def test_ata_vane_capabilities(
    capabilities: dict[str, Any],
    settings: list[dict[str, str]],
    expected: tuple[bool | None, bool | None],
) -> None:
    """The API sends no vane flags, so they come from the settings and hasAirDirection."""
    unit = ATAUnit.model_validate({"id": "ata-1", "givenDisplayName": "AC", "settings": settings, "capabilities": capabilities})
    assert unit.capabilities is not None
    assert (unit.capabilities.has_vane_vertical, unit.capabilities.has_vane_horizontal) == expected
