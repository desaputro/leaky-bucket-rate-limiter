import os

DEFAULT_CAPACITY = 5.0
DEFAULT_LEAK_RATE = 1.0


def load_capacity() -> float:
    """Read bucket capacity from RATE_LIMIT_CAPACITY, or use the default."""
    return float(os.environ.get("RATE_LIMIT_CAPACITY", DEFAULT_CAPACITY))


def load_leak_rate() -> float:
    """Read leak rate (units per second) from RATE_LIMIT_LEAK_RATE, or use the default."""
    return float(os.environ.get("RATE_LIMIT_LEAK_RATE", DEFAULT_LEAK_RATE))
