import random

from django.http import HttpRequest

# silk masks sensitive keys in request bodies, but stores response bodies
# verbatim; these endpoints return live auth tokens (e.g. `{"key": ...}`)
_EXCLUDED_PATH_PREFIXES = (
    "/api/auth/",
    "/api/registration",
    "/api/social",
)


def should_intercept(request: HttpRequest) -> bool:
    if request.path.startswith(_EXCLUDED_PATH_PREFIXES):
        return False

    # setting `SILKY_INTERCEPT_FUNC` disables silk's own percentage sampling,
    # so re-apply it here
    from silk.config import SilkyConfig

    intercept_percent = SilkyConfig().SILKY_INTERCEPT_PERCENT
    return intercept_percent >= 100 or random.random() < intercept_percent / 100.0
