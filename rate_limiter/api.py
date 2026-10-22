import time

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel, Field

from rate_limiter.config import load_capacity, load_leak_rate
from rate_limiter.core import allow_request, create_rate_limiter, get_bucket_state


class RequestIn(BaseModel):
    """Body of POST /requests."""

    user_id: str = Field(min_length=1)
    timestamp: float | None = None


class DecisionOut(BaseModel):
    """Whether the request was allowed."""

    user_id: str
    allowed: bool


class BucketOut(BaseModel):
    """A user's bucket plus the limiter settings, for debugging."""

    user_id: str
    level: float
    last_ts: float
    capacity: float
    leak_rate: float


def create_app(capacity: float, leak_rate: float) -> FastAPI:
    """Build the API with its own global limiter."""
    app = FastAPI(title="Leaky Bucket Rate Limiter")
    app.state.limiter = create_rate_limiter(capacity, leak_rate)

    @app.post("/requests", response_model=DecisionOut)
    async def check_request(body: RequestIn, response: Response) -> DecisionOut:
        timestamp = body.timestamp if body.timestamp is not None else time.time()
        try:
            allowed, new_limiter = allow_request(
                app.state.limiter, body.user_id, timestamp
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        app.state.limiter = new_limiter
        if not allowed:
            response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
        return DecisionOut(user_id=body.user_id, allowed=allowed)

    @app.get("/buckets/{user_id}", response_model=BucketOut)
    async def read_bucket(user_id: str) -> BucketOut:
        bucket = get_bucket_state(app.state.limiter, user_id)
        if bucket is None:
            raise HTTPException(
                status_code=404, detail=f"No bucket for user '{user_id}'"
            )
        return BucketOut(
            user_id=user_id,
            level=bucket.level,
            last_ts=bucket.last_ts,
            capacity=app.state.limiter.capacity,
            leak_rate=app.state.limiter.leak_rate,
        )

    return app


app = create_app(load_capacity(), load_leak_rate())
