"""Asynchronous Python client for Melcloud Home."""

import logging
import socket
from datetime import UTC, datetime
from importlib import metadata
from typing import Any, Self, cast

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout
from aiohttp.hdrs import METH_GET, METH_PUT
from yarl import URL

from aiomelcloudhome.models.telemetry import MeasurementEntry, TelemetryValue

from .auth import MelCloudHomeAuth
from .exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeNotFoundError,
    MelCloudHomeTimeoutError,
)
from .models.ata import ATAFanSpeed, ATAOperationMode, ATAUnitControl, ATAVaneHorizontal, ATAVaneVertical
from .models.atw import ATWUnitControl, ATWZoneMode
from .models.context import UserContext

try:
    VERSION = metadata.version(__package__)
except metadata.PackageNotFoundError:  # pragma: no cover
    VERSION = "DEV-0.0.0"  # pylint: disable=invalid-name


API_BASE = "https://mobile.bff.melcloudhome.com"

_LOGGER = logging.getLogger(__name__)


class MELCloudHome:
    """Asynchronous client for the Melcloud Home API."""

    def __init__(  # pylint: disable=too-many-arguments
        self,
        *,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        session: ClientSession | None = None,
        request_timeout: float = 10.0,
    ) -> None:
        """Initialize the MELCloudHome client.

        Provide one of:
        - ``username`` + ``password``: performs the full PKCE auth flow.
        - ``access_token``: uses the token directly (no PKCE flow).
        """
        if username and password:
            self._auth = MelCloudHomeAuth(username, password)

        self._access_token = access_token
        self._request_timeout = request_timeout
        if session is not None:
            self._session = session
            self._close_session = False
        else:
            self._session = ClientSession()
            self._close_session = True

    async def _request(  # pylint: disable=too-many-arguments
        self,
        uri: str,
        *,
        method: str = METH_GET,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request with retry logic."""
        token = self._access_token or await self._auth.async_get_access_token()
        url = URL(API_BASE) / uri.lstrip("/")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"aiomelcloudhome/{VERSION}",
        }

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=ClientTimeout(total=timeout or self._request_timeout),
            ) as resp:
                match resp.status:
                    case 401:
                        raise MelCloudHomeAuthenticationError("Authentication failed")
                    case 404:
                        raise MelCloudHomeNotFoundError(f"Resource not found: {uri}")
                resp.raise_for_status()
                if resp.content_length == 0 or resp.status in (204, 304):
                    return {}
                _LOGGER.debug("API response for %s %s: %s", method, uri, await resp.text())
                return cast("dict[str, Any]", await resp.json(content_type=None))
        except TimeoutError as err:
            raise MelCloudHomeTimeoutError(f"Request timed out: {err}") from err
        except (ClientResponseError, ClientError, socket.gaierror) as err:
            raise MelCloudHomeConnectionError(f"Connection error: {err}") from err

    async def get_context(self) -> UserContext:
        """Fetch the full user context (all buildings and devices)."""
        return UserContext.model_validate(await self._request("/context"))

    async def control_ata_unit(  # pylint: disable=too-many-arguments
        self,
        unit_id: str,
        *,
        power: bool | None = None,
        operation_mode: ATAOperationMode | None = None,
        set_temperature: float | None = None,
        set_fan_speed: ATAFanSpeed | None = None,
        vane_vertical_direction: ATAVaneVertical | None = None,
        vane_horizontal_direction: ATAVaneHorizontal | None = None,
        in_standby_mode: bool | None = None,
    ) -> None:
        """Control an Air-to-Air unit."""
        control = ATAUnitControl(
            power=power,
            operation_mode=operation_mode,
            set_temperature=set_temperature,
            set_fan_speed=set_fan_speed,
            vane_vertical_direction=vane_vertical_direction,
            vane_horizontal_direction=vane_horizontal_direction,
            in_standby_mode=in_standby_mode,
        )
        await self._request(f"/monitor/ataunit/{unit_id}", method=METH_PUT, json=control.to_api_payload())

    async def control_atw_unit(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        unit_id: str,
        *,
        power: bool | None = None,
        operation_mode_zone1: ATWZoneMode | None = None,
        operation_mode_zone2: ATWZoneMode | None = None,
        set_temperature_zone1: float | None = None,
        set_temperature_zone2: float | None = None,
        set_tank_water_temperature: float | None = None,
        forced_hot_water_mode: bool | None = None,
        in_standby_mode: bool | None = None,
        set_heat_flow_temperature_zone1: float | None = None,
        set_cool_flow_temperature_zone1: float | None = None,
        set_heat_flow_temperature_zone2: float | None = None,
        set_cool_flow_temperature_zone2: float | None = None,
    ) -> None:
        """Control an Air-to-Water unit."""
        control = ATWUnitControl(
            power=power,
            operation_mode_zone1=operation_mode_zone1,
            operation_mode_zone2=operation_mode_zone2,
            set_temperature_zone1=set_temperature_zone1,
            set_temperature_zone2=set_temperature_zone2,
            set_tank_water_temperature=set_tank_water_temperature,
            forced_hot_water_mode=forced_hot_water_mode,
            in_standby_mode=in_standby_mode,
            set_heat_flow_temperature_zone1=set_heat_flow_temperature_zone1,
            set_cool_flow_temperature_zone1=set_cool_flow_temperature_zone1,
            set_heat_flow_temperature_zone2=set_heat_flow_temperature_zone2,
            set_cool_flow_temperature_zone2=set_cool_flow_temperature_zone2,
        )
        await self._request(f"/monitor/atwunit/{unit_id}", method=METH_PUT, json=control.to_api_payload())

    async def get_energy_telemetry(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        unit_id: str,
        from_dt: datetime,
        to_dt: datetime,
        interval: str = "Hour",
        measure: str = "cumulative_energy_consumed_since_last_upload",
    ) -> list[TelemetryValue]:
        """Fetch energy telemetry for a unit."""
        params = {
            "from": from_dt.strftime("%Y-%m-%d %H:%M"),
            "to": to_dt.strftime("%Y-%m-%d %H:%M"),
            "interval": interval,
            "measure": measure,
        }
        data = await self._request(f"/telemetry/telemetry/energy/{unit_id}", params=params)

        measure_data: list[dict[str, object]] = data.get("measureData", [])
        entries = [MeasurementEntry.model_validate(entry) for entry in measure_data]
        if not entries:
            return []
        return entries[0].values

    async def get_outdoor_temperature(self, unit_id: str) -> float | None:
        """Fetch the latest outdoor temperature for an ATA unit.

        Endpoint: GET /report/v1/trendsummary
        Returns the most recent outdoor temperature in °C, or None if unavailable.
        """
        from_dt = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        to_dt = datetime.now(tz=UTC)
        params = {
            "unitId": unit_id,
            "period": "Daily",
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
            "to": to_dt.strftime("%Y-%m-%dT%H:%M:%S.0000000"),
        }
        data = await self._request("/report/v1/trendsummary", params=params)
        if not data:
            return None
        try:
            datasets: list[dict[str, object]] = data[0].get("datasets", [])  # type: ignore[index]
            for dataset in datasets:
                label = str(dataset.get("label", ""))
                if "OUTDOOR_TEMPERATURE" in label.upper():
                    points: list[dict[str, object]] = dataset.get("data", [])  # type: ignore[assignment]
                    if points:
                        return float(points[-1]["y"])  # type: ignore[arg-type]
        except (IndexError, KeyError, TypeError, ValueError):
            return None
        return None

    async def get_actual_telemetry(
        self,
        unit_id: str,
        measure: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[dict[str, str]]:
        """Fetch actual measurements for an ATW unit (flow/return/room temperatures).

        Endpoint: GET /telemetry/telemetry/actual/{unit_id}
        Common measures: flow_temperature, return_temperature, room_temperature.
        """
        params = {
            "from": from_dt.strftime("%Y-%m-%d %H:%M"),
            "to": to_dt.strftime("%Y-%m-%d %H:%M"),
            "measure": measure,
        }
        data = await self._request(f"/telemetry/telemetry/actual/{unit_id}", params=params)
        if not data:
            return []
        measure_data: list[dict[str, object]] = data.get("measureData", [])
        if not measure_data:
            return []
        values: list[dict[str, str]] = measure_data[0].get("values", [])  # type: ignore[assignment]
        return values

    async def __aenter__(self) -> Self:
        """Async enter.

        Returns
        -------
            The Melcloud Home object.

        """
        return self

    async def __aexit__(self, *_: object) -> None:
        """Async context manager exit."""
        await self._auth.close()
        if self._close_session and self._session:
            await self._session.close()
