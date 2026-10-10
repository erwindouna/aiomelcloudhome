"""Tests for Melcloud Home data models."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome.models.ata import ATACapabilities, ATAUnit
from aiomelcloudhome.models.atw import ATWCapabilities, ATWFrostProtection, ATWOperationMode, ATWUnit
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
        pytest.param("Heating", ATWOperationMode.HEATING, id="heating"),
        pytest.param("Cooling", ATWOperationMode.COOLING, id="cooling"),
        pytest.param("FreezeStat", ATWOperationMode.FREEZE_STAT, id="freeze_stat"),
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
    ("capabilities", "setting", "expected"),
    [
        pytest.param({"hasCoolingMode": True}, "False", True, id="capability_wins"),
        pytest.param({"hasHotWater": True}, "True", True, id="from_settings"),
        pytest.param({"hasHotWater": True}, None, None, id="unknown"),
    ],
)
def test_atw_has_cooling_mode(*, capabilities: dict[str, Any], setting: str | None, expected: bool | None) -> None:
    """ATW reports HasCoolingMode in its settings; it fills the capability when that is missing."""
    settings = [] if setting is None else [{"name": "HasCoolingMode", "value": setting}]
    unit = ATWUnit.model_validate({"id": "atw-1", "givenDisplayName": "Heat Pump", "settings": settings, "capabilities": capabilities})
    assert unit.capabilities is not None
    assert unit.capabilities.has_cooling_mode is expected


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        pytest.param({"hasZone2": True}, True, id="capability_true"),
        pytest.param({"hasZone2": False}, False, id="capability_false"),
        pytest.param(None, False, id="settings_fallback"),
    ],
)
def test_atw_has_zone2_from_capabilities(*, capabilities: dict[str, Any] | None, expected: bool) -> None:
    """has_zone2 comes from capabilities.hasZone2; the free-text HasZone2 setting is only a fallback."""
    unit = ATWUnit.model_validate(
        {"id": "atw-1", "givenDisplayName": "Heat Pump", "settings": [{"name": "HasZone2", "value": "None"}], "capabilities": capabilities},
    )
    assert unit.has_zone2 is expected


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        pytest.param({"minSetTemperature": 10, "maxSetTemperature": 30}, (10.0, 30.0, 10.0, 30.0), id="shared_range"),
        pytest.param(
            {"minSetTemperatureZone1": 12, "maxSetTemperatureZone1": 28, "minSetTemperatureZone2": 15, "maxSetTemperatureZone2": 25},
            (12.0, 28.0, 15.0, 25.0),
            id="per_zone",
        ),
    ],
)
def test_atw_zone_temperature_range(capabilities: dict[str, Any], expected: tuple[float, float, float, float]) -> None:
    """The API's single zone range applies to both zones; per-zone keys are still accepted."""
    caps = ATWCapabilities.model_validate(capabilities)
    assert (
        caps.min_set_temperature_zone1,
        caps.max_set_temperature_zone1,
        caps.min_set_temperature_zone2,
        caps.max_set_temperature_zone2,
    ) == expected


@pytest.mark.parametrize(
    ("zone1_active", "zone2_active", "expected"),
    [
        pytest.param(False, False, False, id="inactive"),
        pytest.param(True, False, True, id="zone1"),
        pytest.param(False, True, True, id="zone2"),
    ],
)
def test_atw_frost_protection_zones(*, zone1_active: bool, zone2_active: bool, expected: bool) -> None:
    """ATW frost protection reports activity per zone; ``active`` is set when either zone is."""
    unit = ATWUnit.model_validate(
        {
            "id": "atw-1",
            "givenDisplayName": "Heat Pump",
            "frostProtection": {"enabled": True, "min": 5, "max": 8, "zone1Active": zone1_active, "zone2Active": zone2_active},
        },
    )
    assert isinstance(unit.frost_protection, ATWFrostProtection)
    assert unit.frost_protection.zone1_active is zone1_active
    assert unit.frost_protection.zone2_active is zone2_active
    assert unit.frost_protection.active is expected


@pytest.mark.parametrize(
    ("capabilities", "expected"),
    [
        pytest.param({"hasMeasuredEnergyConsumption": False, "hasEstimatedEnergyConsumption": True}, True, id="estimated"),
        pytest.param({"hasMeasuredEnergyConsumption": True, "hasEstimatedEnergyConsumption": False}, True, id="measured"),
        pytest.param({"hasMeasuredEnergyConsumption": False, "hasEstimatedEnergyConsumption": False}, False, id="none"),
        pytest.param({"hasEnergyConsumedMeter": False, "hasEstimatedEnergyConsumption": True}, False, id="explicit_wins"),
        pytest.param({"hasHotWater": True}, None, id="unknown"),
    ],
)
def test_atw_has_energy_consumed_meter(*, capabilities: dict[str, Any], expected: bool | None) -> None:
    """ATW units report measured or estimated consumption instead of hasEnergyConsumedMeter."""
    assert ATWCapabilities.model_validate(capabilities).has_energy_consumed_meter is expected


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
