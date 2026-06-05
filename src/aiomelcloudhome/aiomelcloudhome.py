"""Asynchronous Python client for Melcloud Home."""

from __future__ import annotations

import socket
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Self

import aiohttp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential
from yarl import URL

from .auth import MelCloudHomeAuth
from .exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeNotFoundError,
    MelCloudHomeTimeoutError,
)
from .models.context import UserContext

_API_BASE = "https://mobile.bff.melcloudhome.com"
_USER_AGENT = "MonitorAndControl.App.Mobile/52 CFNetwork/3860.400.51 Darwin/25.3.0"


@dataclass(slots=True, kw_only=True)
class MELCloudHome:
    """Asynchronous client for the Melcloud Home API."""

    username: str
    password: str
    session: aiohttp.ClientSession | None = None
    request_timeout: float = 10.0

    _session: aiohttp.ClientSession = field(default=None, init=False, repr=False)  # type: ignore[assignment]
    _auth: MelCloudHomeAuth = field(default=None, init=False, repr=False)  # type: ignore[assignment]
    _close_session: bool = field(default=False, init=False)

    async def __aenter__(self) -> Self:
        """Async context manager entry."""
        if self.session is None:
            self._session = aiohttp.ClientSession()
            self._close_session = True
        else:
            self._session = self.session

        self._auth = MelCloudHomeAuth(
            username=self.username,
            password=self.password,
            session=self._session,
        )
        await self._auth.authenticate()
        return self

    async def __aexit__(self, *_: object) -> None:
        """Async context manager exit."""
        if self._close_session and self._session:
            await self._session.close()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated API request with retry logic."""
        await self._auth.ensure_valid_token()

        url = URL(_API_BASE) / path.lstrip("/")

        headers = {
            "Authorization": f"Bearer {self._auth.access_token}",
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": _USER_AGENT,
        }

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=aiohttp.ClientTimeout(total=self.request_timeout),
            ) as resp:
                if resp.status == 304:  # Not Modified
                    return {}
                if resp.status == 401:
                    raise MelCloudHomeAuthenticationError("Authentication failed — token rejected")
                if resp.status == 404:
                    raise MelCloudHomeNotFoundError(f"Resource not found: {path}")
                resp.raise_for_status()
                if resp.content_length == 0 or resp.status == 204:
                    return {}
                return await resp.json(content_type=None)  # type: ignore[no-any-return]
        except MelCloudHomeAuthenticationError:
            raise
        except MelCloudHomeNotFoundError:
            raise
        except aiohttp.ServerTimeoutError as err:
            raise MelCloudHomeTimeoutError(f"Request timed out: {err}") from err
        except aiohttp.ClientConnectionError as err:
            raise MelCloudHomeConnectionError(f"Connection error: {err}") from err
        except socket.gaierror as err:
            raise MelCloudHomeConnectionError(f"DNS resolution failed: {err}") from err

    @retry(
        retry=retry_if_exception_type((MelCloudHomeConnectionError, MelCloudHomeTimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request with automatic retry on transient errors."""
        return await self._request(method, path, params=params, json=json)

    async def get_context(self) -> UserContext:
        """Fetch the full user context (all buildings and devices).

        Endpoint: GET /context
        """
        data = await self._request_with_retry("GET", "/context")
        return UserContext.from_api(data)

    async def control_ata_unit(
        self,
        unit_id: str,
        *,
        power: bool | None = None,
        operation_mode: str | None = None,
        set_temperature: float | None = None,
        set_fan_speed: str | None = None,
        vane_vertical_direction: str | None = None,
        vane_horizontal_direction: str | None = None,
        in_standby_mode: bool | None = None,
    ) -> None:
        """Control an Air-to-Air unit.

        Endpoint: PUT /monitor/ataunit/{unit_id}
        All fields are required by the API; pass None for fields you do not want to change.
        """
        payload: dict[str, Any] = {
            "power": power,
            "operationMode": operation_mode,
            "setTemperature": set_temperature,
            "setFanSpeed": set_fan_speed,
            "vaneVerticalDirection": vane_vertical_direction,
            "vaneHorizontalDirection": vane_horizontal_direction,
            "temperatureIncrementOverride": None,
            "inStandbyMode": in_standby_mode,
        }
        await self._request_with_retry("PUT", f"/monitor/ataunit/{unit_id}", json=payload)

    async def control_atw_unit(
        self,
        unit_id: str,
        *,
        power: bool | None = None,
        set_temperature_zone1: float | None = None,
        set_temperature_zone2: float | None = None,
        operation_mode_zone1: str | None = None,
        operation_mode_zone2: str | None = None,
        set_tank_water_temperature: float | None = None,
        forced_hot_water_mode: bool | None = None,
        in_standby_mode: bool | None = None,
        set_heat_flow_temperature_zone1: float | None = None,
        set_cool_flow_temperature_zone1: float | None = None,
        set_heat_flow_temperature_zone2: float | None = None,
        set_cool_flow_temperature_zone2: float | None = None,
    ) -> None:
        """Control an Air-to-Water unit.

        Endpoint: PUT /monitor/atwunit/{unit_id}
        All fields are required by the API; pass None for fields you do not want to change.
        """
        payload: dict[str, Any] = {
            "power": power,
            "setTemperatureZone1": set_temperature_zone1,
            "setTemperatureZone2": set_temperature_zone2,
            "operationModeZone1": operation_mode_zone1,
            "operationModeZone2": operation_mode_zone2,
            "setTankWaterTemperature": set_tank_water_temperature,
            "forcedHotWaterMode": forced_hot_water_mode,
            "inStandbyMode": in_standby_mode,
            "setHeatFlowTemperatureZone1": set_heat_flow_temperature_zone1,
            "setCoolFlowTemperatureZone1": set_cool_flow_temperature_zone1,
            "setHeatFlowTemperatureZone2": set_heat_flow_temperature_zone2,
            "setCoolFlowTemperatureZone2": set_cool_flow_temperature_zone2,
        }
        await self._request_with_retry("PUT", f"/monitor/atwunit/{unit_id}", json=payload)

    async def get_energy_telemetry(
        self,
        unit_id: str,
        from_dt: datetime,
        to_dt: datetime,
        interval: str = "Hour",
        measure: str = "cumulative_energy_consumed_since_last_upload",
    ) -> list[dict[str, str]]:
        """Fetch energy telemetry for a unit.

        Endpoint: GET /telemetry/telemetry/energy/{unit_id}
        Returns a list of {time, value} dicts. Values are cumulative Wh as strings.
        """
        params = {
            "from": from_dt.strftime("%Y-%m-%d %H:%M"),
            "to": to_dt.strftime("%Y-%m-%d %H:%M"),
            "interval": interval,
            "measure": measure,
        }
        data = await self._request_with_retry("GET", f"/telemetry/telemetry/energy/{unit_id}", params=params)
        if not data:
            return []
        measure_data: list[dict[str, object]] = data.get("measureData", [])
        if not measure_data:
            return []
        values: list[dict[str, str]] = measure_data[0].get("values", [])  # type: ignore[assignment]
        return values

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
        data = await self._request_with_retry("GET", "/report/v1/trendsummary", params=params)
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
        data = await self._request_with_retry("GET", f"/telemetry/telemetry/actual/{unit_id}", params=params)
        if not data:
            return []
        measure_data: list[dict[str, object]] = data.get("measureData", [])
        if not measure_data:
            return []
        values: list[dict[str, str]] = measure_data[0].get("values", [])  # type: ignore[assignment]
        return values
