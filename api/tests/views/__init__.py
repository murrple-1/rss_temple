from django.test import TestCase, modify_settings


@modify_settings(
    MIDDLEWARE={
        "remove": ["api.middleware.throttle.ThrottleMiddleware"],
    }
)
class ViewTestCase(TestCase):
    pass
