from django.conf import settings
from django.urls import re_path
from django.views.generic import RedirectView

from . import views

_uuid_regex = r"(?P<uuid>[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12})"

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
        RedirectView.as_view(
            url=settings.PASSWORD_RESET_CONFIRM_URL_FORMAT, query_string=True
        ),
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
        r"^social/redirect/socialaccountconnections/?$",
        RedirectView.as_view(url=settings.SOCIAL_CONNECTIONS_URL, query_string=True),
        name="socialaccount_connections",
    ),
    re_path(r"^captcha/?$", views.NewCaptchaView.as_view()),
    re_path(
        r"^captcha/image/(?P<key>[A-Za-z0-9_\-]+)/?$", views.CaptchaImageView.as_view()
    ),
    re_path(
        r"^captcha/audio/(?P<key>[A-Za-z0-9_\-]+)/?$", views.CaptchaAudioView.as_view()
    ),
    re_path(r"^user/meta/readcount/?$", views.ReadCountView.as_view()),
    re_path(r"^feed/?$", views.FeedView.as_view()),
    re_path(r"^feeds/query/?$", views.FeedsQueryView.as_view()),
    re_path(r"^feed/subscribe/?$", views.FeedSubscribeView.as_view()),
    re_path(rf"^feedentry/{_uuid_regex}/?$", views.FeedEntryView.as_view()),
    re_path(r"^feedentries/query/?$", views.FeedEntriesQueryView.as_view()),
    re_path(
        r"^feedentries/query/stable/create/?$",
        views.FeedEntriesQueryStableCreateView.as_view(),
    ),
    re_path(
        r"^feedentries/query/stable/?$", views.FeedEntriesQueryStableView.as_view()
    ),
    re_path(rf"^feedentry/{_uuid_regex}/read/?$", views.FeedEntryReadView.as_view()),
    re_path(r"^feedentries/read/?$", views.FeedEntriesReadView.as_view()),
    re_path(
        rf"^feedentry/{_uuid_regex}/favorite/?$", views.FeedEntryFavoriteView.as_view()
    ),
    re_path(r"^feedentries/favorite/?$", views.FeedEntriesFavoriteView.as_view()),
    re_path(rf"^usercategory/?$", views.UserCategoryCreateView.as_view()),
    re_path(rf"^usercategory/{_uuid_regex}/?$", views.UserCategoryView.as_view()),
    re_path(r"^usercategories/query/?$", views.UserCategoriesQueryView.as_view()),
    re_path(r"^usercategories/apply/?$", views.UserCategoriesApplyView.as_view()),
    re_path(r"^opml/?$", views.OPMLView.as_view()),
    re_path(
        rf"^feed/subscribe/progress/{_uuid_regex}/?$",
        views.FeedSubscriptionProgressView.as_view(),
    ),
    re_path(r"^explore/?$", views.ExploreView.as_view()),
]
