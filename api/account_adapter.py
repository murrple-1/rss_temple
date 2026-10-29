from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_url(self, request, emailconfirmation):
        # build the link from the `Site` domain rather than the request's
        # (attacker-controllable) `Host` header, so a forged `Host` can't
        # redirect the confirmation key to a foreign domain
        return super().get_email_confirmation_url(None, emailconfirmation)
