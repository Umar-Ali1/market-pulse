from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth
    path("api/v1/auth/token/",         TokenObtainPairView.as_view(),  name="token_obtain"),
    path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(),     name="token_refresh"),

    # Market data
    path("api/v1/", include("backend.api.urls")),
]
