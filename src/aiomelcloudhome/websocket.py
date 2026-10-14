"""On-demand WebSocket live-update client for Melcloud Home."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Self

from aiohttp import ClientError, ClientSession, ClientTimeout, ClientWebSocketResponse, WSMsgType
from yarl import URL

from .auth import AbstractAuth
from .exceptions import MelCloudHomeConnectionError, MelCloudHomeTimeoutError, MelCloudHomeWebSocketError
from .models.realtime import UnitStateDelta, parse_frame

_LOGGER = logging.getLogger(__name__)

WS_TOKEN_URL = "https://6x2dgdulg7omjsxalnhmo4ynba0dcgwk.lambda-url.eu-west-1.on.aws/"  # noqa: S105
WS_URL = "wss://ws.melcloudhome.com/"

BACKOFF = 1.0
MAX_BACKOFF = 60.0
HEARTBEAT = 30.0


class MELCloudHomeWebSocket:
    """Receive-only WebSocket client yielding live :class:`UnitStateDelta` updates."""

    def __init__(
        self,
        auth: AbstractAuth,
        session: ClientSession,
        *,
        token_url: str = WS_TOKEN_URL,
        ws_url: str = WS_URL,
        request_timeout: float = 10.0,
    ) -> None:
        """Initialize the WebSocket client with an auth provider and an aiohttp session."""
        self._auth = auth
        self._session = session
        self._token_url = token_url
        self._ws_url = ws_url
        self._request_timeout = request_timeout
        self._stop = asyncio.Event()
        self._ws: ClientWebSocketResponse | None = None
        self._delta_callbacks: list[Callable[[UnitStateDelta], None]] = []
        self._connection_callbacks: list[Callable[[bool], None]] = []
        self._connected = False

    @property
    def connected(self) -> bool:
        """Return whether a live socket is currently established."""
        return self._connected

    def register_delta_callback(self, callback: Callable[[UnitStateDelta], None]) -> Callable[[], None]:
        """Register a callback for every live unit-state delta; returns a function that unregisters it."""
        self._delta_callbacks.append(callback)
        return lambda: self._delta_callbacks.remove(callback)

    def register_connection_callback(self, callback: Callable[[bool], None]) -> Callable[[], None]:
        """Register a callback for connection changes (``True`` = live, ``False`` = lost).

        Returns a function that unregisters it. Use it to poll while the stream is down.
        """
        self._connection_callbacks.append(callback)
        return lambda: self._connection_callbacks.remove(callback)

    def _set_connected(self, *, connected: bool) -> None:
        """Store the connection state and notify the connection callbacks."""
        self._connected = connected
        for callback in list(self._connection_callbacks):
            callback(connected)

    async def __aenter__(self) -> Self:
        """Enter the async context; pair with iterating :meth:`stream`."""
        return self

    async def __aexit__(self, *_: object) -> None:
        """Close the stream on context exit."""
        await self.close()

    async def close(self) -> None:
        """Stop the stream gracefully and tear down the active socket."""
        self._stop.set()
        if self._ws is not None and not self._ws.closed:
            await self._ws.close()

    async def _fetch_hash(self) -> str:
        """Fetch a fresh connection hash from the token endpoint using the existing bearer."""
        token = await self._auth.async_get_access_token()
        try:
            async with self._session.get(
                self._token_url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=ClientTimeout(total=self._request_timeout),
            ) as resp:
                if resp.status != 200:
                    raise MelCloudHomeWebSocketError(f"WebSocket token request failed: HTTP {resp.status}")
                data = await resp.json(content_type=None)
        except (ClientError, TimeoutError) as err:
            raise MelCloudHomeWebSocketError(f"WebSocket token request failed: {err}") from err

        ws_hash = data.get("hash") if isinstance(data, dict) else None
        if not ws_hash:
            raise MelCloudHomeWebSocketError("WebSocket token response did not contain a hash")
        return str(ws_hash)

    async def stream(self) -> AsyncIterator[UnitStateDelta]:
        """Yield live unit-state deltas, reconnecting transparently until :meth:`close`.

        Iterate this (typically inside a background task); the iterator ends cleanly once
        :meth:`close` is called. Transient socket drops — including the ~2h gateway cap —
        are retried with exponential backoff. A failing token request raises
        :class:`MelCloudHomeWebSocketError`; use :meth:`listen` to retry those too.
        """
        async for delta in self._run(retry_token_errors=False):
            yield delta

    async def listen(self) -> None:
        """Run until :meth:`close`, passing every live delta to the registered delta callbacks.

        Await this in a task you own; it creates no tasks of its own. Every failure is
        retried with exponential backoff, the token request included, except
        :class:`MelCloudHomeAuthenticationError`, which is raised. Connection changes go to
        the registered connection callbacks; the stream starts out disconnected.
        """
        async for delta in self._run(retry_token_errors=True):
            for callback in list(self._delta_callbacks):
                callback(delta)

    async def _run(self, *, retry_token_errors: bool) -> AsyncIterator[UnitStateDelta]:
        """Connect, yield deltas and reconnect with backoff until :meth:`close`."""
        self._stop.clear()
        backoff = BACKOFF
        while not self._stop.is_set():
            try:
                ws_hash = await self._fetch_hash()
                url = URL(self._ws_url).update_query({"hash": ws_hash})
                async with self._session.ws_connect(url, heartbeat=HEARTBEAT) as ws:
                    _LOGGER.debug("MELCloud Home WebSocket connected")
                    self._ws = ws
                    backoff = BACKOFF
                    self._set_connected(connected=True)
                    try:
                        async for msg in ws:
                            if msg.type == WSMsgType.TEXT:
                                for delta in parse_frame(msg.json()):
                                    yield delta
                            elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR):
                                _LOGGER.info("MELCloud Home WebSocket closed with type %s", msg.type)
                                break
                    finally:
                        self._set_connected(connected=False)
                _LOGGER.debug("MELCloud Home WebSocket closed; reconnecting")
            except (ClientError, TimeoutError) as err:
                _LOGGER.debug("MELCloud Home WebSocket connection error: %s; retrying in %.0fs", err, backoff)
            except (MelCloudHomeWebSocketError, MelCloudHomeConnectionError, MelCloudHomeTimeoutError) as err:
                if not retry_token_errors:
                    raise
                _LOGGER.debug("MELCloud Home WebSocket token request failed: %s; retrying in %.0fs", err, backoff)
            finally:
                self._ws = None
            if self._stop.is_set():
                # Time to close shop. :)
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF)
