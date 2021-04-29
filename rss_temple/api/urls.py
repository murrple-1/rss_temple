from django.urls import re_path

from . import views

_uuid_regex = r'[0-9a-fA-F]{8}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{4}\-[0-9a-fA-F]{12}'

urlpatterns = [
    re_path(r'^login/my/?$', views.my_login),
    re_path(r'^login/google/?$', views.google_login),
    re_path(r'^login/facebook/?$', views.facebook_login),
    re_path(r'^login/my/session/?$', views.my_login_session),
    re_path(r'^login/google/session/?$', views.google_login_session),
    re_path(r'^login/facebook/session/?$', views.facebook_login_session),
    re_path(r'^session/?$', views.session),
    re_path(r'^passwordresettoken/request/?$',
            views.passwordresettoken_request),
    re_path(r'^passwordresettoken/reset/?$', views.passwordresettoken_reset),

    re_path(r'^user/?$', views.user),
    re_path(r'^user/verify/?$', views.user_verify),

    re_path(r'^feed/?$', views.feed),
    re_path(r'^feeds/query/?$', views.feeds_query),
    re_path(r'^feed/subscribe/?$', views.feed_subscribe),

    re_path(rf'^feedentry/({_uuid_regex})/?$', views.feed_entry),
    re_path(r'^feedentries/query/?$', views.feed_entries_query),
    re_path(r'^feedentries/query/stable/create/?$',
            views.feed_entries_query_stable_create),
    re_path(r'^feedentries/query/stable/?$', views.feed_entries_query_stable),
    re_path(rf'^feedentry/({_uuid_regex})/read/?$',
            views.feed_entry_read),
    re_path(r'^feedentries/read/?$', views.feed_entries_read),
    re_path(rf'^feedentry/({_uuid_regex})/favorite/?$',
            views.feed_entry_favorite),
    re_path(r'^feedentries/favorite/?$', views.feed_entries_favorite),

    re_path(rf'^usercategory(?:/({_uuid_regex}))?/?$',
            views.user_category),
    re_path(r'^usercategories/query/?$', views.user_categories_query),
    re_path(r'^usercategories/apply/?$', views.user_categories_apply),

    re_path(r'^opml/?$', views.opml),

    re_path(rf'^feed/subscribe/progress/({_uuid_regex})/?$',
            views.feed_subscription_progress),

    re_path(r'^explore/?$', views.explore),
]
