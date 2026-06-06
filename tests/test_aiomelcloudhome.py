"""Tests for the MELCloudHome client."""

from __future__ import annotations

import json
from datetime import datetime

import pytest
from aresponses import ResponsesMockServer

from aiomelcloudhome import MELCloudHome, MelCloudHomeAuthenticationError, MelCloudHomeNotFoundError, UserContext
from aiomelcloudhome.models.ata import ATAOperationMode
from tests import load_fixture


def _fixture_response(filename: str, status: int = 200) -> str:
    """Return fixture content as a JSON string."""
    return json.dumps(load_fixture(filename))


async def test_get_context(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that get_context returns a parsed UserContext."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/context",
        "GET",
        aresponses.Response(
            status=200,
            text=_fixture_response("context.json"),
            headers={"Content-Type": "application/json"},
        ),
    )

    ctx = await melcloudhome_client.get_context()

    assert isinstance(ctx, UserContext)
    assert len(ctx.buildings) == 1
    assert ctx.buildings[0].name == "My Home"
    assert len(ctx.buildings[0].air_to_air_units) == 1
    assert len(ctx.buildings[0].air_to_water_units) == 1
    aresponses.assert_plan_strictly_followed()


async def test_get_context_ata_unit(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that ATA unit data is parsed correctly from context."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/context",
        "GET",
        aresponses.Response(status=200, text=_fixture_response("context.json"), headers={"Content-Type": "application/json"}),
    )

    ctx = await melcloudhome_client.get_context()
    unit = ctx.buildings[0].air_to_air_units[0]

    assert unit.id == "ata-unit-uuid-1"
    assert unit.name == "Living Room AC"
    assert unit.power is True
    assert unit.set_temperature == 21.0
    assert unit.room_temperature == 20.0
    aresponses.assert_plan_strictly_followed()


async def test_get_context_atw_unit(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that ATW unit data is parsed correctly from context."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/context",
        "GET",
        aresponses.Response(status=200, text=_fixture_response("context.json"), headers={"Content-Type": "application/json"}),
    )

    ctx = await melcloudhome_client.get_context()
    unit = ctx.buildings[0].air_to_water_units[0]

    assert unit.id == "atw-unit-uuid-1"
    assert unit.power is True
    assert unit.tank_water_temperature == 48.0
    aresponses.assert_plan_strictly_followed()


async def test_control_ata_unit(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that control_ata_unit sends a PUT request."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/monitor/ataunit/ata-unit-uuid-1",
        "PUT",
        aresponses.Response(status=200, text="", headers={"Content-Length": "0"}),
    )

    await melcloudhome_client.control_ata_unit(
        "ata-unit-uuid-1",
        power=True,
        operation_mode=ATAOperationMode.HEAT,
        set_temperature=22.0,
    )
    aresponses.assert_plan_strictly_followed()


async def test_control_atw_unit(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that control_atw_unit sends a PUT request."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/monitor/atwunit/atw-unit-uuid-1",
        "PUT",
        aresponses.Response(status=200, text="", headers={"Content-Length": "0"}),
    )

    await melcloudhome_client.control_atw_unit(
        "atw-unit-uuid-1",
        power=True,
        set_tank_water_temperature=50.0,
    )
    aresponses.assert_plan_strictly_followed()


async def test_get_energy_telemetry(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that energy telemetry is fetched and parsed correctly."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/telemetry/telemetry/energy/atw-unit-uuid-1",
        "GET",
        aresponses.Response(status=200, text=_fixture_response("energy.json"), headers={"Content-Type": "application/json"}),
    )

    values = await melcloudhome_client.get_energy_telemetry(
        "atw-unit-uuid-1",
        from_dt=datetime(2026, 1, 14, 0, 0),
        to_dt=datetime(2026, 1, 14, 23, 59),
    )

    assert len(values) == 3
    assert values[0].value == "100.0"
    assert values[2].value == "200.0"
    aresponses.assert_plan_strictly_followed()


async def test_get_energy_telemetry_not_modified(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that a 304 Not Modified response returns an empty list."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/telemetry/telemetry/energy/atw-unit-uuid-1",
        "GET",
        aresponses.Response(status=304, text=""),
    )

    values = await melcloudhome_client.get_energy_telemetry(
        "atw-unit-uuid-1",
        from_dt=datetime(2026, 1, 14, 0, 0),
        to_dt=datetime(2026, 1, 14, 23, 59),
    )
    assert values == []
    aresponses.assert_plan_strictly_followed()


async def test_get_outdoor_temperature(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that outdoor temperature is fetched from the trend summary."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/report/v1/trendsummary",
        "GET",
        aresponses.Response(status=200, text=_fixture_response("trendsummary.json"), headers={"Content-Type": "application/json"}),
    )

    temp = await melcloudhome_client.get_outdoor_temperature("ata-unit-uuid-1")
    assert temp == 12.0
    aresponses.assert_plan_strictly_followed()


async def test_get_outdoor_temperature_not_modified(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that a 304 Not Modified response returns None."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/report/v1/trendsummary",
        "GET",
        aresponses.Response(status=304, text=""),
    )

    temp = await melcloudhome_client.get_outdoor_temperature("ata-unit-uuid-1")
    assert temp is None
    aresponses.assert_plan_strictly_followed()


async def test_get_actual_telemetry(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that actual telemetry data is fetched and parsed correctly."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/telemetry/telemetry/actual/atw-unit-uuid-1",
        "GET",
        aresponses.Response(status=200, text=_fixture_response("actual_telemetry.json"), headers={"Content-Type": "application/json"}),
    )

    values = await melcloudhome_client.get_actual_telemetry(
        "atw-unit-uuid-1",
        measure="flow_temperature",
        from_dt=datetime(2026, 1, 14, 10, 0),
        to_dt=datetime(2026, 1, 14, 11, 0),
    )

    assert len(values) == 2
    assert values[0]["value"] == "45.2"
    aresponses.assert_plan_strictly_followed()


async def test_authentication_error_on_401(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that a 401 response raises MelCloudHomeAuthenticationError."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/context",
        "GET",
        aresponses.Response(status=401, text="Unauthorized"),
    )

    with pytest.raises(MelCloudHomeAuthenticationError):
        await melcloudhome_client.get_context()


async def test_not_found_error_on_404(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that a 404 response raises MelCloudHomeNotFoundError."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/monitor/ataunit/nonexistent",
        "PUT",
        aresponses.Response(status=404, text="Not Found"),
    )

    with pytest.raises(MelCloudHomeNotFoundError):
        await melcloudhome_client.control_ata_unit("nonexistent", power=True)
