# aiomelcloudhome

[![GitHub Release][releases-shield]][releases]
[![Python Versions][python-versions-shield]][pypi]
![Project Stage][project-stage-shield]
![Project Maintenance][maintenance-shield]
[![License][license-shield]](LICENSE)

[![GitHub Activity][commits-shield]][commits-url]
[![PyPI Downloads][downloads-shield]][downloads-url]
[![GitHub Last Commit][last-commit-shield]][commits-url]
[![Open in Dev Containers][devcontainer-shield]][devcontainer]

[![Build Status][build-shield]][build-url]
[![Typing Status][typing-shield]][typing-url]
[![Code Coverage][codecov-shield]][codecov-url]

Asynchronous Python client for MELCloud Home.

## About

aiomelcloudhome is an async client for the MELCloud Home API, focused on:

- Fetching account context (buildings and devices)
- Controlling Air-to-Air units
- Controlling Air-to-Water units
- Reading telemetry (energy and actual measurements)

The library is under active development and endpoint coverage will keep expanding.

## Installation

~~~bash
pip install aiomelcloudhome
~~~

## Usage

### Authenticate with username and password

~~~python
import asyncio

from aiohttp import ClientSession

from aiomelcloudhome import MELCloudHome


async def main() -> None:
    async with ClientSession() as session:
        async with MELCloudHome(
            username="your@email.com",
            password="your_password",
            session=session,
        ) as client:
            context = await client.get_context()

            for building in context.buildings:
                print(f"Building: {building.name}")

                for unit in building.air_to_air_units:
                    print(f"ATA: {unit.name} (room: {unit.room_temperature} C)")

                for unit in building.air_to_water_units:
                    print(f"ATW: {unit.name} (tank: {unit.tank_water_temperature} C)")


if __name__ == "__main__":
    asyncio.run(main())
~~~

### Authenticate with an existing access token

~~~python
from aiomelcloudhome import MELCloudHome


client = MELCloudHome(access_token="YOUR_ACCESS_TOKEN")
~~~

### Control an Air-to-Air unit

~~~python
from aiomelcloudhome import ATAFanSpeed, ATAOperationMode, MELCloudHome


await client.control_ata_unit(
    "ata-unit-id",
    power=True,
    operation_mode=ATAOperationMode.HEAT,
    set_temperature=21.0,
    set_fan_speed=ATAFanSpeed.AUTO,
)
~~~

### Control an Air-to-Water unit

~~~python
from aiomelcloudhome import ATWZoneMode


await client.control_atw_unit(
    "atw-unit-id",
    power=True,
    operation_mode_zone1=ATWZoneMode.HEAT_ROOM_TEMPERATURE,
    set_temperature_zone1=21.0,
    set_tank_water_temperature=50.0,
)
~~~

### Fetch telemetry

~~~python
from datetime import UTC, datetime, timedelta


energy = await client.get_energy_telemetry(
    "unit-id",
    from_dt=datetime.now(UTC) - timedelta(days=1),
    to_dt=datetime.now(UTC),
)

outdoor = await client.get_outdoor_temperature("ata-unit-id")
~~~

### Live updates over WebSocket

Instead of polling `get_context()`, you can opt in to a live update stream. `stream_updates()`
connects to the MELCloud Home realtime WebSocket, reuses the client's existing authentication,
reconnects transparently, and yields a typed `UnitStateDelta` whenever a unit changes. Control,
telemetry and the initial state snapshot still use the REST API.

~~~python
async for delta in client.stream_updates():
    print(delta.unit_id, delta.unit_type, delta.changes)
    # e.g. changes == {"SetTemperature": 21.0} or {"OperationMode": ATAOperationMode.COOL}
~~~

The stream raises `MelCloudHomeWebSocketError` if the realtime channel cannot be established, so
you can fall back to polling.

For a long-lived listener that you need to start and stop (for example a Home Assistant
coordinator), use `client.websocket()` to hold a handle, run `stream()` in a background task, and
`close()` it on teardown:

~~~python
ws = client.websocket()
task = asyncio.create_task(_listen(ws))  # _listen iterates `async for delta in ws.stream()`

# on shutdown (e.g. async_unload_entry):
await ws.close()   # stops gracefully; stream() ends on its own
await task
~~~

More examples can be found in the examples directory.

## Documentation

Project documentation and API reference:
https://github.com/erwindouna/aiomelcloudhome

## Contributing

Contributions are welcome. Please open an issue or pull request.

For local development:

~~~bash
uv sync --all-groups && uv run pre-commit install
~~~

Run checks:

~~~bash
uv run pre-commit run --all-files
~~~

Run tests:

~~~bash
uv run pytest
~~~

Update snapshot tests:

~~~bash
uv run pytest --snapshot-update
~~~

## License

MIT License

Copyright (c) 2026 Erwin Douna

<!-- MARKDOWN LINKS & IMAGES -->

[build-shield]: https://github.com/erwindouna/aiomelcloudhome/actions/workflows/tests.yaml/badge.svg
[build-url]: https://github.com/erwindouna/aiomelcloudhome/actions/workflows/tests.yaml
[codecov-shield]: https://codecov.io/gh/erwindouna/aiomelcloudhome/branch/main/graph/badge.svg
[codecov-url]: https://codecov.io/gh/erwindouna/aiomelcloudhome
[commits-shield]: https://img.shields.io/github/commit-activity/y/erwindouna/aiomelcloudhome.svg
[commits-url]: https://github.com/erwindouna/aiomelcloudhome/commits/main
[devcontainer-shield]: https://img.shields.io/static/v1?label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode
[devcontainer]: https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/erwindouna/aiomelcloudhome
[downloads-shield]: https://img.shields.io/pypi/dm/aiomelcloudhome
[downloads-url]: https://pypistats.org/packages/aiomelcloudhome
[last-commit-shield]: https://img.shields.io/github/last-commit/erwindouna/aiomelcloudhome.svg
[license-shield]: https://img.shields.io/github/license/erwindouna/aiomelcloudhome.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-experimental-yellow.svg
[maintenance-shield]: https://img.shields.io/maintenance/yes/2026.svg
[pypi]: https://pypi.org/project/aiomelcloudhome/
[python-versions-shield]: https://img.shields.io/pypi/pyversions/aiomelcloudhome
[releases-shield]: https://img.shields.io/github/release/erwindouna/aiomelcloudhome.svg
[releases]: https://github.com/erwindouna/aiomelcloudhome/releases
[typing-shield]: https://github.com/erwindouna/aiomelcloudhome/actions/workflows/typing.yaml/badge.svg
[typing-url]: https://github.com/erwindouna/aiomelcloudhome/actions/workflows/typing.yaml
