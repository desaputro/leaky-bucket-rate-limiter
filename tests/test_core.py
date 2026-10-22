import pytest

from rate_limiter.core import allow_request, create_rate_limiter


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


def test_first_request_is_allowed():
    limiter = create_rate_limiter(5, 1.0)

    allowed, limiter = allow_request(limiter, "user1", 0)

    assert allowed is True
    assert limiter.buckets["user1"].level == 1


def test_requests_one_second_apart_are_allowed():
    limiter = create_rate_limiter(5, 1.0)

    allowed, limiter = allow_request(limiter, "user1", 0)

    assert allowed is True
    assert limiter.buckets["user1"].level == 1

    allowed, limiter = allow_request(limiter, "user1", 1)

    assert allowed is True
    assert limiter.buckets["user1"].level == 1


def send_requests(limiter, user_id, timestamps):
    """Send one request per timestamp; return (list of allowed flags, final limiter)."""
    results = []
    for ts in timestamps:
        allowed, limiter = allow_request(limiter, user_id, ts)
        results.append(allowed)
    return results, limiter


def test_burst_over_capacity_is_rejected():
    limiter = create_rate_limiter(5, 1.0)

    results, limiter = send_requests(limiter, "user1", [0, 0, 0, 0, 0, 0])

    assert results == [True, True, True, True, True, False]
    assert limiter.buckets["user1"].level == 5


def test_request_allowed_after_leaking():
    limiter = create_rate_limiter(5, 1.0)

    results, limiter = send_requests(limiter, "user1", [0, 0, 0, 0, 0, 1])

    assert results == [True, True, True, True, True, True]


def test_request_rejected_before_enough_leak():
    limiter = create_rate_limiter(5, 1.0)

    results, limiter = send_requests(limiter, "user1", [0, 0, 0, 0, 0, 0.5])

    assert results == [True, True, True, True, True, False]
    assert limiter.buckets["user1"].level == pytest.approx(4.5)


def test_timestamp_going_backwards_does_not_leak():
    limiter = create_rate_limiter(5, 1.0)

    results, limiter = send_requests(limiter, "user1", [5, 3])
    assert results == [True, True]
    assert limiter.buckets["user1"].level == 2
    assert limiter.buckets["user1"].last_ts == 5


def test_zero_leak_rate_never_drains():
    limiter = create_rate_limiter(5, 0)

    results, limiter = send_requests(limiter, "user1", [0, 0, 0, 0, 0, 1000])
    assert results == [True, True, True, True, True, False]
