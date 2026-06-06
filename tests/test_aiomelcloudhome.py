"""Tests for the MELCloudHome client."""

import json
from datetime import datetime

import pytest
from aresponses import ResponsesMockServer
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome import MELCloudHome, MelCloudHomeAuthenticationError, MelCloudHomeNotFoundError
from aiomelcloudhome.exceptions import MelCloudHomeConnectionError
from aiomelcloudhome.models.ata import ATAOperationMode
from tests import load_fixture


def _fixture_response(filename: str, status: int = 200) -> str:
    """Return fixture content as a JSON string."""
    return json.dumps(load_fixture(filename))


async def test_get_context(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome, snapshot: SnapshotAssertion) -> None:
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

    context = await melcloudhome_client.get_context()
    assert context == snapshot
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


async def test_get_energy_telemetry(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome, snapshot: SnapshotAssertion) -> None:
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

    assert values == snapshot
    aresponses.assert_plan_strictly_followed()


async def test_get_energy_telemetry_not_modified(
    aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome, snapshot: SnapshotAssertion
) -> None:
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
    assert values == snapshot
    aresponses.assert_plan_strictly_followed()


async def test_get_outdoor_temperature(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome, snapshot: SnapshotAssertion) -> None:
    """Test that outdoor temperature is fetched from the trend summary."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/report/v1/trendsummary",
        "GET",
        aresponses.Response(status=200, text=_fixture_response("trendsummary.json"), headers={"Content-Type": "application/json"}),
    )

    temp = await melcloudhome_client.get_outdoor_temperature("ata-unit-uuid-1")
    assert temp == snapshot
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


async def test_get_actual_telemetry(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome, snapshot: SnapshotAssertion) -> None:
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

    assert values == snapshot
    aresponses.assert_plan_strictly_followed()


@pytest.mark.parametrize(
    ("status_code", "expected_exception"),
    [
        (401, MelCloudHomeAuthenticationError),
        (404, MelCloudHomeNotFoundError),
        (500, MelCloudHomeConnectionError),
    ],
)
async def test_client_exceptions(
    aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome, status_code: int, expected_exception: type
) -> None:
    """Test that client exceptions are raised for different status codes."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/context",
        "GET",
        aresponses.Response(status=status_code, text="Error", headers={"Content-Type": "text/plain"}),
    )

    with pytest.raises(expected_exception):
        await melcloudhome_client.get_context()
