from typing import Any

from django.contrib import admin
from django.urls import include, path
from drf_yasg import openapi
from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg.views import get_schema_view
from rest_framework import permissions


class _MyOpenAPISchemaGenerator(OpenAPISchemaGenerator):
    def get_schema(self, *args: Any, **kwargs: Any):
        schema = super().get_schema(*args, **kwargs)
        schema.schemes = ["http", "https"]
        return schema


schema_view = get_schema_view(
    openapi.Info(
        title="RSS Temple API",
        default_version="v1",
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
    generator_class=_MyOpenAPISchemaGenerator,
)

urlpatterns = [
    path(
        "swagger<format>/", schema_view.without_ui(cache_timeout=0), name="schema-json"
    ),
    path(
        "swagger/",
        schema_view.with_ui("swagger", cache_timeout=0),
        name="schema-swagger-ui",
    ),
    path("redoc/", schema_view.with_ui("redoc", cache_timeout=0), name="schema-redoc"),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
]
