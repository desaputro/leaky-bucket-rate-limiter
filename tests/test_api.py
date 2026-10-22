from fastapi.testclient import TestClient

from rate_limiter.api import create_app


def make_client(capacity: float = 2, leak_rate: float = 1.0) -> TestClient:
    """Fresh app and limiter per test, so tests don't share state."""
    return TestClient(create_app(capacity, leak_rate))


def test_allowed_request_returns_200():
    client = make_client()

    response = client.post("/requests", json={"user_id": "user1", "timestamp": 0})

    assert response.status_code == 200
    assert response.json() == {"user_id": "user1", "allowed": True}


def test_request_over_capacity_returns_429():
    client = make_client(capacity=1)

    client.post("/requests", json={"user_id": "user1", "timestamp": 0})
    response = client.post("/requests", json={"user_id": "user1", "timestamp": 0})

    assert response.status_code == 429
    assert response.json() == {"user_id": "user1", "allowed": False}


def test_bucket_state_after_request():
    client = make_client()
    client.post("/requests", json={"user_id": "user1", "timestamp": 10})

    response = client.get("/buckets/user1")

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user1",
        "level": 1,
        "last_ts": 10,
        "capacity": 2,
        "leak_rate": 1.0,
    }


def test_unknown_user_returns_404():
    client = make_client()

    response = client.get("/buckets/nobody")

    assert response.status_code == 404


def test_missing_timestamp_uses_server_clock():
    client = make_client()

    response = client.post("/requests", json={"user_id": "user1"})

    assert response.status_code == 200
    assert client.get("/buckets/user1").json()["last_ts"] > 0


def test_invalid_body_returns_422():
    client = make_client()

    assert client.post("/requests", json={"user_id": ""}).status_code == 422
    assert client.post("/requests", json={"timestamp": 0}).status_code == 422
