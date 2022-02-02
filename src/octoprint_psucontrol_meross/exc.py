class MerossPSUControlError(Exception):
    """A generic meross client exception."""


class MerossCacheError(MerossPSUControlError):
    """Cache-related error."""


class CacheGetError(MerossCacheError):
    """Unable acquire a value to be cached."""


class MerossClientError(MerossPSUControlError):
    """Meross cloud-related error."""
