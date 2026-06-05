"""Pytest configuration and fixtures for aiomelcloudhome tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientSession
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome import MELCloudHome

from .syrupy import MelCloudHomeSnapshotExtension


@pytest.fixture(name="snapshot")
def snapshot_fixture(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return a syrupy snapshot assertion with the custom extension."""
    return snapshot.use_extension(MelCloudHomeSnapshotExtension)


@pytest.fixture(name="melcloudhome_client")
async def melcloudhome_client_fixture() -> AsyncGenerator[MELCloudHome, None]:
    """Return a MELCloudHome client with mocked authentication."""
    async with ClientSession() as session:
        client = MELCloudHome(
            username="test@example.com",
            password="test_password",
            session=session,
            request_timeout=10.0,
        )
        # Bypass real authentication for tests
        mock_auth = MagicMock()
        mock_auth.access_token = "mock_access_token"
        mock_auth.ensure_valid_token = AsyncMock()
        client._session = session
        client._auth = mock_auth
        client._close_session = False
        yield client
