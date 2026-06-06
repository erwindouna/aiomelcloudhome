"""Additional tests to increase coverage for the MELCloudHome client and auth."""

import json
import socket
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from aresponses import ResponsesMockServer
from pydantic import ValidationError

from aiomelcloudhome import MELCloudHome, MelCloudHomeAuthenticationError, MelCloudHomeConnectionError, MelCloudHomeTimeoutError
from aiomelcloudhome.auth import MelCloudHomeAuth, _generate_pkce_pair
from aiomelcloudhome.models.ata import ATAUnit
from aiomelcloudhome.models.atw import ATWUnit, ATWZoneMode


async def test_client_creates_own_session() -> None:
    """Test that the client creates and closes its own session when none is provided."""
    with patch("aiomelcloudhome.aiomelcloudhome.MelCloudHomeAuth") as mock_auth_class:
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock()
        mock_auth.access_token = "tok"
        mock_auth.ensure_valid_token = AsyncMock()
        mock_auth.close = AsyncMock()
        mock_auth_class.return_value = mock_auth

        client = MELCloudHome(username="u@example.com", password="p")
        async with client as c:
            assert c._session is not None
            assert c._close_session is True


async def test_client_uses_provided_session() -> None:
    """Test that the client reuses a provided session and does not close it."""
    with patch("aiomelcloudhome.aiomelcloudhome.MelCloudHomeAuth") as mock_auth_class:
        mock_auth = MagicMock()
        mock_auth.authenticate = AsyncMock()
        mock_auth.access_token = "tok"
        mock_auth.close = AsyncMock()
        mock_auth_class.return_value = mock_auth

        async with aiohttp.ClientSession() as session:
            client = MELCloudHome(username="u@example.com", password="p", session=session)
            async with client as c:
                assert c._close_session is False
                assert c._session is session


@pytest.mark.parametrize(
    ("request_side_effect", "expected_exception"),
    [
        (aiohttp.ClientConnectionError("connection refused"), MelCloudHomeConnectionError),
        (aiohttp.ServerTimeoutError(), MelCloudHomeTimeoutError),
        (socket.gaierror("DNS lookup failed"), MelCloudHomeConnectionError),
    ],
)
async def test_request_error_wrapping(
    melcloudhome_client: MELCloudHome,
    request_side_effect: Exception,
    expected_exception: type[Exception],
) -> None:
    """Test that low-level request failures are mapped to client-level exceptions."""
    with patch.object(melcloudhome_client._session, "request", side_effect=request_side_effect):
        with pytest.raises(expected_exception):
            await melcloudhome_client.get_context()


async def test_get_outdoor_temperature_no_matching_dataset(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that get_outdoor_temperature returns None when no outdoor dataset is present."""
    import json

    data = [{"datasets": [{"label": "ROOM_TEMPERATURE", "data": [{"x": "2026-01-14", "y": 21}]}]}]
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/report/v1/trendsummary",
        "GET",
        aresponses.Response(status=200, text=json.dumps(data), headers={"Content-Type": "application/json"}),
    )

    temp = await melcloudhome_client.get_outdoor_temperature("unit-1")
    assert temp is None


async def test_get_outdoor_temperature_empty_data(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that get_outdoor_temperature returns None when outdoor dataset has no data points."""
    import json

    data = [{"datasets": [{"label": "OUTDOOR_TEMPERATURE", "data": []}]}]
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/report/v1/trendsummary",
        "GET",
        aresponses.Response(status=200, text=json.dumps(data), headers={"Content-Type": "application/json"}),
    )

    temp = await melcloudhome_client.get_outdoor_temperature("unit-1")
    assert temp is None


async def test_get_energy_telemetry_empty_measure_data(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that get_energy_telemetry returns [] when measureData is empty."""
    import json

    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/telemetry/telemetry/energy/unit-1",
        "GET",
        aresponses.Response(status=200, text=json.dumps({"measureData": []}), headers={"Content-Type": "application/json"}),
    )

    values = await melcloudhome_client.get_energy_telemetry("unit-1", from_dt=datetime(2026, 1, 14), to_dt=datetime(2026, 1, 14, 23))
    assert values == []


async def test_get_actual_telemetry_empty_measure_data(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that get_actual_telemetry returns [] when measureData is empty."""
    import json

    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/telemetry/telemetry/actual/unit-1",
        "GET",
        aresponses.Response(status=200, text=json.dumps({"measureData": []}), headers={"Content-Type": "application/json"}),
    )

    values = await melcloudhome_client.get_actual_telemetry(
        "unit-1", measure="flow_temperature", from_dt=datetime(2026, 1, 14), to_dt=datetime(2026, 1, 14, 23)
    )
    assert values == []


