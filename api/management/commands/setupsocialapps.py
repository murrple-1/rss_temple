from typing import Any

from allauth.socialaccount.models import SocialApp
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction


class Command(BaseCommand):
    help = "Setup the social apps"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("site_domain")
        parser.add_argument("site_name")
        parser.add_argument("google_client_id")
        parser.add_argument("google_secret")
        parser.add_argument("facebook_client_id")
        parser.add_argument("facebook_secret")

    def handle(self, *args: Any, **options: Any) -> None:
        site = Site.objects.get(id=settings.SITE_ID)

        site.domain = options["site_domain"]
        site.name = options["site_name"]

        google_social_app: SocialApp
        try:
            google_social_app = SocialApp.objects.get(provider="google")
        except SocialApp.DoesNotExist:
            self.stderr.write("new social app: Google")
            google_social_app = SocialApp(provider="google", name="Google", key="")
        google_social_app.client_id = options["google_client_id"]
        google_social_app.secret = options["google_secret"]

        facebook_social_app: SocialApp
        try:
            facebook_social_app = SocialApp.objects.get(provider="facebook")
        except SocialApp.DoesNotExist:
            self.stderr.write("new social app: Facebook")
            facebook_social_app = SocialApp(
                provider="facebook", name="Facebook", key=""
            )
        facebook_social_app.client_id = options["facebook_client_id"]
        facebook_social_app.secret = options["facebook_secret"]

        with transaction.atomic():
            site.save()
            google_social_app.save()
            facebook_social_app.save()

            site.socialapp_set.add(google_social_app, facebook_social_app)  # type: ignore

        self.stderr.write("social apps setup complete")
