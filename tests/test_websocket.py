"""Tests for the on-demand WebSocket live-update client."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, Self
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import ClientError, ClientSession, WSMsgType
from aresponses import ResponsesMockServer
from syrupy.assertion import SnapshotAssertion

from aiomelcloudhome import MELCloudHomeWebSocket, MelCloudHomeWebSocketError
from aiomelcloudhome import websocket as websocket_module
from aiomelcloudhome.exceptions import MelCloudHomeAuthenticationError, MelCloudHomeConnectionError
from aiomelcloudhome.models.realtime import UnitStateDelta

_TOKEN_HOST = "6x2dgdulg7omjsxalnhmo4ynba0dcgwk.lambda-url.eu-west-1.on.aws"


def _auth(token: str = "test-token") -> MagicMock:
    """Return a mock auth provider that yields a bearer token."""
    auth = MagicMock()
    auth.async_get_access_token = AsyncMock(return_value=token)
    return auth


class _FakeMessage:
    """Minimal stand-in for an aiohttp WSMessage."""

    def __init__(self, msg_type: WSMsgType, payload: Any = None) -> None:
        self.type = msg_type
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _FakeWS:
    """Async-context-manager / async-iterator stand-in for a connected socket."""

    def __init__(self, messages: list[_FakeMessage]) -> None:
        self._messages = messages
        self.closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> bool:
        return False

    async def __aiter__(self) -> AsyncIterator[_FakeMessage]:
        for message in self._messages:
            yield message

    async def close(self) -> None:
        self.closed = True


async def test_fetch_hash_success(aresponses: ResponsesMockServer) -> None:
    """A 200 with a hash returns it."""
    aresponses.add(
        _TOKEN_HOST,
        "/",
        "GET",
        aresponses.Response(status=200, text=json.dumps({"hash": "the-hash", "userId": "the-hash"}), headers={"Content-Type": "application/json"}),
    )
    async with ClientSession() as session:
        ws = MELCloudHomeWebSocket(_auth(), session)
        assert await ws._fetch_hash() == "the-hash"
    aresponses.assert_plan_strictly_followed()


async def test_fetch_hash_non_200_raises(aresponses: ResponsesMockServer) -> None:
    """A non-200 token response raises so the caller can fall back to polling."""
    aresponses.add(_TOKEN_HOST, "/", "GET", aresponses.Response(status=403, text=""))
    async with ClientSession() as session:
        ws = MELCloudHomeWebSocket(_auth(), session)
        with pytest.raises(MelCloudHomeWebSocketError):
            await ws._fetch_hash()
    aresponses.assert_plan_strictly_followed()


async def test_fetch_hash_missing_hash_raises(aresponses: ResponsesMockServer) -> None:
    """A 200 without a hash raises."""
    aresponses.add(
        _TOKEN_HOST,
        "/",
        "GET",
        aresponses.Response(status=200, text=json.dumps({"userId": "x"}), headers={"Content-Type": "application/json"}),
    )
    async with ClientSession() as session:
        ws = MELCloudHomeWebSocket(_auth(), session)
        with pytest.raises(MelCloudHomeWebSocketError):
            await ws._fetch_hash()
    aresponses.assert_plan_strictly_followed()


async def test_stream_yields_delta(snapshot: SnapshotAssertion, monkeypatch: pytest.MonkeyPatch) -> None:
    """A TEXT frame is parsed and yielded as a UnitStateDelta."""
    frame = [{"messageType": "unitStateChanged", "Data": {"id": "u1", "unitType": "ata", "settings": [{"name": "SetTemperature", "value": 17}]}}]
    session = MagicMock()
    session.ws_connect = MagicMock(return_value=_FakeWS([_FakeMessage(WSMsgType.TEXT, frame), _FakeMessage(WSMsgType.CLOSED)]))
    ws = MELCloudHomeWebSocket(_auth(), session)
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(return_value="hash"))

    deltas = []
    async for delta in ws.stream():
        deltas.append(delta)
        break

    assert deltas == snapshot


async def test_stream_raises_on_token_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """An unrecoverable token failure propagates out of the stream."""
    ws = MELCloudHomeWebSocket(_auth(), MagicMock())
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(side_effect=MelCloudHomeWebSocketError("boom")))
    with pytest.raises(MelCloudHomeWebSocketError):
        async for _ in ws.stream():
            pass


async def test_stream_reconnects_after_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """After a socket close the loop backs off and re-fetches a hash."""
    monkeypatch.setattr(websocket_module, "BACKOFF", 0.0)
    session = MagicMock()
    session.ws_connect = MagicMock(return_value=_FakeWS([_FakeMessage(WSMsgType.CLOSED)]))
    ws = MELCloudHomeWebSocket(_auth(), session)

    calls = {"n": 0}

    async def _fake_hash() -> str:
        calls["n"] += 1
        if calls["n"] > 1:
            raise MelCloudHomeWebSocketError("stop")
        return "hash"

    monkeypatch.setattr(ws, "_fetch_hash", _fake_hash)
    with pytest.raises(MelCloudHomeWebSocketError):
        async for _ in ws.stream():
            pass
    assert calls["n"] == 2


async def test_close_stops_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    """close() ends the stream loop gracefully and closes the active socket."""
    frame = [{"messageType": "unitStateChanged", "Data": {"id": "u1", "unitType": "ata", "settings": [{"name": "Power", "value": True}]}}]
    live = _FakeWS([_FakeMessage(WSMsgType.TEXT, frame)])

    session = MagicMock()
    session.ws_connect = MagicMock(return_value=live)
    ws = MELCloudHomeWebSocket(_auth(), session)
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(return_value="hash"))

    received = []

    async def _consume() -> None:
        async for delta in ws.stream():
            received.append(delta)
            await ws.close()  # request stop right after the first delta

    await asyncio.wait_for(_consume(), timeout=1.0)
    assert len(received) == 1
    assert live.closed is True


async def test_stream_retries_on_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A ClientError while connecting is retried rather than raised."""
    monkeypatch.setattr(websocket_module, "BACKOFF", 0.0)
    session = MagicMock()
    session.ws_connect = MagicMock(side_effect=ClientError("down"))
    ws = MELCloudHomeWebSocket(_auth(), session)
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(return_value="hash"))

    async def _consume() -> None:
        async for _ in ws.stream():
            pass

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(_consume(), timeout=0.1)
    assert session.ws_connect.call_count >= 1