async def test_get_actual_telemetry_not_modified(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that get_actual_telemetry returns [] on 304 Not Modified."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/telemetry/telemetry/actual/unit-1",
        "GET",
        aresponses.Response(status=304, text=""),
    )

    values = await melcloudhome_client.get_actual_telemetry(
        "unit-1", measure="flow_temperature", from_dt=datetime(2026, 1, 14), to_dt=datetime(2026, 1, 14, 23)
    )
    assert values == []


def test_ata_unit_invalid_float_value() -> None:
    """Test that invalid float values in settings are treated as None."""
    raw = {
        "id": "unit-x",
        "givenDisplayName": "Test",
        "settings": [{"name": "SetTemperature", "value": "not_a_number"}],
    }
    unit = ATAUnit.model_validate(raw)
    assert unit.set_temperature is None


def test_ata_unit_unknown_operation_mode() -> None:
    """Test that an unknown operation mode in settings does not crash."""
    raw = {
        "id": "unit-x",
        "givenDisplayName": "Test",
        "settings": [{"name": "OperationMode", "value": "Auto"}],
    }
    with pytest.raises(ValidationError):
        ATAUnit.model_validate(raw)


def test_atw_unit_unknown_zone_mode_returns_none() -> None:
    """Test that an unknown zone mode is gracefully handled as None."""
    raw = {
        "id": "unit-atw",
        "givenDisplayName": "Test ATW",
        "settings": [{"name": "OperationModeZone1", "value": "UnknownMode"}],
    }
    unit = ATWUnit.model_validate(raw)
    assert unit.operation_mode_zone1 is None


def test_atw_unit_has_zone2_false_variants() -> None:
    """Test that HasZone2=0 and HasZone2=False both result in has_zone2=False."""
    for false_val in ("0", "False", "false"):
        raw = {
            "id": "unit-atw",
            "givenDisplayName": "Test",
            "settings": [{"name": "HasZone2", "value": false_val}],
        }
        unit = ATWUnit.model_validate(raw)
        assert unit.has_zone2 is False, f"Expected False for HasZone2={false_val!r}"


def test_atw_unit_has_zone2_true() -> None:
    """Test that HasZone2=True results in has_zone2=True."""
    raw = {
        "id": "unit-atw",
        "givenDisplayName": "Test",
        "settings": [{"name": "HasZone2", "value": "True"}],
    }
    unit = ATWUnit.model_validate(raw)
    assert unit.has_zone2 is True


def test_atw_unit_zone2_fields_parsed() -> None:
    """Test that Zone 2 temperature fields are parsed when present."""
    raw = {
        "id": "unit-atw",
        "givenDisplayName": "Heat Pump",
        "settings": [
            {"name": "HasZone2", "value": "True"},
            {"name": "OperationModeZone2", "value": "HeatFlowTemperature"},
            {"name": "SetTemperatureZone2", "value": "19"},
            {"name": "RoomTemperatureZone2", "value": "18"},
        ],
    }
    unit = ATWUnit.model_validate(raw)
    assert unit.has_zone2 is True
    assert unit.operation_mode_zone2 == ATWZoneMode.HEAT_FLOW_TEMPERATURE
    assert unit.set_temperature_zone2 == 19.0
    assert unit.room_temperature_zone2 == 18.0


def _make_mock_response(status: int, json_data: dict[str, object] | None = None) -> tuple[MagicMock, MagicMock]:
    """Create a properly set up aiohttp mock response context manager."""
    mock_resp = MagicMock()
    mock_resp.status = status
    if status >= 400:
        mock_resp.raise_for_status.side_effect = aiohttp.ClientResponseError(None, (), status=status)  # type: ignore[arg-type]
    else:
        mock_resp.raise_for_status.return_value = None
    if json_data is not None:
        mock_resp.json = AsyncMock(return_value=json_data)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_resp, mock_cm


async def test_auth_exchange_code_raises_on_error() -> None:
    """Test that _exchange_code raises MelCloudHomeAuthenticationError on HTTP error."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u", password="p", session=session)
        _, mock_cm = _make_mock_response(400)
        with patch.object(session, "post", return_value=mock_cm), pytest.raises(MelCloudHomeAuthenticationError):
            await auth._exchange_code("code", "verifier")


async def test_auth_refresh_raises_on_non_400_error() -> None:
    """Test that refresh() re-raises non-400 HTTP errors as MelCloudHomeAuthenticationError."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u", password="p", session=session)
        auth._refresh_token = "some_refresh_token"
        _, mock_cm = _make_mock_response(500)
        with patch.object(session, "post", return_value=mock_cm), pytest.raises(MelCloudHomeAuthenticationError):
            await auth.refresh()


