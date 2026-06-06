"""Models for telemetry data from Melcloud Home."""

from pydantic import BaseModel, ConfigDict, Field


class TelemetryValue(BaseModel):
    """A single telemetry data point."""

    time: str
    value: str


class MeasurementEntry(BaseModel):
    """A single measure series within a telemetry response."""

    model_config = ConfigDict(populate_by_name=True)

    device_id: str | None = Field(default=None, alias="deviceId")
    type: str
    values: list[TelemetryValue]


class EnergyTelemetryEntry(BaseModel):
    """Top-level telemetry response containing one or more measure series."""

    model_config = ConfigDict(populate_by_name=True)

    measure_data: list[MeasurementEntry] = Field(alias="measureData")
