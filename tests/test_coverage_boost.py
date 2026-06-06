"""Targeted tests to reach 90% coverage threshold."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aresponses import ResponsesMockServer

from aiomelcloudhome import MELCloudHome
from aiomelcloudhome.auth import MelCloudHomeAuth, _generate_pkce_pair
from aiomelcloudhome.models.ata import ATAUnit
from aiomelcloudhome.models.atw import ATWUnit

# ---------------------------------------------------------------------------
# auth.py: _generate_pkce_pair (lines 27-29)
# ---------------------------------------------------------------------------


def test_generate_pkce_pair_returns_valid_pair() -> None:
    """Test that _generate_pkce_pair returns a verifier and a SHA256 challenge."""
    import base64
    import hashlib

    verifier, challenge = _generate_pkce_pair()

    assert len(verifier) > 0
    assert len(challenge) > 0
    # Verify the challenge is the SHA256 hash of the verifier
    expected_challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert challenge == expected_challenge


def test_generate_pkce_pair_returns_different_pairs() -> None:
    """Test that each call to _generate_pkce_pair returns a unique pair."""
    v1, c1 = _generate_pkce_pair()
    v2, c2 = _generate_pkce_pair()
    assert v1 != v2
    assert c1 != c2


# ---------------------------------------------------------------------------
# auth.py: successful refresh path (line 176)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# aiomelcloudhome.py: get_outdoor_temperature exception branch (lines 255-256)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# models/ata.py: _int exception branches (lines 122, 125-126)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# models/atw.py: _float / _int / _zone_mode exception branches (lines 95-96, 100, 103-104)
# ---------------------------------------------------------------------------


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
