from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

import redis
from redis import ConnectionPool
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from app.core.config import get_settings


@lru_cache(maxsize=1)
def _get_pool() -> ConnectionPool:
    settings = get_settings()
    return ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        decode_responses=True,
        health_check_interval=5,
        retry=Retry(ExponentialBackoff(), 8),
    )


@contextmanager
def get_redis_client() -> Iterator[redis.Redis]:
    """Context manager to get a Redis client from the shared pool.

    Usage:
    ```python
    with get_redis_client() as client:
        client.ping()
    ```
    """
    client = redis.Redis(connection_pool=_get_pool())
    try:
        yield client
    finally:
        client.close()  # type: ignore
