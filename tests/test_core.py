from dataclasses import FrozenInstanceError

import pytest

from rate_limiter.core import (
    Bucket,
    allow_request,
    create_rate_limiter,
    get_bucket_state,
)


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


def test_users_have_independent_buckets():
    limiter = create_rate_limiter(5, 1.0)

    user1_results, limiter = send_requests(limiter, "user1", [0, 0, 0, 0, 0, 0])
    user2_allowed, limiter = allow_request(limiter, "user2", 0)

    assert user1_results[-1] is False
    assert user2_allowed is True
    assert limiter.buckets["user1"].level == 5
    assert limiter.buckets["user2"].level == 1


def test_get_bucket_state_returns_none_for_unknown_user():
    limiter = create_rate_limiter(5, 1.0)

    assert get_bucket_state(limiter, "nobody") is None


def test_get_bucket_state_returns_bucket_after_request():
    limiter = create_rate_limiter(5, 1.0)

    _, limiter = allow_request(limiter, "user1", 10)

    assert get_bucket_state(limiter, "user1") == Bucket(level=1, last_ts=10)


def test_allow_request_does_not_modify_original_limiter():
    original = create_rate_limiter(5, 1.0)

    _, after_first = allow_request(original, "user1", 0)
    _, after_second = allow_request(after_first, "user1", 0)

    assert len(original.buckets) == 0
    assert after_first.buckets["user1"].level == 1
    assert after_second.buckets["user1"].level == 2


def test_limiter_cannot_be_mutated():
    limiter = create_rate_limiter(5, 1.0)

    with pytest.raises(TypeError):
        limiter.buckets["user1"] = Bucket(level=0, last_ts=0)
    with pytest.raises(FrozenInstanceError):
        limiter.capacity = 10
