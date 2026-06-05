"""Tests for the authenticate() PKCE flow in MelCloudHomeAuth."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from aiomelcloudhome.auth import MelCloudHomeAuth
from aiomelcloudhome.exceptions import MelCloudHomeAuthenticationError


def _make_cm(
    status: int,
    json_data: dict[str, object] | None = None,
    text_data: str | None = None,
    headers: dict[str, str] | None = None,
) -> MagicMock:
    """Build an aiohttp async context manager mock."""
    mock_resp = MagicMock()
    mock_resp.status = status
    mock_resp.url = "http://example.com"
    mock_resp.headers = headers or {}
    if status >= 400:
        mock_resp.raise_for_status.side_effect = aiohttp.ClientResponseError(None, (), status=status)  # type: ignore[arg-type]
    else:
        mock_resp.raise_for_status.return_value = None
    if json_data is not None:
        mock_resp.json = AsyncMock(return_value=json_data)
    if text_data is not None:
        mock_resp.text = AsyncMock(return_value=text_data)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return mock_cm


async def test_authenticate_par_request_failure_raises() -> None:
    """Test that a failed PAR request raises MelCloudHomeAuthenticationError."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u@example.com", password="pass", session=session)
        with patch.object(session, "post", return_value=_make_cm(400)):
            with pytest.raises(MelCloudHomeAuthenticationError, match="PAR request failed"):
                await auth.authenticate()


async def test_authenticate_no_auth_code_in_callback() -> None:
    """Test that a missing auth code in the callback raises MelCloudHomeAuthenticationError."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u@example.com", password="pass", session=session)

        # Step 1: PAR succeeds
        par_cm = _make_cm(200, json_data={"request_uri": "urn:ietf:params:oauth:request_uri:test"})

        # Step 2: Authorization GET returns Cognito page with a CSRF token
        cognito_html = '<input name="_csrf" value="csrf_token_value">'
        auth_cm = _make_cm(200, text_data=cognito_html)

        # Step 3: POST credentials → 302 redirect to melcloudhome:// scheme (no code)
        redirect_cm = _make_cm(302, headers={"Location": "melcloudhome://?state=x"})

        def _post_side_effect(*args: object, **kwargs: object) -> MagicMock:
            url = str(args[0]) if args else str(kwargs.get("url", ""))
            if "par" in url or "connect/par" in url:
                return par_cm
            return redirect_cm

        def _get_side_effect(*args: object, **kwargs: object) -> MagicMock:
            return auth_cm

        with patch.object(session, "post", side_effect=_post_side_effect), patch.object(session, "get", side_effect=_get_side_effect):
            with pytest.raises(MelCloudHomeAuthenticationError, match="No authorization code"):
                await auth.authenticate()


async def test_authenticate_cognito_no_csrf_raises() -> None:
    """Test that a missing CSRF token on the Cognito page raises MelCloudHomeAuthenticationError."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u@example.com", password="pass", session=session)

        par_cm = _make_cm(200, json_data={"request_uri": "urn:ietf:params:oauth:request_uri:test"})
        # No CSRF token in HTML
        auth_cm = _make_cm(200, text_data="<html>No csrf here</html>")

        def _post_side_effect(*args: object, **kwargs: object) -> MagicMock:
            return par_cm

        def _get_side_effect(*args: object, **kwargs: object) -> MagicMock:
            return auth_cm

        with patch.object(session, "post", side_effect=_post_side_effect), patch.object(session, "get", side_effect=_get_side_effect):
            with pytest.raises(MelCloudHomeAuthenticationError, match="CSRF"):
                await auth.authenticate()


async def test_authenticate_full_flow_with_identity_server_callback() -> None:
    """Test the flow where the callback requires following the IdentityServer redirect."""
    async with aiohttp.ClientSession() as session:
        auth = MelCloudHomeAuth(username="u@example.com", password="pass", session=session)

        par_cm = _make_cm(200, json_data={"request_uri": "urn:ietf:params:oauth:request_uri:test"})
        cognito_html = '<input name="_csrf" value="csrf_token_value">'
        auth_cm = _make_cm(200, text_data=cognito_html)
        # Cognito redirects to identity server (not directly to melcloudhome://)
        cognito_redirect_cm = _make_cm(302, headers={"Location": "https://auth.melcloudhome.com/connect/authorize/callback?code=auth_code_123"})
        # Identity server callback redirects to melcloudhome:// with code
        callback_cm = _make_cm(302, headers={"Location": "melcloudhome://?code=auth_code_123&state=x"})
        # Token exchange
        token_cm = _make_cm(200, json_data={"access_token": "acc_tok", "refresh_token": "ref_tok", "expires_in": 3600})

        post_calls = [par_cm, cognito_redirect_cm, token_cm]
        get_calls = [auth_cm, callback_cm]

        with patch.object(session, "post", side_effect=post_calls), patch.object(session, "get", side_effect=get_calls):
            await auth.authenticate()

        assert auth.access_token == "acc_tok"
