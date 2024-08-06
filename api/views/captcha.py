import datetime
import secrets
from typing import Any, cast

from captcha.audio import AudioCaptcha
from captcha.image import ImageCaptcha
from django.conf import settings
from django.core.cache import BaseCache, caches
from django.core.signals import setting_changed
from django.db.models.functions import Now
from django.dispatch import receiver
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api import throttling
from api.models import Captcha

_CAPTCHA_EXPIRY_INTERVAL: datetime.timedelta
_image_captcha: ImageCaptcha
_audio_captcha: AudioCaptcha
_CAPTCHA_SEND_ANSWER: bool


@receiver(setting_changed)
def _load_global_settings(*args: Any, **kwargs: Any):
    global _CAPTCHA_EXPIRY_INTERVAL
    global _image_captcha
    global _audio_captcha
    global _CAPTCHA_SEND_ANSWER

    _CAPTCHA_EXPIRY_INTERVAL = settings.CAPTCHA_EXPIRY_INTERVAL
    _image_captcha = ImageCaptcha(
        width=settings.CAPTCHA_IMAGE_WIDTH,
        height=settings.CAPTCHA_IMAGE_HEIGHT,
        fonts=settings.CAPTCHA_IMAGE_FONTS_DIR,
        font_sizes=cast(tuple[int], settings.CAPTCHA_IMAGE_FONT_SIZES),
    )
    _audio_captcha = AudioCaptcha(voicedir=settings.CAPTCHA_AUDIO_VOICES_DIR)
    _CAPTCHA_SEND_ANSWER = settings.CAPTCHA_SEND_ANSWER


_load_global_settings()


class NewCaptchaView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (throttling.AnonRateThrottle,)

    @extend_schema(
        summary="Get a new captcha key",
        description="Get a new captcha key",
        request=None,
        responses=OpenApiTypes.STR,
    )
    def post(self, request: Request):
        captcha = Captcha.objects.create(
            key=secrets.token_urlsafe(32),
            seed=secrets.token_hex(32),
            expires_at=(timezone.now() + _CAPTCHA_EXPIRY_INTERVAL),
        )

        return Response(captcha.key)


class CaptchaImageView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (throttling.AnonRateThrottle,)

    @extend_schema(
        summary="Download an image captcha",
        description="Download an image captcha",
        request=None,
        responses={(200, "image/png"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, *, key: str) -> HttpResponse:
        cache: BaseCache = caches["captcha"]

        captcha: Captcha
        try:
            captcha = Captcha.objects.get(key=key, expires_at__gt=Now())
        except Captcha.DoesNotExist:
            raise NotFound("captcha not found")

        cache_key = f"captcha_png_{key}"
        bytes_: bytes | None = cache.get(cache_key)
        cache_hit = True
        if bytes_ is None:
            cache_hit = False
            bytes_ = _image_captcha.generate(captcha.secret_phrase).getvalue()
            cache.set(cache_key, bytes_)

        response = HttpResponse(bytes_, content_type="image/png")
        response["Content-Length"] = len(bytes_)
        response["X-Cache-Hit"] = "YES" if cache_hit else "NO"

        if _CAPTCHA_SEND_ANSWER:
            response["X-Answer"] = captcha.secret_phrase  # pragma: no cover

        return response


class CaptchaAudioView(APIView):
    permission_classes = (permissions.AllowAny,)
    throttle_classes = (throttling.AnonRateThrottle,)

    @extend_schema(
        summary="Download an audio captcha",
        description="Download an audio captcha",
        request=None,
        responses={(200, "audio/wav"): OpenApiTypes.BINARY},
    )
    def get(self, request: Request, *, key: str) -> HttpResponse:
        cache: BaseCache = caches["captcha"]

        captcha: Captcha
        try:
            captcha = Captcha.objects.get(key=key, expires_at__gt=Now())
        except Captcha.DoesNotExist:
            raise NotFound("captcha not found")

        cache_key = f"captcha_wav_{key}"
        bytes_: bytes | None = cache.get(cache_key)
        cache_hit = True
        if bytes_ is None:
            cache_hit = False
            bytes_ = bytes(_audio_captcha.generate(captcha.secret_phrase))
            cache.set(cache_key, bytes_)

        response = HttpResponse(bytes_, content_type="audio/wav")
        response["Content-Length"] = len(bytes_)
        response["X-Cache-Hit"] = "YES" if cache_hit else "NO"

        if _CAPTCHA_SEND_ANSWER:
            response["X-Answer"] = captcha.secret_phrase  # pragma: no cover

        return response
