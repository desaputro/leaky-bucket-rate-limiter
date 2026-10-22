# Leaky Bucket Rate Limiter

A small REST API backed by a single in-memory **leaky bucket** rate limiter.
Each user gets their own bucket; every request adds 1 unit, and the bucket
drains at a constant rate. A request that would overflow the bucket is rejected.

Built with Python, [FastAPI](https://fastapi.tiangolo.com/) and pytest.

## Requirements

- Python **3.10+** (developed on 3.14)
- `make` (optional; every command is also listed below)

## Quick start

```bash
make install   # create .venv and install dependencies
make run       # start the API on http://127.0.0.1:8000
```

Interactive API docs (Swagger UI): <http://127.0.0.1:8000/docs>

Without `make`:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn rate_limiter.api:app --reload
```

## Configuration

The global limiter is created once at startup from environment variables:

| Variable               | Meaning                       | Default |
|------------------------|-------------------------------|---------|
| `RATE_LIMIT_CAPACITY`  | Maximum bucket size (units)   | `5`     |
| `RATE_LIMIT_LEAK_RATE` | Units leaked per second       | `1.0`   |

```bash
RATE_LIMIT_CAPACITY=10 RATE_LIMIT_LEAK_RATE=2 make run
```

Invalid values (capacity ≤ 0, negative leak rate) stop the server at startup.

## API

### `POST /requests`: check whether a request is allowed

```bash
curl -i -X POST http://127.0.0.1:8000/requests \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "timestamp": 1700000000.5}'
```

| Field       | Type   | Required | Notes                                         |
|-------------|--------|----------|-----------------------------------------------|
| `user_id`   | string | yes      | Must not be empty                             |
| `timestamp` | number | no       | Unix epoch seconds; defaults to server clock  |

| Status | Body                                     | Meaning                     |
|--------|------------------------------------------|-----------------------------|
| `200`  | `{"user_id": "user1", "allowed": true}`  | Request fits in the bucket  |
| `429`  | `{"user_id": "user1", "allowed": false}` | Bucket would overflow       |
| `422`  | validation error                         | Missing/empty `user_id`, non-finite timestamp |

### `GET /buckets/{user_id}`: read a user's bucket (debugging)

```bash
curl -i http://127.0.0.1:8000/buckets/user1
```

| Status | Body                                                                                       |
|--------|--------------------------------------------------------------------------------------------|
| `200`  | `{"user_id": "user1", "level": 1.0, "last_ts": 1700000000.5, "capacity": 5.0, "leak_rate": 1.0}` |
| `404`  | User has never made a request                                                              |

## Running tests

```bash
make test      # unit tests (core) + API tests
make lint      # ruff lint + format check
```

Without `make`: `.venv/bin/python -m pytest -v`

## Project structure

```text
rate_limiter/
  core.py      # the three core functions; pure, no web code
  api.py       # FastAPI app; thin handlers that call core.py
  config.py    # capacity / leak rate from environment variables
tests/
  test_core.py # unit tests for the rate limiter logic
  test_api.py  # endpoint tests
```

## Design decisions and trade-offs

**Functional core.** `core.py` has no mutable state. `RateLimiter` and `Bucket`
are frozen dataclasses, and the buckets mapping is a read-only
`MappingProxyType`. `allow_request` returns `(allowed, new_limiter)` and never
changes the limiter it was given; tests check both properties.

**Lazy leaking.** There is no background timer. When a request arrives, the
bucket is drained by `elapsed_seconds × leak_rate` (never below 0) and then
the request is checked. This keeps the logic deterministic and easy to test
with explicit timestamps.

**Rejected requests still record the drain.** Draining is linear, so draining
in two steps gives the same result as one step. Saving the drained level on a
rejection is therefore safe, and it keeps `get_bucket_state` closer to reality.

**Edge cases handled in the core**

- First request from a new user: starts from an empty bucket.
- Burst/overflow: a request is allowed only if `level + 1 ≤ capacity`; a
  rejected request does not add to the bucket.
- Timestamps going backwards: treated as zero elapsed time (no negative leak),
  and `last_ts` never moves backwards.
- `NaN`/infinite timestamps: rejected with `ValueError`, because they would
  otherwise freeze a bucket forever.
- Floating-point rounding: the capacity check uses a small tolerance (`1e-9`).
- `leak_rate = 0` is allowed (the bucket never drains).

**`get_bucket_state` returns the last recorded state.** It takes no timestamp,
so it shows the bucket as of the user's last request, without draining it up
to "now".

**One global limiter, thin handlers.** The API keeps the limiter in
`app.state` and replaces it with the state returned by `allow_request`.
Handlers contain no rate-limiting logic. `create_app()` builds a fresh app and
limiter, so every API test runs in isolation.

**Single-threaded by design.** Handlers are `async def` and never await, so
on the single event-loop thread each read-and-replace of the limiter finishes
before the next request starts. Plain `def` handlers would run in a thread
pool and could lose updates.

**Known limitations**

- Each request copies the buckets mapping: O(number of users). Fine at this
  scale; a persistent data structure would make this about O(log n).
- Buckets are never removed, so memory grows with the number of users. A
  bucket that has fully drained is equivalent to having no bucket, so idle
  buckets could be evicted safely.
- State is in memory: lost on restart and not shared between processes.

## What I would change for production

- Store buckets in Redis and update them atomically, so
  multiple API instances share limits and survive restarts.
- Use the server clock only, rather than accepting client timestamps.
- Add a `Retry-After` header on `429` responses.
- Evict idle buckets, and add metrics on allowed/rejected requests.
