from dj_rest_auth.registration.views import RegisterView as _RegisterView
from dj_rest_auth.registration.views import ResendEmailVerificationView, VerifyEmailView
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters

sensitive_post_parameters_m = method_decorator(
    sensitive_post_parameters("password"),
)


class RegisterView(_RegisterView):
    @sensitive_post_parameters_m
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)


__all__ = [
    "RegisterView",
    "VerifyEmailView",
    "ResendEmailVerificationView",
]
