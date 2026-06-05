"""Tests for Melcloud Home authentication."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientSession

from aiomelcloudhome.auth import MelCloudHomeAuth


@pytest.fixture(name="auth")
async def auth_fixture() -> MelCloudHomeAuth:
    """Return a MelCloudHomeAuth instance with a mock session."""
    async with ClientSession() as session:
        return MelCloudHomeAuth(
            username="test@example.com",
            password="test_password",
            session=session,
        )


async def test_token_valid_when_not_expired(auth: MelCloudHomeAuth) -> None:
    """Test that is_token_valid returns True when the token has not expired."""
    auth._access_token = "valid_token"
    auth._token_expiry = time.monotonic() + 3600
    assert auth.is_token_valid is True


async def test_token_invalid_when_expired(auth: MelCloudHomeAuth) -> None:
    """Test that is_token_valid returns False when the token has expired."""
    auth._access_token = "expired_token"
    auth._token_expiry = time.monotonic() - 1
    assert auth.is_token_valid is False


async def test_token_invalid_when_empty(auth: MelCloudHomeAuth) -> None:
    """Test that is_token_valid returns False when no token is stored."""
    assert auth.is_token_valid is False


async def test_token_invalid_within_refresh_buffer(auth: MelCloudHomeAuth) -> None:
    """Test that is_token_valid returns False within the 60-second refresh buffer."""
    auth._access_token = "near_expiry_token"
    auth._token_expiry = time.monotonic() + 30
    assert auth.is_token_valid is False


async def test_access_token_property(auth: MelCloudHomeAuth) -> None:
    """Test that the access_token property returns the stored token."""
    auth._access_token = "my_token"
    assert auth.access_token == "my_token"


async def test_store_tokens(auth: MelCloudHomeAuth) -> None:
    """Test that _store_tokens sets access token, refresh token, and expiry."""
    before = time.monotonic()
    auth._store_tokens(
        {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600,
        }
    )
    after = time.monotonic()

    assert auth._access_token == "new_access"
    assert auth._refresh_token == "new_refresh"
    assert before + 3600 <= auth._token_expiry <= after + 3600


async def test_ensure_valid_token_skips_when_valid(auth: MelCloudHomeAuth) -> None:
    """Test that ensure_valid_token does not refresh when the token is still valid."""
    auth._access_token = "valid_token"
    auth._token_expiry = time.monotonic() + 3600

    # Patch at the class level since slots=True prevents instance-level patching
    with patch.object(MelCloudHomeAuth, "refresh", new_callable=AsyncMock) as mock_refresh:
        await auth.ensure_valid_token()
        mock_refresh.assert_not_called()


async def test_ensure_valid_token_refreshes_when_expired(auth: MelCloudHomeAuth) -> None:
    """Test that ensure_valid_token calls refresh when the token is expired."""
    auth._access_token = "expired"
    auth._token_expiry = time.monotonic() - 1

    with patch.object(MelCloudHomeAuth, "refresh", new_callable=AsyncMock) as mock_refresh:
        await auth.ensure_valid_token()
        mock_refresh.assert_called_once()


async def test_refresh_falls_back_to_authenticate_when_no_refresh_token(auth: MelCloudHomeAuth) -> None:
    """Test that refresh() falls back to full authentication when no refresh token is set."""
    with patch.object(MelCloudHomeAuth, "authenticate", new_callable=AsyncMock) as mock_auth:
        await auth.refresh()
        mock_auth.assert_called_once()
