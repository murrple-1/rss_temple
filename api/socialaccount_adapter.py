from allauth.account import app_settings as account_settings
from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from rest_framework.exceptions import APIException


class CannotDisconnect(APIException):
    status_code = 409


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def validate_disconnect(self, account, accounts):
        """
        Validate whether or not the socialaccount account can be
        safely disconnected.
        """
        if len(accounts) == 1:
            # No usable password would render the local account unusable
            if not account.user.has_usable_password():
                raise CannotDisconnect("Your account has no password set up.")
            # No email address, no password reset
            if (
                account_settings.EMAIL_VERIFICATION
                == account_settings.EmailVerificationMethod.MANDATORY
            ):
                if not EmailAddress.objects.filter(
                    user=account.user, verified=True
                ).exists():
                    raise CannotDisconnect(
                        "Your account has no verified e-mail address.",
                    )
