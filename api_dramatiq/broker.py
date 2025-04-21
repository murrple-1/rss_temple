import os
import ssl

from dramatiq.broker import Broker
from dramatiq.middleware import (
    AgeLimit,
    Callbacks,
    Middleware,
    Pipelines,
    Retries,
    ShutdownNotifications,
    TimeLimit,
)
from dramatiq.results import Results
from dramatiq.results.backends import RedisBackend

_REDIS_URL = os.getenv("APP_REDIS_URL", "redis://valkey:6379")
_BROKER_URL = f"{_REDIS_URL}/5"
_RESULTS_URL = f"{_REDIS_URL}/6"

results_backend = RedisBackend(url=_RESULTS_URL)

_middleware: list[Middleware] = [
    AgeLimit(),
    TimeLimit(),
    ShutdownNotifications(),
    Callbacks(),
    Pipelines(),
    Retries(),
    Results(backend=results_backend),
]

broker: Broker

if _BROKER_URL.startswith("amqp"):
    from dramatiq.brokers.rabbitmq import RabbitmqBroker

    broker = RabbitmqBroker(
        url=_BROKER_URL,
        middleware=_middleware,
    )
else:
    from dramatiq.brokers.redis import RedisBroker

    broker = RedisBroker(
        url=_BROKER_URL,
        middleware=_middleware,
        ssl_cert_reqs=ssl.CERT_REQUIRED if _BROKER_URL.startswith("rediss") else None,
    )
