"""Backend error hierarchy."""


class PixelForgeError(Exception):
    """Base class for all backend errors."""


class BackendUnavailableError(PixelForgeError):
    """Raised when a generation backend cannot run on this machine."""


class JobCancelledError(PixelForgeError):
    """Raised inside a running job when cancellation is requested."""


class InvalidPaletteError(PixelForgeError):
    """Raised when a palette file or definition is malformed."""


class UnknownRegistryKeyError(PixelForgeError):
    """Raised when a style, mode, palette, or exporter id is not registered."""
