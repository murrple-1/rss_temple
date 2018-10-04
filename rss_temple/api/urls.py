from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r'^login/my/?$', views.my_login),
    re_path(r'^login/my/session/?$', views.my_login_session),
    re_path(r'^login/google/session/?$', views.google_login_session),
    re_path(r'^login/facebook/session/?$', views.facebook_login_session),

    re_path(r'^user/?$', views.user),

    re_path(r'^feed/?$', views.feed),
    re_path(r'^feeds/?$', views.feeds),
    re_path(r'^feed/subscribe/?$', views.feed_subscribe),
]
