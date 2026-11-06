from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


class AccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self, request, emailconfirmation):
        # link straight to the frontend's verify page, rather than to the API's
        # redirect to it, so the link doesn't depend on the request's `Host`
        return settings.ACCOUNT_CONFIRM_EMAIL_URL % {"key": emailconfirmation.key}
