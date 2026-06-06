"""Asynchronous example for MELCloud Home."""

import asyncio

from aiomelcloudhome import MELCloudHome


async def main() -> None:
    """Run the example."""
    async with MELCloudHome(
        username="YOUR_USERNAME",
        password="YOUR_PASSWORD",
    ) as client:
        context = await client.get_context()

        for building in context.buildings:
            print(f"Building: {building.name}")

            for unit in building.air_to_air_units:
                print(f"  ATA unit: {unit.name}")
                print(f"    Power: {unit.power}")
                print(f"    Mode: {unit.operation_mode}")
                print(f"    Set temperature: {unit.set_temperature}°C")
                print(f"    Room temperature: {unit.room_temperature}°C")
                print(f"    Fan speed: {unit.set_fan_speed}")

            for atw_unit in building.air_to_water_units:
                print(f"  ATW unit: {atw_unit.name}")
                print(f"    Power: {atw_unit.power}")
                print(f"    Mode: {atw_unit.operation_mode}")
                print(f"    Zone 1 temperature: {atw_unit.room_temperature_zone1}°C")
                print(f"    Tank temperature: {atw_unit.tank_water_temperature}°C")


if __name__ == "__main__":
    asyncio.run(main())
