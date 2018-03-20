from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r'^login/my/?$', views.my_login),
    re_path(r'^login/my/session/?$', views.my_login_session),

    re_path(r'^user/?$', views.user),

    re_path('^channel/?$', views.channel),
    re_path('^channels/?$', views.channels),

    #re_path('^entry/?$', views.entry),
]
