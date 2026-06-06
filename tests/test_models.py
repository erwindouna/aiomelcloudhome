"""Tests for Melcloud Home data models."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome.models.ata import ATAUnit
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
