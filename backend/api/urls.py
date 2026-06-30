from django.urls import path
from backend.api.views import CandleView, AssetListView, HealthView

urlpatterns = [
    path("candles/",  CandleView.as_view(),     name="candles"),
    path("assets/",   AssetListView.as_view(),  name="assets"),
    path("health/",   HealthView.as_view(),     name="health"),
]
