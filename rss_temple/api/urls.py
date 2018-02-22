from django.urls import path

from . import views

urlpatterns = [
    path('user/<uuid:_uuid>', views.user),
]
