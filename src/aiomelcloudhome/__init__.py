"""Asynchronous Python client for Melcloud Home."""

from .aiomelcloudhome import MELCloudHome
from .auth import AbstractAuth, MelCloudHomeAuth, StaticTokenAuth
from .exceptions import (
    MelCloudHomeAuthenticationError,
    MelCloudHomeConnectionError,
    MelCloudHomeError,
    MelCloudHomeNotFoundError,
    MelCloudHomeTimeoutError,
    MelCloudHomeWebSocketError,
)
from .models import (
    ATACapabilities,
    ATAFanSpeed,
    ATAOperationMode,
    ATAUnit,
    ATAUnitControl,
    ATAVaneHorizontal,
    ATAVaneVertical,
    ATWCapabilities,
    ATWFrostProtection,
    ATWOperationMode,
    ATWUnit,
    ATWUnitControl,
    ATWZoneMode,
    Building,
    HolidayMode,
    UserContext,
)
from .models.realtime import UnitStateDelta
from .websocket import MELCloudHomeWebSocket

__all__ = [
    "ATACapabilities",
    "ATAFanSpeed",
    "ATAOperationMode",
    "ATAUnit",
    "ATAUnitControl",
    "ATAVaneHorizontal",
    "ATAVaneVertical",
    "ATWCapabilities",
    "ATWFrostProtection",
    "ATWOperationMode",
    "ATWUnit",
    "ATWUnitControl",
    "ATWZoneMode",
    "AbstractAuth",
    "Building",
    "HolidayMode",
    "MELCloudHome",
    "MELCloudHomeWebSocket",
    "MelCloudHomeAuth",
    "MelCloudHomeAuthenticationError",
    "MelCloudHomeConnectionError",
    "MelCloudHomeError",
    "MelCloudHomeNotFoundError",
    "MelCloudHomeTimeoutError",
    "MelCloudHomeWebSocketError",
    "StaticTokenAuth",
    "UnitStateDelta",
    "UserContext",
]
