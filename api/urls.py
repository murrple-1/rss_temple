from django.urls import re_path

from . import views

_uuid_regex = (
    r"[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}"
)

urlpatterns = [
    re_path(
        r"^auth/password/reset/?$",
        views.PasswordResetView.as_view(),
        name="rest_password_reset",
    ),
    re_path(
        r"^auth/password/reset/confirm/?$",
        views.PasswordResetConfirmView.as_view(),
        name="rest_password_reset_confirm",
    ),
    re_path(r"^auth/login/?$", views.LoginView.as_view(), name="rest_login"),
    re_path(r"^auth/logout/?$", views.LogoutView.as_view(), name="rest_logout"),
    re_path(
        r"^auth/password/change/?$",
        views.PasswordChangeView.as_view(),
        name="rest_password_change",
    ),
    re_path(r"^registration/?$", views.RegisterView.as_view(), name="rest_register"),
    re_path(
        r"^registration/verify-email/?$",
        views.VerifyEmailView.as_view(),
        name="rest_verify_email",
    ),
    re_path(
        r"^registration/resend-email/?$",
        views.ResendEmailVerificationView.as_view(),
        name="rest_resend_email",
    ),
    re_path(
        r"^account-confirm-email/(?P<key>[-:\w]+)/?$",
        views.VerifyEmailView.as_view(),
        name="account_confirm_email",
    ),
    re_path(r"^social/?", views.SocialAccountListView.as_view()),
    re_path(r"^social/google/?$", views.GoogleLoginView.as_view()),
    re_path(r"^social/google/connect/?$", views.GoogleConnectView.as_view()),
    re_path(r"^social/google/disconnect/?$", views.GoogleDisconnectView.as_view()),
    re_path(r"^social/facebook/?$", views.FacebookLoginView.as_view()),
    re_path(r"^social/facebook/connect/?$", views.FacebookConnectView.as_view()),
    re_path(r"^social/facebook/disconnect/?$", views.FacebookDisconnectView.as_view()),
    re_path(r"^user/?$", views.user),
    re_path(r"^user/attributes/?$", views.user_attributes),
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
    re_path(r"^explore/?$", views.explore),
]
