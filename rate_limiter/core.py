import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType

# tolerance for floating-point rounding when comparing levels.
EPSILON = 1e-9


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


def _leak(bucket: Bucket, now: float, leak_rate: float) -> Bucket:
    """Return the bucket drained up to `now`; time never runs backwards."""
    elapsed = max(0, now - bucket.last_ts)
    level = max(0, bucket.level - elapsed * leak_rate)
    return Bucket(
        level=level,
        last_ts=max(bucket.last_ts, now),
    )


def allow_request(
    limiter: RateLimiter, user_id: str, timestamp: float
) -> tuple[bool, RateLimiter]:
    """Decide whether a request fits in the user's bucket.

    Returns (allowed, new_limiter). The given limiter is never modified.
    Raises ValueError if timestamp is NaN or infinite.
    """
    if not math.isfinite(timestamp):
        raise ValueError(f"timestamp must be a finite number, got {timestamp}")
    current = limiter.buckets.get(user_id)
    if current is None:
        current = Bucket(level=0, last_ts=timestamp)
    leaked = _leak(current, timestamp, limiter.leak_rate)

    allowed = leaked.level + 1 <= limiter.capacity + EPSILON
    updated = replace(leaked, level=leaked.level + 1) if allowed else leaked

    new_buckets = {**limiter.buckets, user_id: updated}
    return allowed, replace(limiter, buckets=MappingProxyType(new_buckets))


def get_bucket_state(limiter: RateLimiter, user_id: str) -> Bucket | None:
    """Return the user's last recorded bucket, or None if they never made a request."""
    return limiter.buckets.get(user_id)
