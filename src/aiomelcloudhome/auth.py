"""OAuth 2.0 PKCE authentication for Melcloud Home."""

import base64
import hashlib
import re
import secrets
import time
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

from aiohttp import ClientResponseError, ClientSession

from .exceptions import MelCloudHomeAuthenticationError

_AUTH_BASE = "https://auth.melcloudhome.com"
_COGNITO_DOMAIN = "live-melcloudhome.auth.eu-west-1.amazoncognito.com"
_CLIENT_ID = "homemobile"
_REDIRECT_URI = "melcloudhome://"
_SCOPES = "openid profile email offline_access IdentityServerApi"
_TOKEN_REFRESH_BUFFER = 60


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code verifier and challenge."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _parse_token_response(token_data: dict[str, object]) -> tuple[str, str, float]:
    """Parse a token endpoint response into (access_token, refresh_token, expiry)."""
    access_token = str(token_data.get("access_token", ""))
    refresh_token = str(token_data.get("refresh_token", ""))
    raw_expires = token_data.get("expires_in", 3600)
    expires_in = int(raw_expires) if isinstance(raw_expires, (int, float, str, bytes, bytearray)) else 3600
    return access_token, refresh_token, time.monotonic() + expires_in


class MelCloudHomeAuth:
    """Standalone OAuth 2.0 PKCE authentication using username and password."""

    def __init__(self, username: str, password: str, session: ClientSession | None = None) -> None:
        """Initialize MelCloudHomeAuth."""
        self.username = username
        self.password = password
        self._close_session = False
        if session is not None:
            self.session = session
        else:
            self.session = ClientSession()
            self._close_session = True
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expiry: float = 0.0

    @property
    def access_token(self) -> str | None:
        """Return the current access token."""
        return self._access_token

    @property
    def is_token_valid(self) -> bool:
        """Return True if the access token is still valid."""
        return bool(self._access_token) and time.monotonic() < self._token_expiry - _TOKEN_REFRESH_BUFFER

    async def authenticate(self) -> None:  # pylint: disable=too-many-locals
        """Perform the full OAuth 2.0 PKCE authentication flow."""
        verifier, challenge = _generate_pkce_pair()
        state = secrets.token_urlsafe(16)

        try:
            async with self.session.post(
                f"{_AUTH_BASE}/connect/par",
                data={
                    "client_id": _CLIENT_ID,
                    "redirect_uri": _REDIRECT_URI,
                    "response_type": "code",
                    "scope": _SCOPES,
                    "state": state,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                },
                allow_redirects=False,
            ) as resp:
                resp.raise_for_status()
                par_data = await resp.json(content_type=None)
                request_uri = par_data["request_uri"]
        except (ClientResponseError, KeyError) as err:
            raise MelCloudHomeAuthenticationError("PAR request failed") from err

        auth_url = f"{_AUTH_BASE}/connect/authorize?" + urlencode({"client_id": _CLIENT_ID, "request_uri": request_uri})
        try:
            async with self.session.get(auth_url, allow_redirects=True) as resp:
                cognito_url = str(resp.url)
                cognito_html = await resp.text()
        except ClientResponseError as err:
            raise MelCloudHomeAuthenticationError("Authorization redirect failed") from err

        csrf_match = re.search(r'name="_csrf"\s+value="([^"]+)"', cognito_html)
        if not csrf_match:
            raise MelCloudHomeAuthenticationError("Could not extract CSRF token from Cognito login page")
        csrf_token = csrf_match.group(1)

        parsed = urlparse(cognito_url)
        login_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        try:
            async with self.session.post(
                login_url,
                data={
                    "_csrf": csrf_token,
                    "username": self.username,
                    "password": self.password,
                },
                params=parse_qs(parsed.query),
                allow_redirects=False,
            ) as resp:
                if resp.status not in (301, 302):
                    raise MelCloudHomeAuthenticationError("Cognito credential submission did not redirect; check username/password")
                raw_location = resp.headers.get("Location", "")
                callback_location = urljoin(login_url, raw_location) if raw_location else ""
        except ClientResponseError as err:
            raise MelCloudHomeAuthenticationError("Credential submission failed") from err

        callback_location = await self._follow_redirects(callback_location, login_url)

        callback_parsed = urlparse(callback_location)
        callback_params = parse_qs(callback_parsed.query)

        auth_code = (callback_params.get("code") or [""])[0]
        if not auth_code:
            raise MelCloudHomeAuthenticationError("No authorization code in callback")

        await self._exchange_code(auth_code, verifier)

    async def _follow_redirects(self, start_location: str, base: str) -> str:
        """Follow redirects until reaching the app callback URI."""
        location = start_location
        for _ in range(10):
            if _REDIRECT_URI in location or not location:
                break
            if not location.startswith("http"):
                location = urljoin(base, location)
            try:
                async with self.session.get(location, allow_redirects=False) as resp:
                    base = location
                    raw_next = resp.headers.get("Location", "")
                    if raw_next:
                        location = urljoin(base, raw_next)
                    else:
                        loc_params = parse_qs(urlparse(location).query)
                        redirect_uri = (loc_params.get("RedirectUri") or [""])[0]
                        location = urljoin(base, redirect_uri) if redirect_uri else ""
            except ClientResponseError as err:
                raise MelCloudHomeAuthenticationError("Callback follow failed") from err
        return location

    async def _exchange_code(self, code: str, verifier: str) -> None:
        """Exchange an authorization code for access and refresh tokens."""
        try:
            async with self.session.post(
                f"{_AUTH_BASE}/connect/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": _CLIENT_ID,
                    "code": code,
                    "redirect_uri": _REDIRECT_URI,
                    "code_verifier": verifier,
                },
            ) as resp:
                resp.raise_for_status()
                token_data = await resp.json(content_type=None)
        except ClientResponseError as err:
            raise MelCloudHomeAuthenticationError("Token exchange failed") from err

        self._store_tokens(token_data)

    async def refresh(self) -> None:
        """Refresh the access token using the stored refresh token."""
        if not self._refresh_token:
            await self.authenticate()
            return

        try:
            async with self.session.post(
                f"{_AUTH_BASE}/connect/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": _CLIENT_ID,
                    "refresh_token": self._refresh_token,
                },
            ) as resp:
                resp.raise_for_status()
                token_data = await resp.json(content_type=None)
        except ClientResponseError as err:
            if err.status == 400:
                await self.authenticate()
                return
            raise MelCloudHomeAuthenticationError("Token refresh failed") from err

        self._store_tokens(token_data)

    def _store_tokens(self, token_data: dict[str, object]) -> None:
        """Store tokens and compute expiry time."""
        self._access_token, self._refresh_token, self._token_expiry = _parse_token_response(token_data)

    async def ensure_valid_token(self) -> None:
        """Ensure we have a valid token, refreshing or re-authenticating as needed."""
        if not self.is_token_valid:
            await self.refresh()

    async def async_get_access_token(self) -> str | None:
        """Return a valid access token, refreshing or re-authenticating as needed."""
        await self.ensure_valid_token()
        return self._access_token

    async def close(self) -> None:
        """Close the session if it was created internally."""
        if self._close_session and self.session:
            await self.session.close()
