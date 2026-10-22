import pytest

from rate_limiter.core import create_rate_limiter


def test_create_rate_limiter_sets_config():
    limiter = create_rate_limiter(5, 1.0)

    assert limiter.capacity == 5
    assert limiter.leak_rate == 1.0
    assert len(limiter.buckets) == 0


@pytest.mark.parametrize(
    "capacity, leak_rate",
    [
        (0, 1.0),
        (-1, 1.0),
        (5, -1),
    ],
)
def test_invalid_config_raises(capacity, leak_rate):
    with pytest.raises(ValueError):
        create_rate_limiter(capacity, leak_rate)


def test_zero_leak_rate_is_allowed():
    limiter = create_rate_limiter(5, 0)

    assert limiter.leak_rate == 0
