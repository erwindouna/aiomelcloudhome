"""Asynchronous Python client for Melcloud Home."""


class MelCloudHomeError(Exception):
    """Generic exception for Melcloud Home errors."""


class MelCloudHomeConnectionError(MelCloudHomeError):
    """Exception raised for connection errors."""


class MelCloudHomeTimeoutError(MelCloudHomeError):
    """Exception raised for timeout errors."""


class MelCloudHomeAuthenticationError(MelCloudHomeError):
    """Exception raised for authentication errors."""


class MelCloudHomeNotFoundError(MelCloudHomeError):
    """Exception raised when a resource is not found."""


class MelCloudHomeWebSocketError(MelCloudHomeError):
    """Exception raised for unrecoverable WebSocket errors.

    Raised when the realtime stream cannot be established or sustained (for example the
    token endpoint returns a non-200 status). Callers should fall back to REST polling.
    """