async def test_auth_refresh_falls_back_on_400() -> None:
    """Test that refresh() falls back to authenticate() when server returns 400."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u", password="p", session=session)
        auth._refresh_token = "expired_refresh"
        _, mock_cm = _make_mock_response(400)

        with patch.object(session, "post", return_value=mock_cm), patch.object(MelCloudHomeAuth, "authenticate", new_callable=AsyncMock) as mock_auth:
            await auth.refresh()
            mock_auth.assert_called_once()


async def test_auth_exchange_code_stores_tokens() -> None:
    """Test that _exchange_code stores the returned tokens."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u", password="p", session=session)
        _, mock_cm = _make_mock_response(200, {"access_token": "acc", "refresh_token": "ref", "expires_in": 3600})
        with patch.object(session, "post", return_value=mock_cm):
            await auth._exchange_code("code", "verifier")
        assert auth.access_token == "acc"


def test_generate_pkce_pair_returns_valid_pair() -> None:
    """Test that _generate_pkce_pair returns a verifier and a SHA256 challenge."""
    import base64
    import hashlib

    verifier, challenge = _generate_pkce_pair()

    assert len(verifier) > 0
    assert len(challenge) > 0
    expected_challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected_challenge


def test_generate_pkce_pair_returns_different_pairs() -> None:
    """Test that each call to _generate_pkce_pair returns a unique pair."""
    v1, c1 = _generate_pkce_pair()
    v2, c2 = _generate_pkce_pair()
    assert v1 != v2
    assert c1 != c2


async def test_auth_refresh_success_stores_tokens() -> None:
    """Test that a successful token refresh stores the new tokens."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u", password="p", session=session)
        auth._refresh_token = "valid_refresh_token"

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.raise_for_status.return_value = None
        mock_resp.json = AsyncMock(return_value={"access_token": "new_access", "refresh_token": "new_refresh", "expires_in": 3600})
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch.object(session, "post", return_value=mock_cm):
            await auth.refresh()

        assert auth.access_token == "new_access"


async def test_get_outdoor_temperature_malformed_data(aresponses: ResponsesMockServer, melcloudhome_client: MELCloudHome) -> None:
    """Test that get_outdoor_temperature returns None when the response is malformed."""
    aresponses.add(
        "mobile.bff.melcloudhome.com",
        "/report/v1/trendsummary",
        "GET",
        aresponses.Response(
            status=200,
            text=json.dumps([{"datasets": [{"label": "OUTDOOR_TEMPERATURE", "data": [{"x": "2026-01-14", "y": "not_a_number"}]}]}]),
            headers={"Content-Type": "application/json"},
        ),
    )
    temp = await melcloudhome_client.get_outdoor_temperature("unit-1")
    assert temp is None


def test_ata_unit_invalid_rssi_string() -> None:
    """Test that an invalid rssi value (non-numeric string) is handled as None."""
    raw = {
        "id": "unit-x",
        "givenDisplayName": "Test",
        "settings": [],
        "rssi": "not-an-int",
    }
    unit = ATAUnit.model_validate(raw)
    assert unit.rssi is None


def test_ata_unit_rssi_none_string() -> None:
    """Test that a None rssi (converted to 'None' string) is handled as None."""
    raw: dict[str, object] = {
        "id": "unit-x",
        "givenDisplayName": "Test",
        "settings": [],
        "rssi": None,
    }
    unit = ATAUnit.model_validate(raw)
    assert unit.rssi is None


def test_atw_unit_invalid_float_temperature() -> None:
    """Test that an invalid float temperature value is handled as None."""
    raw = {
        "id": "unit-atw",
        "givenDisplayName": "Test",
        "settings": [
            {"name": "SetTemperatureZone1", "value": "not_a_float"},
        ],
    }
    unit = ATWUnit.model_validate(raw)
    assert unit.set_temperature_zone1 is None


def test_atw_unit_invalid_rssi_string() -> None:
    """Test that an invalid ATW rssi value is handled as None."""
    raw = {
        "id": "unit-atw",
        "givenDisplayName": "Test",
        "settings": [],
        "rssi": "not-an-int",
    }
    unit = ATWUnit.model_validate(raw)
    assert unit.rssi is None


def test_atw_unit_rssi_none_string() -> None:
    """Test that a None ATW rssi (converted to 'None' string) is handled as None."""
    raw: dict[str, object] = {
        "id": "unit-atw",
        "givenDisplayName": "Test",
        "settings": [],
        "rssi": None,
    }
    unit = ATWUnit.model_validate(raw)
    assert unit.rssi is None
