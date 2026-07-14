"""Asynchronous example for MELCloud Home."""

import asyncio

from aiomelcloudhome import MELCloudHome


async def print_live_updates(client: MELCloudHome, *, max_updates: int = 5, timeout_seconds: float = 60.0) -> None:
    """Stream a few live unit-state updates over the WebSocket, then stop."""
    print(f"Listening for up to {max_updates} live updates (timeout {timeout_seconds:.0f}s)...")

    async def _run() -> None:
        count = 0
        async for delta in client.stream_updates():
            print(f"  Update: unit={delta.unit_id} type={delta.unit_type} changes={delta.changes}")
            count += 1
            if count >= max_updates:
                break

    try:
        await asyncio.wait_for(_run(), timeout=timeout_seconds)
    except TimeoutError:
        print("  (timed out waiting for updates)")


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

        # Opt-in live updates instead of polling get_context().
        await print_live_updates(client)


if __name__ == "__main__":
    asyncio.run(main())
