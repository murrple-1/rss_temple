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

    re_path(r'^user/?$', views.user),

    re_path(r'^feed/?$', views.feed),
    re_path(r'^feeds/?$', views.feeds),
    re_path(r'^feed/subscribe/?$', views.feed_subscribe),

    re_path(r'^feedentry/({})/?$'.format(_uuid_regex), views.feed_entry),
    re_path(r'^feedentries/?$', views.feed_entries),
    re_path(r'^feedentry/read/({})/?$'.format(_uuid_regex), views.feed_entry_read),
    re_path(r'^feedentries/read/?$', views.feed_entries_read),
]
