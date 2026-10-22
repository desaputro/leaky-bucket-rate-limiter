from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class Bucket:
    """One user's bucket: how full it is and when we last updated it."""

    level: float
    last_ts: float


@dataclass(frozen=True)
class RateLimiter:
    """All buckets plus the limiter's configuration."""

    capacity: float
    leak_rate: float
    buckets: Mapping[str, Bucket]


def create_rate_limiter(capacity: float, leak_rate: float) -> RateLimiter:
    """Create an empty rate limiter.

    Raises ValueError if capacity is not positive or leak_rate is negative.
    """
    if capacity <= 0:
        raise ValueError(f"capacity must be positive, got {capacity}")
    if leak_rate < 0:
        raise ValueError(f"leak_rate must not be negative, got {leak_rate}")
    return RateLimiter(
        capacity=capacity,
        leak_rate=leak_rate,
        buckets=MappingProxyType({}),
    )
