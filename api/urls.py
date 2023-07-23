from django.conf import settings
from django.urls import re_path
from django.views.generic import RedirectView

from . import views

_uuid_regex = (
    r"[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}"
)

urlpatterns = [
    re_path(
        r"^auth/password/reset/?$",
        views.PasswordResetView.as_view(),
    ),
    re_path(
        r"^auth/password/reset/confirm/?$",
        views.PasswordResetConfirmView.as_view(),
    ),
    re_path(r"^auth/login/?$", views.LoginView.as_view()),
    re_path(r"^auth/logout/?$", views.LogoutView.as_view()),
    re_path(r"^auth/user/?$", views.UserDetailsView.as_view()),
    re_path(
        r"^auth/password/change/?$",
        views.PasswordChangeView.as_view(),
    ),
    re_path(r"^auth/user/attributes/?$", views.UserAttributesView.as_view()),
    re_path(
        r"^auth/redirect/passwordresetconfirm/(?P<userId>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,32})/?$",
        views.PasswordResetConfirmRedirectView.as_view(),
        name="password_reset_confirm",
    ),
    re_path(r"^registration/?$", views.RegisterView.as_view(), name="rest_register"),
    re_path(
        r"^registration/verifyemail/?$",
        views.VerifyEmailView.as_view(),
        name="rest_verify_email",
    ),
    re_path(
        r"^registration/resendemail/?$",
        views.ResendEmailVerificationView.as_view(),
        name="rest_resend_email",
    ),
    re_path(
        r"^registration/redirect/accountconfirmemail/(?P<key>[-:\w]+)/?$",
        RedirectView.as_view(url=settings.ACCOUNT_CONFIRM_EMAIL_URL, query_string=True),
        name="account_confirm_email",
    ),
    re_path(
        r"^registration/redirect/accountemailverificationsent/?$",
        RedirectView.as_view(
            url=settings.ACCOUNT_EMAIL_VERIFICATION_SENT_URL, query_string=True
        ),
        name="account_email_verification_sent",
    ),
    re_path(
        r"^social/?$",
        views.SocialAccountListView.as_view(),
    ),
    re_path(r"^social/google/?$", views.GoogleLogin.as_view()),
    re_path(r"^social/google/connect/?$", views.GoogleConnect.as_view()),
    re_path(
        r"^social/google/disconnect/?$",
        views.GoogleDisconnect.as_view(),
    ),
    re_path(r"^social/facebook/?$", views.FacebookLogin.as_view()),
    re_path(
        r"^social/facebook/connect/?$",
        views.FacebookConnect.as_view(),
    ),
    re_path(
        r"^social/facebook/disconnect/?$",
        views.FacebookDisconnect.as_view(),
    ),
    re_path(
        r"^social/redirect/socialaccountconnections",
        RedirectView.as_view(url=settings.SOCIAL_CONNECTIONS_URL, query_string=True),
        name="socialaccount_connections",
    ),
    re_path(r"^feed/?$", views.feed),
    re_path(r"^feeds/query/?$", views.feeds_query),
    re_path(r"^feed/subscribe/?$", views.feed_subscribe),
    re_path(rf"^feedentry/({_uuid_regex})/?$", views.feed_entry),
    re_path(r"^feedentries/query/?$", views.feed_entries_query),
    re_path(
        r"^feedentries/query/stable/create/?$", views.feed_entries_query_stable_create
    ),
    re_path(r"^feedentries/query/stable/?$", views.feed_entries_query_stable),
    re_path(rf"^feedentry/({_uuid_regex})/read/?$", views.feed_entry_read),
    re_path(r"^feedentries/read/?$", views.feed_entries_read),
    re_path(rf"^feedentry/({_uuid_regex})/favorite/?$", views.feed_entry_favorite),
    re_path(r"^feedentries/favorite/?$", views.feed_entries_favorite),
    re_path(rf"^usercategory(?:/({_uuid_regex}))?/?$", views.user_category),
    re_path(r"^usercategories/query/?$", views.user_categories_query),
    re_path(r"^usercategories/apply/?$", views.user_categories_apply),
    re_path(r"^opml/?$", views.opml),
    re_path(
        rf"^feed/subscribe/progress/({_uuid_regex})/?$",
        views.feed_subscription_progress,
    ),
    re_path(r"^explore/?$", views.ExploreView.as_view()),
]