async def test_listen_calls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """listen() passes deltas and connection changes to the callbacks and ends on close()."""
    monkeypatch.setattr(websocket_module, "BACKOFF", 0.0)
    frame = [{"messageType": "unitStateChanged", "Data": {"id": "u1", "unitType": "ata", "settings": [{"name": "Power", "value": True}]}}]
    session = MagicMock()
    session.ws_connect = MagicMock(return_value=_FakeWS([_FakeMessage(WSMsgType.TEXT, frame)]))
    ws = MELCloudHomeWebSocket(_auth(), session)
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(return_value="hash"))

    events: list[str] = []

    def _on_delta(delta: UnitStateDelta) -> None:
        events.append(f"delta {delta.unit_id} connected={ws.connected}")
        asyncio.get_running_loop().create_task(ws.close())

    ws.register_delta_callback(_on_delta)
    ws.register_connection_callback(lambda connected: events.append(f"connected={connected}"))

    await asyncio.wait_for(ws.listen(), timeout=1.0)
    assert events == ["connected=True", "delta u1 connected=True", "connected=False"]
    assert ws.connected is False


async def test_unregister_callbacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unregistered callbacks are no longer called."""
    monkeypatch.setattr(websocket_module, "BACKOFF", 0.0)
    frame = [{"messageType": "unitStateChanged", "Data": {"id": "u1", "unitType": "ata", "settings": [{"name": "Power", "value": True}]}}]
    session = MagicMock()
    session.ws_connect = MagicMock(return_value=_FakeWS([_FakeMessage(WSMsgType.TEXT, frame)]))
    ws = MELCloudHomeWebSocket(_auth(), session)
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(return_value="hash"))
    on_delta = MagicMock()
    on_connection = MagicMock()

    def _close(_: UnitStateDelta) -> None:
        asyncio.get_running_loop().create_task(ws.close())

    ws.register_delta_callback(_close)
    ws.register_delta_callback(on_delta)()
    ws.register_connection_callback(on_connection)()

    await asyncio.wait_for(ws.listen(), timeout=1.0)
    on_delta.assert_not_called()
    on_connection.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(MelCloudHomeWebSocketError("token"), id="token_request"),
        pytest.param(MelCloudHomeConnectionError("auth down"), id="auth_connection"),
    ],
)
async def test_listen_retries_token_failure(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """listen() retries a failing token request instead of ending."""
    monkeypatch.setattr(websocket_module, "BACKOFF", 0.0)
    frame = [{"messageType": "unitStateChanged", "Data": {"id": "u1", "unitType": "ata", "settings": [{"name": "Power", "value": True}]}}]
    session = MagicMock()
    session.ws_connect = MagicMock(return_value=_FakeWS([_FakeMessage(WSMsgType.TEXT, frame)]))
    ws = MELCloudHomeWebSocket(_auth(), session)
    fetch_hash = AsyncMock(side_effect=[error, "hash"])
    monkeypatch.setattr(ws, "_fetch_hash", fetch_hash)

    deltas: list[UnitStateDelta] = []

    def _on_delta(delta: UnitStateDelta) -> None:
        deltas.append(delta)
        asyncio.get_running_loop().create_task(ws.close())

    ws.register_delta_callback(_on_delta)
    await asyncio.wait_for(ws.listen(), timeout=1.0)
    assert fetch_hash.await_count == 2
    assert len(deltas) == 1


async def test_listen_raises_on_auth_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """An authentication error ends listen() so the caller can reauthenticate."""
    ws = MELCloudHomeWebSocket(_auth(), MagicMock())
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(side_effect=MelCloudHomeAuthenticationError("bad")))
    with pytest.raises(MelCloudHomeAuthenticationError):
        await ws.listen()


async def test_listen_without_connection_change_on_failed_connect(monkeypatch: pytest.MonkeyPatch) -> None:
    """A connect attempt that fails reports no connection change."""
    monkeypatch.setattr(websocket_module, "BACKOFF", 0.0)
    session = MagicMock()
    session.ws_connect = MagicMock(side_effect=ClientError("down"))
    ws = MELCloudHomeWebSocket(_auth(), session)
    monkeypatch.setattr(ws, "_fetch_hash", AsyncMock(return_value="hash"))
    on_connection = MagicMock()
    ws.register_connection_callback(on_connection)

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(ws.listen(), timeout=0.1)
    on_connection.assert_not_called()
