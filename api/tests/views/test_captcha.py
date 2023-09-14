import datetime
import logging
from typing import ClassVar

from django.core.cache import BaseCache, caches
from django.test import TestCase
from django.utils import timezone

from api.models import Captcha
from api.tests.utils import (
    reusable_captcha_key,
    reusable_captcha_seed,
    throttling_monkey_patch,
)


class CaptchaTestCase(TestCase):
    old_app_logger_level: ClassVar[int]
    old_django_logger_level: ClassVar[int]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.old_app_logger_level = logging.getLogger("rss_temple").getEffectiveLevel()
        cls.old_django_logger_level = logging.getLogger("django").getEffectiveLevel()

        logging.getLogger("rss_temple").setLevel(logging.CRITICAL)
        logging.getLogger("django").setLevel(logging.CRITICAL)

        throttling_monkey_patch()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()

        logging.getLogger("rss_temple").setLevel(cls.old_app_logger_level)
        logging.getLogger("django").setLevel(cls.old_django_logger_level)

    def test_NewCaptchaView_post(self):
        response = self.client.post(
            "/api/captcha",
        )
        self.assertEqual(response.status_code, 200, response.content)

        json_ = response.json()

        self.assertIs(type(json_), str)

    def test_CaptchaImageView_get(self):
        cache: BaseCache = caches["captcha"]

        captcha = Captcha.objects.create(
            key=reusable_captcha_key(),
            seed=reusable_captcha_seed(),
            expires_at=(timezone.now() + datetime.timedelta(days=1)),
        )
        cache_key = f"captcha_png_{captcha.key}"
        self.assertFalse(cache.delete(cache_key))

        response = self.client.get(
            f"/api/captcha/image/{captcha.key}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("X-Cache-Hit", response.headers)
        self.assertEqual(response.headers["X-Cache-Hit"], "NO")

        response = self.client.get(
            f"/api/captcha/image/{captcha.key}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("X-Cache-Hit", response.headers)
        self.assertEqual(response.headers["X-Cache-Hit"], "YES")

    def test_CaptchaImageView_get_notfound(self):
        response = self.client.get(
            "/api/captcha/image/badkey",
        )
        self.assertEqual(response.status_code, 404, response.content)

    def test_CaptchaAudioView_get(self):
        cache: BaseCache = caches["captcha"]

        captcha = Captcha.objects.create(
            key=reusable_captcha_key(),
            seed=reusable_captcha_seed(),
            expires_at=(timezone.now() + datetime.timedelta(days=1)),
        )
        cache_key = f"captcha_wav_{captcha.key}"
        self.assertFalse(cache.delete(cache_key))

        response = self.client.get(
            f"/api/captcha/audio/{captcha.key}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("X-Cache-Hit", response.headers)
        self.assertEqual(response.headers["X-Cache-Hit"], "NO")

        response = self.client.get(
            f"/api/captcha/audio/{captcha.key}",
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("X-Cache-Hit", response.headers)
        self.assertEqual(response.headers["X-Cache-Hit"], "YES")

    def test_CaptchaAudioView_get_notfound(self):
        response = self.client.get(
            "/api/captcha/audio/badkey",
        )
        self.assertEqual(response.status_code, 404, response.content)
