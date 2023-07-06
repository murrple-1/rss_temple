from django.urls import re_path
from knox import views as knox_views

from . import views

_uuid_regex = (
    r"[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}"
)

urlpatterns = [
    re_path(r"^login/my/?$", views.my_login),
    re_path(r"^login/?", views.LoginView.as_view(), name="knox_login"),
    re_path(r"^logout/?", knox_views.LogoutView.as_view(), name="knox_logout"),
    re_path(r"^logoutall/?", knox_views.LogoutAllView.as_view(), name="knox_logoutall"),
    re_path(r"^passwordresettoken/request/?$", views.passwordresettoken_request),
    re_path(r"^passwordresettoken/reset/?$", views.passwordresettoken_reset),
    re_path(r"^user/?$", views.user),
    re_path(r"^user/verify/?$", views.user_verify),
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
