# aiomelcloudhome

Asynchronous Python client for the Melcloud Home API.

## Installation

```bash
pip install aiomelcloudhome
```

## Usage

```python
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
                    print(f"  ATA unit: {unit.name}, temp: {unit.room_temperature}°C")
                for unit in building.air_to_water_units:
                    print(f"  ATW unit: {unit.name}, tank: {unit.tank_water_temperature}°C")

asyncio.run(main())
```

## License

MIT
