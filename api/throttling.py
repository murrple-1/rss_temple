from django.core.cache import caches
from rest_framework import throttling


class AnonRateThrottle(throttling.AnonRateThrottle):
    cache = caches["throttle"]


class UserRateThrottle(throttling.UserRateThrottle):
    cache = caches["throttle"]
