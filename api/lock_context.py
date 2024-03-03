import contextlib

from django.core.cache import BaseCache
from redis_lock.django_cache import RedisCache as RedisLockCache


def lock_context(cache: BaseCache, lock_key: str) -> contextlib.AbstractContextManager:
    if isinstance(cache, RedisLockCache):
        return cache.lock(lock_key, expire=60, auto_renewal=True)  # pragma: no cover
    else:
        return contextlib.nullcontext()
